"""Routing core (Phase 2, S4a): which models may serve a request of a given sensitivity, and which one is chosen.

The properties below are the guarantee S4b builds on: nothing outside the authorized set is ever chosen, and
nothing is excluded without a stated reason.
"""

from __future__ import annotations

import itertools
import uuid

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.services.data_class import DATA_CLASSES, data_class_rank
from app.services.routing_service import EXCLUSION_ORDER, Candidate, authorize, choose_route, clearance, decide, may_leave_registry

REGIONS = ("us", "eu", "ap", "global")
RISKS = ("low", "medium", "high")
RISK_RANK = {name: index for index, name in enumerate(RISKS)}
CAPABILITIES = ("CODE_GENERATION", "VISION", "SUMMARIZATION")


def candidate(model_id="openai/gpt-4o", **overrides) -> Candidate:
	fields = dict(
		model_id=model_id, provider=model_id.split("/", 1)[0], enabled=True, key_id=uuid.uuid4(), key_active=True,
		key_class="confidential", entry_class="confidential", regions=("us",), risk="medium", capabilities=(), cost_tier=None,
	)
	return Candidate(**{**fields, **overrides})


def allow_all(_model: str) -> bool:
	return True


def run(candidates, *, data_class="internal", region="us", max_risk="high", allows=allow_all):
	return authorize(candidates, data_class=data_class, org_region=region, max_risk=max_risk, allows_model=allows)


# ── strategies ───────────────────────────────────────────────────────────────

classes = st.sampled_from(DATA_CLASSES)
candidates_st = st.builds(
	Candidate,
	model_id=st.integers(0, 40).map(lambda i: f"prov{i % 3}/model-{i}"),
	provider=st.sampled_from(("prov0", "prov1", "prov2")),
	enabled=st.booleans(),
	key_id=st.one_of(st.none(), st.uuids()),
	key_active=st.booleans(),
	key_class=st.one_of(st.none(), classes),
	entry_class=classes,
	regions=st.lists(st.sampled_from(REGIONS), min_size=1, max_size=4, unique=True).map(tuple),
	risk=st.sampled_from(RISKS),
	capabilities=st.lists(st.sampled_from(CAPABILITIES), max_size=3, unique=True).map(tuple),
	cost_tier=st.one_of(st.none(), st.sampled_from(RISKS)),
)
pools = st.lists(candidates_st, max_size=12, unique_by=lambda c: c.model_id)
allow_sets = st.one_of(st.none(), st.sets(st.integers(0, 40).map(lambda i: f"prov{i % 3}/model-{i}"), max_size=30))


def allows_from(allowed):
	return allow_all if allowed is None else (lambda model: model in allowed)


def oracle_reason(c: Candidate, data_class, region, max_risk, allows):
	"""An independent restatement of the rules, in the documented order."""
	if not c.enabled:
		return "disabled"
	if c.key_id is None:
		return "no_key"
	if not c.key_active:
		return "key_inactive"
	if data_class_rank(c.entry_class) < data_class_rank(data_class) or data_class_rank(c.key_class or "public") < data_class_rank(data_class):
		return "class_too_low"
	if region not in c.regions and "global" not in c.regions:
		return "region"
	if RISK_RANK[c.risk] > RISK_RANK[max_risk]:
		return "risk"
	if not allows(c.model_id):
		return "not_allowed_by_policy"
	return None


SETTINGS = settings(max_examples=300, deadline=None)

# ── properties ───────────────────────────────────────────────────────────────


@SETTINGS
@given(pool=pools, data_class=classes, region=st.sampled_from(REGIONS[:3]), max_risk=st.sampled_from(RISKS), allowed=allow_sets)
def test_every_authorized_model_satisfies_every_rule_and_every_exclusion_has_the_right_reason(pool, data_class, region, max_risk, allowed):
	allows = allows_from(allowed)
	result = run(pool, data_class=data_class, region=region, max_risk=max_risk, allows=allows)

	authorized_ids = {c.model_id for c in result.authorized}
	assert authorized_ids.isdisjoint(result.excluded)
	assert authorized_ids | set(result.excluded) == {c.model_id for c in pool}
	for c in pool:
		expected = oracle_reason(c, data_class, region, max_risk, allows)
		if expected is None:
			assert c.model_id in authorized_ids
			assert clearance(c) >= data_class_rank(data_class)
		else:
			assert result.excluded[c.model_id] == expected


