"""Data classification: effective class = max(org default, caller's header, detected entities)."""

import itertools
import threading
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.schemas.policy import PolicyConfigRequest
from app.services import classification_service as cs
from app.services import presidio_service
from app.services.classification_service import Classification, InvalidDataClass, classify
from app.services.data_class import DATA_CLASSES, data_class_rank
from app.services.policy_service import PolicyConfig


def _classify(default="internal", header=None, entities=(), class_map=None):
	return classify(default_class=default, header_value=header, entities=list(entities), class_map=class_map or cs.DEFAULT_CLASS_MAP)


# ── the rule itself ──────────────────────────────────────────────────────────


def test_with_nothing_else_the_org_default_applies():
	assert _classify() == Classification("internal", "default", ())
	assert _classify(default="public").data_class == "public"


@pytest.mark.parametrize("default,header", list(itertools.product(DATA_CLASSES, DATA_CLASSES)))
def test_the_header_can_raise_the_class_but_never_lower_it(default, header):
	result = _classify(default=default, header=header)
	assert data_class_rank(result.data_class) == max(data_class_rank(default), data_class_rank(header))
	assert data_class_rank(result.data_class) >= data_class_rank(default)


@pytest.mark.parametrize("default,header,entity_class", list(itertools.product(DATA_CLASSES, DATA_CLASSES, DATA_CLASSES)))
def test_the_result_is_never_below_any_input(default, header, entity_class):
	result = _classify(default=default, header=header, entities=["thing"], class_map={"thing": entity_class})
	assert data_class_rank(result.data_class) == max(data_class_rank(c) for c in (default, header, entity_class))


def test_source_names_what_set_the_class():
	assert _classify(default="internal", header="confidential").source == "header"
	assert _classify(default="internal", header="public").source == "default"  # the header was ignored, not obeyed
	assert _classify(entities=["ssn"]).source == "detected"
	assert _classify(header="confidential", entities=["ssn"]).source == "detected"  # a tie goes to the most specific reason


def test_the_header_is_case_and_space_tolerant_but_an_unknown_value_is_an_error():
	assert _classify(header=" Confidential ").data_class == "confidential"
	for bad in ("top-secret", "", "  ", "classified"):
		with pytest.raises(InvalidDataClass):
			_classify(header=bad)


def test_detected_entities_are_mapped_and_unmapped_ones_change_nothing():
	result = _classify(entities=["ssn", "email", "mystery"])
	assert result.data_class == "confidential"
	assert result.entities == ("ssn", "email", "mystery")
	assert _classify(entities=["mystery"]).data_class == "internal"


def test_org_map_overrides_and_extends_the_defaults():
	config = PolicyConfig(data_class_map={"ssn": "secret", "EMPLOYEE_ID": "confidential"})
	merged = cs.effective_class_map(config)
	assert merged["ssn"] == "secret" and merged["EMPLOYEE_ID"] == "confidential"
	assert merged["payment_card"] == "confidential"  # untouched default


def test_default_map_treats_the_common_sensitive_entities_as_confidential():
	for entity in ("ssn", "payment_card", "US_SSN", "CREDIT_CARD", "IBAN_CODE", cs.UNSCANNED):
		assert cs.DEFAULT_CLASS_MAP[entity] == "confidential"


# ── detection ────────────────────────────────────────────────────────────────

TEXT = "Contact jane@example.com, SSN 123-45-6789, card 4111 1111 1111 1111."


async def test_regex_detection_finds_every_kind_once():
	found = await cs.detect_entities(TEXT + " again jane@example.com", PolicyConfig())
	assert sorted(found) == ["email", "payment_card", "ssn"]


async def test_clean_text_has_no_entities():
	assert await cs.detect_entities("What is the capital of France?", PolicyConfig()) == []


async def test_detection_is_off_when_the_org_turned_pii_detection_off():
	assert await cs.detect_entities(TEXT, PolicyConfig(pii_detection_enabled=False)) == []


