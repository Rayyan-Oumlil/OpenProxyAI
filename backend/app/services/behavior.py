"""Behaviour settings: what the organization wants a model to be like, in terms that do not depend on the provider.

A caller (or the org's defaults) says ``creativity=low``, ``reasoning_depth=high``, ``max_response_length=short`` or
``citations=true``. This module is the *only* place those words become provider parameters, so a provider's quirks live in
one file and every endpoint that calls a model gets the same behaviour.

Rules, each pinned by a test:

- **The org's ceiling can only lower.** Defaults fill in what the caller left unsaid; a request above the ceiling is clamped to
  it and reported (``Resolved.clamped``), never refused and never silently ignored.
- **A ceiling also clamps the caller's own raw parameters** (``temperature``, ``max_tokens``, ``reasoning_effort``): otherwise
  asking for ``temperature=2`` would walk around a "low creativity" ceiling. With no ceiling set, raw parameters are untouched.
- **A raw parameter the caller sent always beats a behaviour setting** (it was an explicit choice).
- **Only parameters the model supports are sent.** Support comes from the provider library's own list for that model; a setting
  the model cannot honour is *ignored and recorded* in the trace (``Plan.ignored``), and when the capabilities are unknown nothing
  derived is sent. A provider never receives a parameter it would reject.
- ``citations`` has no provider parameter. It is a fixed instruction added after the leading system messages.
"""

from __future__ import annotations

import functools
import logging
from collections.abc import Mapping
from dataclasses import dataclass, fields
from typing import Any, Final

logger = logging.getLogger(__name__)

HEADER: Final = "x-openproxy-behavior"

CREATIVITY: Final = ("low", "medium", "high")
REASONING: Final = ("low", "medium", "high")
LENGTH: Final = ("short", "medium", "long")
SCALES: Final = {"creativity": CREATIVITY, "reasoning_depth": REASONING, "max_response_length": LENGTH}
KEYS: Final = (*SCALES, "citations")

TEMPERATURE: Final = {"low": 0.2, "medium": 0.7, "high": 1.0}
MAX_TOKENS: Final = {"short": 256, "medium": 1024, "long": 4096}
_EFFORT_RANK: Final = ("minimal", *REASONING)  # a caller's own reasoning_effort may be "minimal", which sits below "low"

# Where a call goes and with whose credentials is the gateway's decision (the org's provider keys and registry), never the caller's.
# A request body may carry extra fields, and these must never reach the provider call, with or without a ceiling.
TRANSPORT_FIELDS: Final = frozenset({
    "api_base", "base_url", "api_key", "api_version", "client", "custom_llm_provider", "extra_headers", "headers", "organization",
    "azure_ad_token", "aws_access_key_id", "aws_secret_access_key", "aws_session_token", "vertex_credentials", "vertex_project", "vertex_location",
})

# Fail closed: while a ceiling is active, only these reach the provider (plus what the plan itself sets). A name list of aliases is
# incomplete by nature (every provider invents new ones), so anything not listed here is removed and recorded, whatever it is called.
ALLOWED: Final = frozenset({
    "model", "messages", "temperature", "max_tokens", "stream", "stop", "user", "frequency_penalty", "presence_penalty",
    "tools", "tool_choice", "parallel_tool_calls", "functions", "function_call", "response_format", "stream_options",
    "reasoning_effort",
})

CITATION_INSTRUCTION: Final = (
	"When you rely on a specific source, document or earlier message, name it. "
	"Say plainly when you are not sure or have no source; do not invent references."
)


class InvalidBehavior(ValueError):
	"""A behaviour setting that is not one of the allowed words. The caller gets a 400 with the message."""


@dataclass(frozen=True)
class Behavior:
	creativity: str | None = None
	reasoning_depth: str | None = None
	max_response_length: str | None = None
	citations: bool | None = None

	def as_dict(self) -> dict[str, Any]:
		return {f.name: getattr(self, f.name) for f in fields(self) if getattr(self, f.name) is not None}


def from_mapping(raw: object) -> Behavior:
	"""Strict: a caller's body field. Anything that is not exactly a known setting with a known value is an error."""
	if not isinstance(raw, Mapping):
		raise InvalidBehavior("behavior must be an object such as {\"creativity\": \"low\"}")
	unknown = sorted(set(raw) - set(KEYS))
	if unknown:
		raise InvalidBehavior(f"unknown behavior setting {unknown[0]!r}; allowed: {', '.join(KEYS)}")
	values: dict[str, Any] = {}
	for key, value in raw.items():
		if key == "citations":
			if not isinstance(value, bool):
				raise InvalidBehavior("citations must be true or false")
		elif not isinstance(value, str) or value not in SCALES[key]:
			raise InvalidBehavior(f"{key} must be one of: {', '.join(SCALES[key])}")
		values[key] = value
	return Behavior(**values)