@SETTINGS
@given(pool=pools, low=classes, high=classes, region=st.sampled_from(REGIONS[:3]))
def test_a_more_sensitive_request_never_has_more_authorized_models(pool, low, high, region):
	if data_class_rank(low) > data_class_rank(high):
		low, high = high, low
	narrow = {c.model_id for c in run(pool, data_class=high, region=region).authorized}
	wide = {c.model_id for c in run(pool, data_class=low, region=region).authorized}
	assert narrow <= wide


@SETTINGS
@given(pool=pools, data_class=classes, cap=st.sampled_from(CAPABILITIES), requested_index=st.integers(0, 12))
def test_the_chosen_route_is_always_inside_the_authorized_set_and_never_a_substitute(pool, data_class, cap, requested_index):
	result = run(pool, data_class=data_class)
	authorized_ids = {c.model_id for c in result.authorized}

	if pool:
		requested = pool[requested_index % len(pool)].model_id
		route = choose_route(result, requested)
		if requested in authorized_ids:
			assert route is not None and route.candidate.model_id == requested and route.reason == "exact"
		else:
			assert route is None  # an unauthorized model is refused, not swapped for another

	route = choose_route(result, f"cap:{cap}")
	matching = [c for c in result.authorized if cap in c.capabilities]
	if not matching:
		assert route is None
	else:
		assert route is not None and route.reason == "capability"
		assert route.candidate in matching
		cost = {None: 1, "low": 0, "medium": 1, "high": 2}
		best = min(matching, key=lambda c: (cost[c.cost_tier], RISK_RANK[c.risk], c.model_id))
		assert route.candidate == best
		assert choose_route(result, f"cap:{cap}") == route  # deterministic


@SETTINGS
@given(pool=pools, data_class=classes, new_key_class=classes)
def test_lowering_a_keys_clearance_never_adds_models(pool, data_class, new_key_class):
	before = {c.model_id for c in run(pool, data_class=data_class).authorized}
	lowered = [c if data_class_rank(new_key_class) >= data_class_rank(c.key_class or "public") else _with(c, key_class=new_key_class) for c in pool]
	after = {c.model_id for c in run(lowered, data_class=data_class).authorized}
	assert after <= before


def _with(c: Candidate, **changes) -> Candidate:
	return Candidate(**{**c.__dict__, **changes})


# ── the rules, one at a time ─────────────────────────────────────────────────


def test_a_model_is_cleared_only_as_high_as_its_lower_of_model_and_key_class():
	assert [c.model_id for c in run([candidate(entry_class="confidential", key_class="internal")], data_class="confidential").authorized] == []
	assert [c.model_id for c in run([candidate(entry_class="internal", key_class="secret")], data_class="confidential").authorized] == []
	assert len(run([candidate(entry_class="confidential", key_class="confidential")], data_class="confidential").authorized) == 1


def test_exclusion_reasons_follow_the_documented_order():
	several_problems = candidate(enabled=False, key_id=None, key_active=False, entry_class="public", regions=("ap",), risk="high")
	assert run([several_problems], data_class="secret").excluded[several_problems.model_id] == "disabled"
	assert EXCLUSION_ORDER == ("disabled", "no_key", "key_inactive", "class_too_low", "region", "risk", "not_allowed_by_policy")


def test_global_means_any_region_like_provider_keys_do():
	assert len(run([candidate(regions=("global",))], region="eu").authorized) == 1
	assert run([candidate(regions=("us",))], region="eu").excluded == {"openai/gpt-4o": "region"}


def test_risk_above_the_orgs_ceiling_is_excluded():
	assert run([candidate(risk="high")], max_risk="medium").excluded == {"openai/gpt-4o": "risk"}
	assert len(run([candidate(risk="medium")], max_risk="medium").authorized) == 1


def test_the_policy_allowlist_still_applies():
	result = run([candidate("openai/gpt-4o"), candidate("openai/gpt-4o-mini")], allows=lambda m: m == "openai/gpt-4o")
	assert [c.model_id for c in result.authorized] == ["openai/gpt-4o"]
	assert result.excluded == {"openai/gpt-4o-mini": "not_allowed_by_policy"}