async def test_presidio_detection_uses_the_entities_and_threshold_and_runs_off_the_event_loop(monkeypatch):
	main = threading.get_ident()
	seen = {}

	def fake_analyze(text, entities=None, **_):
		seen["thread"] = threading.get_ident()
		return [SimpleNamespace(entity_type="US_SSN", score=0.95), SimpleNamespace(entity_type="PERSON", score=0.2), SimpleNamespace(entity_type="US_SSN", score=0.9)]

	monkeypatch.setattr(presidio_service, "is_enabled", lambda: True)
	monkeypatch.setattr(presidio_service, "analyze", fake_analyze)
	found = await cs.detect_entities("anything", PolicyConfig())
	assert found == ["US_SSN"]  # the low-score PERSON is dropped, duplicates collapse
	assert seen["thread"] != main


# ── classify a request ───────────────────────────────────────────────────────


async def test_classify_text_combines_default_header_and_detection():
	config = PolicyConfig(default_data_class="public")
	assert (await cs.classify_text("hello", config, None)).data_class == "public"
	assert (await cs.classify_text("hello", config, "confidential")).data_class == "confidential"
	result = await cs.classify_text("my ssn is 123-45-6789", config, None)
	assert (result.data_class, result.source, result.entities) == ("confidential", "detected", ("ssn",))


async def test_text_that_could_not_be_scanned_is_not_assumed_to_be_harmless():
	result = await cs.classify_text(None, PolicyConfig(), None)
	assert result.data_class == "confidential" and result.entities == (cs.UNSCANNED,)


async def test_an_org_can_relax_the_unscanned_class():
	config = PolicyConfig(data_class_map={cs.UNSCANNED: "internal"})
	assert (await cs.classify_text(None, config, None)).data_class == "internal"


def test_metadata_shape_never_contains_text():
	meta = Classification("confidential", "detected", ("ssn",)).as_metadata()
	assert meta == {"class": "confidential", "source": "detected", "entities": ["ssn"]}


# ── policy config ────────────────────────────────────────────────────────────


def test_policy_config_round_trips_the_classification_fields():
	config = PolicyConfig(default_data_class="confidential", data_class_map={"EMPLOYEE_ID": "secret"})
	again = PolicyConfig.from_dict(config.to_dict())
	assert again.default_data_class == "confidential" and again.data_class_map == {"EMPLOYEE_ID": "secret"}
	assert PolicyConfig.from_dict({}).default_data_class == "internal" and PolicyConfig.from_dict({}).data_class_map == {}


def test_stored_garbage_in_the_class_fields_falls_back_to_safe_values():
	config = PolicyConfig.from_dict({"default_data_class": "nope", "data_class_map": {"ssn": "nope", "ok": "secret", "bad key!": "secret"}})
	assert config.default_data_class == "internal"
	assert config.data_class_map == {"ok": "secret"}


def test_routing_fields_default_off_and_round_trip_and_reject_garbage():
	assert PolicyConfig().routing_mode == "off" and PolicyConfig().max_risk_rating == "high"
	again = PolicyConfig.from_dict(PolicyConfig(routing_mode="enforce", max_risk_rating="medium").to_dict())
	assert (again.routing_mode, again.max_risk_rating) == ("enforce", "medium")
	bad = PolicyConfig.from_dict({"routing_mode": "sometimes", "max_risk_rating": "extreme"})
	assert (bad.routing_mode, bad.max_risk_rating) == ("off", "high")  # the API rejects bad values; this only guards hand-edited stored data
	assert PolicyConfigRequest(routing_mode="log_only", max_risk_rating="low").routing_mode == "log_only"
	for field in ("routing_mode", "max_risk_rating"):
		for value in ("sometimes", None):
			with pytest.raises(ValidationError):
				PolicyConfigRequest(**{field: value})


def test_policy_request_validates_the_class_fields():
	assert PolicyConfigRequest(default_data_class="public", data_class_map={"US_SSN": "secret"}).data_class_map == {"US_SSN": "secret"}
	for bad in ({"default_data_class": "nope"}, {"data_class_map": {"ssn": "nope"}}, {"data_class_map": {"bad key": "secret"}}, {"data_class_map": {f"E{i}": "secret" for i in range(51)}}):
		with pytest.raises(ValidationError):
			PolicyConfigRequest(**bad)