def parse_header(value: str | None) -> Behavior:
	"""``creativity=low; reasoning_depth=high, citations=true``. Either ``;`` or ``,`` separates pairs; case is ignored."""
	if value is None or not value.strip():
		return Behavior()
	values: dict[str, Any] = {}
	for part in value.replace(";", ",").split(","):
		if not part.strip():
			continue
		key, sep, word = (s.strip().lower() for s in part.partition("="))
		if not sep or not word:
			raise InvalidBehavior(f"{HEADER}: expected name=value, got {part.strip()!r}")
		if key in values:
			raise InvalidBehavior(f"{HEADER}: {key} given twice")
		if key == "citations":
			if word not in ("true", "false"):
				raise InvalidBehavior(f"{HEADER}: citations must be true or false")
			values[key] = word == "true"
		elif key in SCALES:
			if word not in SCALES[key]:
				raise InvalidBehavior(f"{HEADER}: {key} must be one of: {', '.join(SCALES[key])}")
			values[key] = word
		else:
			raise InvalidBehavior(f"{HEADER}: unknown setting {key!r}; allowed: {', '.join(KEYS)}")
	return Behavior(**values)


def from_stored(raw: object) -> Behavior:
	"""The org's stored defaults or ceiling. The API validates what is saved; if something invalid got in anyway, drop that entry
	rather than guess (a ceiling that cannot be read must not become a stricter or looser one by accident)."""
	if not isinstance(raw, Mapping):
		return Behavior()
	values: dict[str, Any] = {}
	for key in KEYS:
		value = raw.get(key)
		if key == "citations":
			if isinstance(value, bool):
				values[key] = value
		elif isinstance(value, str) and value in SCALES[key]:
			values[key] = value
	return Behavior(**values)


def merge(primary: Behavior, secondary: Behavior) -> Behavior:
	"""``primary``'s settings, with ``secondary`` filling what ``primary`` left unsaid (a body field over the header)."""
	return Behavior(**{f.name: getattr(primary, f.name) if getattr(primary, f.name) is not None else getattr(secondary, f.name) for f in fields(Behavior)})


@dataclass(frozen=True)
class Resolved:
	"""What the request asked for, the org's defaults and ceiling, and the outcome."""

	requested: Behavior
	effective: Behavior
	ceiling: Behavior
	clamped: tuple[str, ...] = ()

	def as_metadata(self) -> dict[str, Any]:
		return {"requested": self.requested.as_dict(), "effective": self.effective.as_dict(), "clamped": list(self.clamped)}


def resolve(requested: Behavior, defaults: Behavior, ceiling: Behavior) -> Resolved:
	"""The request, else the org's default, lowered to the ceiling. The ceiling never raises anything."""
	effective: dict[str, Any] = {}
	clamped: list[str] = []
	for key, scale in SCALES.items():
		value = getattr(requested, key) or getattr(defaults, key)
		cap = getattr(ceiling, key)
		if value is not None and cap is not None and scale.index(value) > scale.index(cap):
			value = cap
			clamped.append(key)
		if value is not None:
			effective[key] = value
	citations = requested.citations if requested.citations is not None else defaults.citations
	if citations is not None:
		effective["citations"] = citations
	return Resolved(requested=requested, effective=Behavior(**effective), ceiling=ceiling, clamped=tuple(clamped))


def settle(stored_defaults: object, stored_ceiling: object, requested: Behavior) -> Resolved | None:
	"""``resolve`` for a request against an org's stored settings. ``None`` when nobody asked for anything and the org set nothing,
	so an organization that does not use behaviour settings runs exactly the code it ran before they existed."""
	defaults, ceiling = from_stored(stored_defaults), from_stored(stored_ceiling)
	ceiling = Behavior(creativity=ceiling.creativity, reasoning_depth=ceiling.reasoning_depth, max_response_length=ceiling.max_response_length)
	if not (requested.as_dict() or defaults.as_dict() or ceiling.as_dict()):
		return None
	return resolve(requested, defaults, ceiling)