def test_a_model_without_a_key_or_with_an_inactive_key_is_never_routable():
	assert run([candidate(key_id=None, key_class=None)]).excluded["openai/gpt-4o"] == "no_key"
	assert run([candidate(key_active=False)]).excluded["openai/gpt-4o"] == "key_inactive"


def test_authorized_models_are_ordered_by_id():
	result = run([candidate("z/m"), candidate("a/m"), candidate("m/m")])
	assert [c.model_id for c in result.authorized] == ["a/m", "m/m", "z/m"]


def test_a_capability_request_prefers_cheaper_then_lower_risk_then_name():
	pool = [
		candidate("a/pricey", capabilities=("VISION",), cost_tier="high"),
		candidate("b/risky", capabilities=("VISION",), cost_tier="low", risk="high"),
		candidate("c/safe", capabilities=("VISION",), cost_tier="low", risk="low"),
		candidate("d/other", capabilities=("CODE_GENERATION",)),
	]
	assert choose_route(run(pool), "cap:VISION").candidate.model_id == "c/safe"
	assert choose_route(run(pool), "cap:UNKNOWN") is None


# ── destinations the registry does not govern ────────────────────────────────


@pytest.mark.parametrize("mode", ["off", "log_only"])
@pytest.mark.parametrize("data_class", DATA_CLASSES)
def test_nothing_is_withheld_unless_routing_is_enforced(mode, data_class):
	assert may_leave_registry(mode, data_class, "public") is True


@pytest.mark.parametrize("data_class,ceiling", list(itertools.product(DATA_CLASSES, DATA_CLASSES)))
def test_when_enforcing_content_may_go_to_ungoverned_destinations_only_up_to_the_ceiling(data_class, ceiling):
	assert may_leave_registry("enforce", data_class, ceiling) is (data_class_rank(data_class) <= data_class_rank(ceiling))


# ── the decision, with its mode ──────────────────────────────────────────────


def _decide(pool, mode, requested="openai/gpt-4o", data_class="confidential", **kw):
	return decide(pool, mode=mode, data_class=data_class, org_region="us", max_risk="high", allows_model=allow_all, requested=requested, **kw)


def test_off_mode_decides_nothing():
	decision = _decide([candidate()], "off")
	assert decision is None


def test_enforce_blocks_when_nothing_authorized_serves_the_request():
	decision = _decide([candidate(entry_class="internal")], "enforce")
	assert decision.model is None and decision.blocked is True
	assert decision.reason == "not_authorized:class_too_low"


def test_log_only_reports_the_same_decision_but_never_blocks():
	decision = _decide([candidate(entry_class="internal")], "log_only")
	assert decision.model is None and decision.blocked is False and decision.reason == "not_authorized:class_too_low"


def test_a_model_missing_from_the_registry_is_reported_as_such():
	decision = _decide([candidate("anthropic/claude")], "enforce", requested="openai/gpt-4o")
	assert decision.blocked and decision.reason == "not_in_registry"


def test_an_authorized_exact_request_routes_to_itself_with_its_key():
	pool = [candidate()]
	decision = _decide(pool, "enforce")
	assert (decision.model, decision.key_id, decision.reason, decision.blocked) == ("openai/gpt-4o", pool[0].key_id, "authorized", False)
	assert decision.authorized == ("openai/gpt-4o",)


def test_a_capability_request_reports_the_chosen_model_and_why():
	decision = _decide([candidate("a/m", capabilities=("VISION",))], "enforce", requested="cap:VISION")
	assert decision.model == "a/m" and decision.reason == "capability"
	assert _decide([candidate("a/m")], "enforce", requested="cap:VISION").reason == "no_model_with_capability"


def test_metadata_has_names_and_reasons_only():
	meta = _decide([candidate(), candidate("openai/mini", enabled=False)], "enforce").as_metadata()
	assert meta == {
		"mode": "enforce", "data_class": "confidential", "requested": "openai/gpt-4o", "model": "openai/gpt-4o",
		"reason": "authorized", "authorized": ["openai/gpt-4o"], "excluded": {"openai/mini": "disabled"},
	}


def test_metadata_excluded_list_is_bounded():
	pool = [candidate(f"p/m{i}", enabled=False) for i in range(60)]
	assert len(_decide(pool, "enforce").as_metadata()["excluded"]) == 20


def test_unknown_mode_is_a_programming_error():
	with pytest.raises(ValueError):
		_decide([candidate()], "sometimes")
