"""One plain sentence for a refused caller: what was refused and why, in words an end user can act on.

This is a separate field from the technical ``detail``. It names only what the caller already knows (the model they
asked for, their request's data class) and never says which rule, keyword, pattern, plugin or registry setting was
involved, so it cannot teach a caller how the organization configured the gateway. The console shows the same sentence.
"""

from __future__ import annotations

from typing import Final

_MAX_ECHO: Final = 80

_ROUTING_EXCLUSION: Final[dict[str, str]] = {
	"class_too_low": "{model} is not approved for {data_class} data in your organization.",
	"region": "{model} cannot serve this request under your organization's data-region setting.",
	"risk": "{model} is above your organization's risk limit for models.",
	"not_allowed_by_policy": "{model} is not on your organization's approved model list.",
}
_UNAVAILABLE: Final = "{model} is not available to your organization right now."
for _code in ("disabled", "no_key", "key_inactive"):  # how the org wired its registry is not the caller's business
	_ROUTING_EXCLUSION[_code] = _UNAVAILABLE

_POLICY: Final[dict[str, str]] = {
	"prompt_injection_detected": "This request looks like an attempt to override the assistant's instructions, so your organization's policy blocked it.",
	"model_not_allowed": "The model you asked for is not approved by your organization's policy.",
	"blocked_keyword": "This request contains wording that your organization's policy does not allow.",
	"pii_detected": "This request appears to contain personal or sensitive data that your organization's policy does not allow to be sent.",
	"tool_blocked": "A tool in this request is not allowed by your organization's policy.",
	"tool_not_allowed": "A tool in this request is not allowed by your organization's policy.",
	"tool_taint_forced_sink": "A tool with side effects cannot be used right after untrusted tool output.",
	"request_too_complex": "This request is too large or complex to check completely, so it was refused.",
	"scan_limit_exceeded": "This request is too large or complex to check completely, so it was refused.",
	"response_keyword_blocked": "The model's answer was withheld by your organization's policy.",
	"response_pii_detected": "The model's answer was withheld by your organization's policy.",
}
_POLICY_DEFAULT: Final = "This request was blocked by your organization's policy."
_POLICY_PLUGIN: Final = "A policy check set up by your organization blocked this request."


def _echo(model: str) -> str:
	"""The model name the caller sent, on one line and bounded, so the sentence cannot be used to reflect arbitrary text."""
	one_line = " ".join(model.split())
	return one_line[:_MAX_ECHO] or "The model"


def explain_routing(reason: str, data_class: str, requested: str) -> str:
	"""Why routing authorized no model, from a routing decision's ``reason`` (see ``routing_service``)."""
	model = _echo(requested)
	if reason.startswith("not_authorized:"):
		template = _ROUTING_EXCLUSION.get(reason.split(":", 1)[1])
		if template is not None:
			return template.format(model=model, data_class=data_class)
		return _UNAVAILABLE.format(model=model)
	if reason == "not_in_registry":
		return f"{model} is not an approved model for your organization."
	if reason == "no_model_with_capability":
		return f"Your organization has no approved model with that capability for {data_class} data."
	return f"No model approved for {data_class} data is available to serve this request."


def explain_policy(reason_code: str | None) -> str:
	"""Why policy blocked a request or an answer, from a policy decision's ``reason_code``."""
	if reason_code and reason_code.startswith("wasm_plugin"):
		return _POLICY_PLUGIN
	return _POLICY.get(reason_code or "", _POLICY_DEFAULT)
