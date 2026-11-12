"""The plain-language sentence a refused caller gets: what was refused and why, without leaking what the org configured."""

from __future__ import annotations

import pytest

from app.services.policy_service import POLICY_BLOCK_STATUS, PolicyDecision
from app.services.refusal_explanations import explain_policy, explain_routing
from app.services.routing_service import EXCLUSION_ORDER, RoutingDecision


def _decision(reason: str, model: str | None = None, data_class: str = "confidential", requested: str = "openai/gpt-4o") -> RoutingDecision:
	return RoutingDecision(
		mode="enforce", data_class=data_class, requested=requested, model=model, key_id=None, reason=reason, authorized=(), excluded={},
	)


def test_class_too_low_names_the_class_and_the_requested_model():
	text = explain_routing("not_authorized:class_too_low", "confidential", "openai/gpt-4o")
	assert "openai/gpt-4o" in text and "confidential" in text


@pytest.mark.parametrize("code", EXCLUSION_ORDER)
def test_every_exclusion_code_has_its_own_sentence(code):
	text = explain_routing(f"not_authorized:{code}", "internal", "openai/gpt-4o")
	assert text.endswith(".") and "openai/gpt-4o" in text
	assert "_" not in text and ":" not in text  # no raw reason code leaks into the sentence


def test_infrastructure_reasons_are_not_distinguished_to_the_caller():
	# a disabled model, a missing key and an inactive key look the same: the caller must not learn how the org wired its registry
	texts = {explain_routing(f"not_authorized:{c}", "internal", "m") for c in ("disabled", "no_key", "key_inactive")}
	assert len(texts) == 1


@pytest.mark.parametrize("reason", ["not_in_registry", "no_model_with_capability", "something_new", "not_authorized:from_the_future"])
def test_other_and_unknown_reasons_still_get_a_sentence(reason):
	text = explain_routing(reason, "secret", "cap:chat")
	assert text and "\n" not in text


def test_the_requested_model_echo_is_bounded_and_single_line():
	text = explain_routing("not_authorized:region", "internal", "x" * 500 + "\nINJECT")
	assert len(text) < 300 and "\n" not in text


@pytest.mark.parametrize(
	"code",
	["prompt_injection_detected", "model_not_allowed", "blocked_keyword", "pii_detected", "tool_blocked", "tool_not_allowed",
	 "tool_taint_forced_sink", "request_too_complex", "scan_limit_exceeded", "response_keyword_blocked", "response_pii_detected",
	 "wasm_plugin:my-secret-plugin", "wasm_plugin_error:my-secret-plugin", None, "brand_new_code"],
)
def test_every_policy_reason_has_a_sentence_and_names_no_rule_detail(code):
	text = explain_policy(code)
	assert text.endswith(".") and "\n" not in text
	assert "my-secret-plugin" not in text


def test_policy_sentences_do_not_say_which_pattern_matched():
	assert "ssn" not in explain_policy("pii_detected").lower()
	assert "keyword" not in explain_policy("blocked_keyword").lower() or "wording" in explain_policy("blocked_keyword")


def test_routing_decision_carries_its_explanation_only_when_nothing_was_authorized():
	refused = _decision("not_authorized:class_too_low")
	served = _decision("authorized", model="openai/gpt-4o")
	assert refused.explanation and "explanation" in refused.as_metadata()
	assert served.explanation is None and "explanation" not in served.as_metadata()


def test_the_routing_refusal_body_keeps_its_shape_and_adds_the_explanation():
	from app.services.llm_service import LLMService

	response = LLMService._routing_block_response(_decision("not_authorized:class_too_low"))
	import json

	body = json.loads(response.body)
	assert response.status_code == 446
	assert body["error"] == "routing_blocked" and body["reason_code"] == "no_authorized_model"
	assert body["detail"] == "No model authorized for this request's data class can serve it."
	assert body["explanation"] == explain_routing("not_authorized:class_too_low", "confidential", "openai/gpt-4o")


def test_the_policy_refusal_body_keeps_its_shape_and_adds_the_explanation():
	import json

	from app.services.llm_service import LLMService

	decision = PolicyDecision(allowed=False, action="block", reason_code="pii_detected", detail="Potential PII detected: ssn", triggered_rules=["pii_detection"])
	response = LLMService._policy_block_response(decision)
	body = json.loads(response.body)
	assert response.status_code == POLICY_BLOCK_STATUS
	assert body["detail"] == "Potential PII detected: ssn" and body["reason_code"] == "pii_detected"
	assert body["explanation"] == explain_policy("pii_detected")


def test_policy_metadata_has_an_explanation_only_for_a_refusal():
	allowed = PolicyDecision(allowed=True).as_metadata()["policy"]
	blocked = PolicyDecision(allowed=False, action="block", reason_code="blocked_keyword").as_metadata()["policy"]
	assert "explanation" not in allowed
	assert blocked["explanation"] == explain_policy("blocked_keyword")