@dataclass(frozen=True)
class Plan:
	"""The provider parameters to add to (or lower in) a call, and what was left out and why."""

	params: dict[str, Any]
	ignored: tuple[dict[str, str], ...] = ()
	clamped: tuple[dict[str, Any], ...] = ()
	remove: tuple[str, ...] = ()  # parameters to take out of the call: aliases of a limit the org has capped

	@property
	def changes_more_than_temperature(self) -> bool:
		"""The answer cache is keyed on temperature, not on the other parameters, so these calls must not use it."""
		return bool(self.remove) or any(name != "temperature" for name in self.params)

	def as_metadata(self) -> dict[str, Any]:
		return {"applied": dict(self.params), "ignored": list(self.ignored), "clamped_params": list(self.clamped), "removed": list(self.remove)}


@functools.lru_cache(maxsize=512)
def supported_params(provider: str, model_name: str) -> frozenset[str] | None:
	"""The OpenAI-style parameters this model accepts, from the provider library. ``None`` when that cannot be determined."""
	try:
		import litellm

		found = litellm.get_supported_openai_params(model=model_name, custom_llm_provider=provider)
	except Exception:  # noqa: BLE001
		logger.warning("could not read the supported parameters for %s/%s", provider, model_name, exc_info=True)
		return None
	return frozenset(found) if found else None


def _cap_of(scale_value: str | None, table: Mapping[str, Any]) -> Any:
	return table[scale_value] if scale_value is not None else None


def plan_params(*, resolved: Resolved | None, explicit: Mapping[str, Any], supported: frozenset[str] | None) -> Plan:
	"""Turn the effective behaviour into provider parameters for one model.

	``explicit`` is what the caller sent as raw parameters. ``supported`` is what the model accepts (``None`` = unknown).
	"""
	if resolved is None:
		return Plan(params={})
	eff, ceiling = resolved.effective, resolved.ceiling
	params: dict[str, Any] = {}
	ignored: list[dict[str, str]] = []
	clamped: list[dict[str, Any]] = []

	def numeric(name: str, level: str | None, cap_level: str | None, table: Mapping[str, Any]) -> None:
		cap = _cap_of(cap_level, table)
		if name in explicit and explicit[name] is not None:
			given = explicit[name]
			if cap is not None and isinstance(given, (int, float)) and not isinstance(given, bool) and given > cap:
				params[name] = cap
				clamped.append({"param": name, "from": given, "to": cap})
			return
		if level is None:
			return
		if supported is None or name not in supported:
			reason = "the model's supported parameters are unknown" if supported is None else "the model does not accept it"
			ignored.append({"param": name, "reason": reason})
			return
		params[name] = table[level]

	numeric("temperature", eff.creativity, ceiling.creativity, TEMPERATURE)
	numeric("max_tokens", eff.max_response_length, ceiling.max_response_length, MAX_TOKENS)

	cap_depth = ceiling.reasoning_depth
	given_effort = explicit.get("reasoning_effort")
	if given_effort is not None:
		if cap_depth is not None and (given_effort not in _EFFORT_RANK or _EFFORT_RANK.index(given_effort) > _EFFORT_RANK.index(cap_depth)):
			params["reasoning_effort"] = cap_depth
			clamped.append({"param": "reasoning_effort", "from": given_effort, "to": cap_depth})
	elif eff.reasoning_depth is not None:
		if supported is None or "reasoning_effort" not in supported:
			reason = "the model's supported parameters are unknown" if supported is None else "the model does not accept it"
			ignored.append({"param": "reasoning_effort", "reason": reason})
		else:
			params["reasoning_effort"] = eff.reasoning_depth
	remove: list[str] = []
	if any(getattr(ceiling, key) is not None for key in SCALES):
		remove.extend(k for k in explicit if k not in ALLOWED and k not in remove)  # includes n and best_of, which multiply the output
	return Plan(params=params, ignored=tuple(ignored), clamped=tuple(clamped), remove=tuple(dict.fromkeys(remove)))


def with_citation_instruction(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
	"""A copy of ``messages`` with the citation instruction as a system message after any leading system messages."""
	index = 0
	while index < len(messages) and messages[index].get("role") == "system":
		index += 1
	return [*messages[:index], {"role": "system", "content": CITATION_INSTRUCTION}, *messages[index:]]


def citation_system_prompt(system_prompt: str | None) -> str:
	"""For callers that keep a system prompt as a string (a conversation): the same instruction, appended."""
	return f"{system_prompt}\n\n{CITATION_INSTRUCTION}" if system_prompt else CITATION_INSTRUCTION
