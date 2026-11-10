"""Policy service for pre-provider request guardrails and policy metadata."""

from __future__ import annotations

import asyncio
import fnmatch
import json
import math
import re
import re as _re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.schemas.chat import ChatCompletionRequest, EmbeddingRequest
from app.utils.logging import get_logger
from app.services import pii_detection, presidio_service
from app.services.data_class import DATA_CLASSES, DEFAULT_DATA_CLASS

logger = get_logger(__name__)

# ── Redis key helpers ────────────────────────────────────────────────────────

_POLICY_CACHE_TTL = 60  # seconds
_POLICY_CACHE_KEY = "policy:config:{org_id}"


# ── Policy config (per-org, loaded from DB / Redis) ──────────────────────────

_ROUTING_MODES = ("off", "log_only", "enforce")
_RISK_LEVELS = ("low", "medium", "high")
_ENTITY_NAME = re.compile(r"^[A-Za-z0-9_]{1,50}$")


def _valid_class(value: object, fallback: str) -> str:
	return value if isinstance(value, str) and value in DATA_CLASSES else fallback


def _valid_rate(value: object) -> float:
	"""A sample rate in [0, 1]. Anything else stored (a corrupt value, NaN, a string) means off, never 'capture everything'."""
	if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
		return 0.0
	return float(value)


def _clean_class_map(raw: object) -> dict[str, str]:
	"""Stored data is validated by the API; if something invalid got in anyway, drop it rather than guess."""
	if not isinstance(raw, dict):
		return {}
	return {k: v for k, v in raw.items() if isinstance(k, str) and _ENTITY_NAME.match(k) and v in DATA_CLASSES}



@dataclass
class PolicyConfig:
	"""Runtime policy configuration for a single organization."""

	enforcement_mode: str = "off"
	allowed_models: list[str] = field(default_factory=list)
	blocked_keywords: list[str] = field(default_factory=list)
	pii_detection_enabled: bool = True
	pii_entities: list[str] = field(default_factory=list)
	model_rate_limits: dict[str, dict[str, int]] = field(default_factory=dict)  # e.g. {"openai/gpt-4o": {"rpm": 100, "tpm": 50000}}
	per_team_limits: dict[str, int] = field(default_factory=dict)  # {"rpm": 60, "tpm": 50000} applied when request has team_id
	updated_at: datetime | None = None
	prompt_injection_detection_enabled: bool = False
	response_guardrails_enabled: bool = False
	response_pii_redact: bool = False
	# MCP gateway: fnmatch patterns on namespaced tool names ("<server>__<tool>"); empty allowlist = all tools.
	mcp_allowed_tools: list[str] = field(default_factory=list)
	mcp_blocked_tools: list[str] = field(default_factory=list)
	# Data classification (Phase 2): the class of a request that shows no sign of being more sensitive, and the
	# class each detected entity (e.g. "ssn", "US_SSN") raises it to. The org's map overrides the built-in defaults.
	default_data_class: str = DEFAULT_DATA_CLASS
	data_class_map: dict[str, str] = field(default_factory=dict)
	# Classification-aware routing (Phase 2): off = today's behavior; log_only = decide and record, never refuse;
	# enforce = only models authorized for the request's data class may serve it.
	routing_mode: str = "off"
	max_risk_rating: str = "high"  # models rated above this are never authorized
	# Evaluation (Phase 3): the share of eligible requests whose redacted prompt and answer are kept for evaluation.
	# 0 (the default) stores nothing.
	payload_capture_sample_rate: float = 0.0

	@classmethod
	def from_settings(cls) -> "PolicyConfig":
		"""Build a config from global env settings (fallback when no org override)."""
		return cls(
			enforcement_mode=settings.POLICY_ENFORCEMENT_MODE,
			allowed_models=list(settings.POLICY_ALLOWED_MODELS),
			blocked_keywords=list(settings.POLICY_BLOCKED_KEYWORDS),
			pii_detection_enabled=settings.POLICY_PII_DETECTION_ENABLED,
			pii_entities=[],
		)

	@classmethod
	def from_dict(cls, data: dict) -> "PolicyConfig":
		return cls(
			enforcement_mode=data.get("enforcement_mode", "off"),
			allowed_models=list(data.get("allowed_models") or []),
			blocked_keywords=list(data.get("blocked_keywords") or []),
			pii_detection_enabled=bool(data.get("pii_detection_enabled", True)),
			pii_entities=list(data.get("pii_entities") or []),
			model_rate_limits=dict(data.get("model_rate_limits") or {}),
			per_team_limits=dict(data.get("per_team_limits") or {}),
			updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else None,
			prompt_injection_detection_enabled=bool(data.get("prompt_injection_detection_enabled", False)),
			response_guardrails_enabled=bool(data.get("response_guardrails_enabled", False)),
			response_pii_redact=bool(data.get("response_pii_redact", False)),
			mcp_allowed_tools=list(data.get("mcp_allowed_tools") or []),
			mcp_blocked_tools=list(data.get("mcp_blocked_tools") or []),
			default_data_class=_valid_class(data.get("default_data_class"), DEFAULT_DATA_CLASS),
			data_class_map=_clean_class_map(data.get("data_class_map")),
			routing_mode=data.get("routing_mode") if data.get("routing_mode") in _ROUTING_MODES else "off",
			max_risk_rating=data.get("max_risk_rating") if data.get("max_risk_rating") in _RISK_LEVELS else "high",
			payload_capture_sample_rate=_valid_rate(data.get("payload_capture_sample_rate")),
		)

	def to_dict(self) -> dict:
		return {
			"enforcement_mode": self.enforcement_mode,
			"allowed_models": self.allowed_models,
			"blocked_keywords": self.blocked_keywords,
			"pii_detection_enabled": self.pii_detection_enabled,
			"pii_entities": self.pii_entities,
			"model_rate_limits": self.model_rate_limits,
			"per_team_limits": self.per_team_limits,
			"updated_at": self.updated_at.isoformat() if self.updated_at else None,
			"prompt_injection_detection_enabled": self.prompt_injection_detection_enabled,
			"response_guardrails_enabled": self.response_guardrails_enabled,
			"response_pii_redact": self.response_pii_redact,
			"mcp_allowed_tools": self.mcp_allowed_tools,
			"mcp_blocked_tools": self.mcp_blocked_tools,
			"default_data_class": self.default_data_class,
			"data_class_map": self.data_class_map,
			"routing_mode": self.routing_mode,
			"max_risk_rating": self.max_risk_rating,
			"payload_capture_sample_rate": self.payload_capture_sample_rate,
		}


# ── Policy store (I/O layer: Redis → DB → settings fallback) ─────────────────


class PolicyStore:
	"""Load and persist per-org policy config via Redis cache + PostgreSQL."""

	async def load(
		self,
		org_id: uuid.UUID,
		db: AsyncSession,
		redis: Redis,
	) -> PolicyConfig:
		"""Return the effective policy config for org_id.

		Resolution order:
		  1. Redis cache (TTL 60 s)
		  2. org.settings['policy'] in PostgreSQL
		  3. Global env settings (fallback)
		"""
		cache_key = _POLICY_CACHE_KEY.format(org_id=org_id)
		cached = await redis.get(cache_key)
		if cached:
			try:
				return PolicyConfig.from_dict(json.loads(cached))
			except (json.JSONDecodeError, KeyError):
				pass

		# Lazy import to avoid circular dependencies
		from app.models.organization import Organization

		try:
			org = await db.scalar(select(Organization).where(Organization.id == org_id))
			if org is not None:
				policy_data = (org.settings or {}).get("policy")
				if policy_data and isinstance(policy_data, dict):
					try:
						config = PolicyConfig.from_dict(policy_data)
					except (ValueError, TypeError, KeyError) as exc:
						# Bad JSON shape or invalid dates in org.settings.policy — don't 500 the app
						logger.warning(
							"Ignoring invalid org policy for %s: %s — using defaults",
							org_id,
							exc,
						)
						return PolicyConfig.from_settings()
					await redis.setex(cache_key, _POLICY_CACHE_TTL, json.dumps(config.to_dict()))
					return config
		except Exception as exc:
			logger.error(
				"Failed to load policy config for org %s — cannot proceed safely: %s",
				org_id, exc,
			)
			raise

		return PolicyConfig.from_settings()

	async def save(
		self,
		org_id: uuid.UUID,
		config: PolicyConfig,
		db: AsyncSession,
		redis: Redis,
	) -> None:
		"""Persist config to org.settings['policy'] and invalidate the Redis cache."""
		from app.models.organization import Organization

		org = await db.scalar(select(Organization).where(Organization.id == org_id))
		if org is None:
			return

		merged = dict(org.settings or {})
		merged["policy"] = config.to_dict()
		org.settings = merged
		await db.commit()
		await db.refresh(org)

		# Invalidate so next load re-reads from DB
		cache_key = _POLICY_CACHE_KEY.format(org_id=org_id)
		await redis.delete(cache_key)


policy_store = PolicyStore()


# ── Policy decision ───────────────────────────────────────────────────────────


# HTTP status for a request or response blocked by policy (decision D6); 403 stays for real authorization failures.
POLICY_BLOCK_STATUS = 446


@dataclass
class PolicyDecision:
	allowed: bool
	action: str = "allow"
	reason_code: str | None = None
	detail: str | None = None
	triggered_rules: list[str] | None = None
	_mode: str = "off"
	redacted_text: Optional[str] = None

	def as_metadata(self) -> dict[str, object]:
		return {
			"policy": {
				"allowed": self.allowed,
				"action": self.action,
				"reason_code": self.reason_code,
				"detail": self.detail,
				"triggered_rules": self.triggered_rules or [],
				"mode": self._mode,
			}
		}


# ── Prompt injection patterns ─────────────────────────────────────────────────

_INJECTION_PATTERNS = [
	_re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions", _re.IGNORECASE),
	_re.compile(r"you\s+are\s+now\b", _re.IGNORECASE),
	_re.compile(r"\bact\s+as\b", _re.IGNORECASE),
	_re.compile(r"\bpretend\s+(you\s+are|to\s+be)\b", _re.IGNORECASE),
	_re.compile(r"\bjailbreak\b", _re.IGNORECASE),
	_re.compile(r"\bDAN\s+mode\b", _re.IGNORECASE),
	_re.compile(r"\bdeveloper\s+mode\b", _re.IGNORECASE),
	_re.compile(r"disregard\s+your\s+(training|guidelines|rules)", _re.IGNORECASE),
]


# ── Policy service (pure — no I/O) ───────────────────────────────────────────


class PolicyService:

	async def evaluate_chat_request(
		self,
		request: ChatCompletionRequest,
		config: PolicyConfig | None = None,
	) -> PolicyDecision:
		cfg = config or PolicyConfig.from_settings()
		try:
			text = self._extract_chat_text(request)
		except PolicyScanLimitExceeded:
			mode = cfg.enforcement_mode.lower().strip()
			if mode == "off":
				return PolicyDecision(allowed=True, action="allow", _mode=mode)
			return self._decision_for_violation(
				mode=mode,
				reason_code="request_too_complex",
				detail="The request has too many fields to be checked against organization policy.",
				triggered_rules=["scan_limit"],
			)
		decision = await self._evaluate_off_loop(model=request.model, text=text, config=cfg)
		if self._skip_injection(decision, cfg):
			return decision
		injection = await self._check_injection_async(text, cfg)
		return injection if injection is not None else decision

	async def _evaluate_off_loop(self, model: str, text: str, config: PolicyConfig) -> PolicyDecision:
		"""Presidio's NLP pass takes tens of milliseconds and would stall every other request on the event loop."""
		if presidio_service.is_enabled():
			return await asyncio.to_thread(self._evaluate, model, text, config)
		return self._evaluate(model=model, text=text, config=config)

	def chat_text(self, request: ChatCompletionRequest) -> str:
		"""All the text policy and classification inspect. Raises PolicyScanLimitExceeded on an oversized request."""
		return self._extract_chat_text(request)

	@staticmethod
	def embedding_text(request: EmbeddingRequest) -> str:
		if isinstance(request.input, list):
			return "\n".join(str(item) for item in request.input)
		return str(request.input)

	def pii_entities_found(self, text: str, config: PolicyConfig) -> list[str]:
		"""Every distinct kind of PII in the text (first-seen order), for classification.

		Empty when the org turned PII detection off. Blocking uses ``_pii_hit``, which stops at the first hit;
		classification needs them all.
		"""
		if not config.pii_detection_enabled:
			return []
		found: list[str] = []
		if presidio_service.is_enabled():
			entities = config.pii_entities or settings.PRESIDIO_ENTITIES
			for result in presidio_service.analyze(text, entities=entities):
				if result.score >= settings.PRESIDIO_SCORE_THRESHOLD and result.entity_type not in found:
					found.append(result.entity_type)
			return found
		return pii_detection.entities(text)

	async def evaluate_embedding_request(
		self,
		request: EmbeddingRequest,
		config: PolicyConfig | None = None,
	) -> PolicyDecision:
		cfg = config or PolicyConfig.from_settings()
		text = self.embedding_text(request)
		decision = await self._evaluate_off_loop(model=request.model, text=text, config=cfg)
		if self._skip_injection(decision, cfg):
			return decision
		injection = await self._check_injection_async(text, cfg)
		return injection if injection is not None else decision

	@staticmethod
	def _skip_injection(decision: "PolicyDecision", config: "PolicyConfig") -> bool:
		"""Return True when the async injection check should be bypassed."""
		return (
			not decision.allowed
			or not config.prompt_injection_detection_enabled
			or config.enforcement_mode.lower().strip() == "off"
		)

	async def _check_injection_async(
		self, text: str, config: PolicyConfig
	) -> PolicyDecision | None:
		"""ML injection check; returns a decision on hit, None if safe."""
		from app.services.prompt_injection_service import injection_detector

		is_injection, score = await injection_detector.detect(text)
		if not is_injection:
			return None
		mode = config.enforcement_mode.lower().strip()
		return self._decision_for_violation(
			mode=mode,
			reason_code="prompt_injection_detected",
			detail=f"Prompt injection detected (confidence: {score:.1%})",
			triggered_rules=["prompt_injection"],
		)

	def _evaluate(self, model: str, text: str, config: PolicyConfig) -> PolicyDecision:
		mode = config.enforcement_mode.lower().strip()
		if mode == "off":
			return PolicyDecision(allowed=True, action="allow", _mode=mode)

		triggered_rules: list[str] = []

		if self._model_is_blocked(model, config):
			triggered_rules.append("model_allowlist")
			return self._decision_for_violation(
				mode=mode,
				reason_code="model_not_allowed",
				detail="The requested model is not allowed by organization policy.",
				triggered_rules=triggered_rules,
			)

		keyword_hit = self._keyword_hit(text, config)
		if keyword_hit is not None:
			triggered_rules.append("blocked_keyword")
			return self._decision_for_violation(
				mode=mode,
				reason_code="blocked_keyword",
				detail=f"Request matched blocked keyword: {keyword_hit}",
				triggered_rules=triggered_rules,
			)

		pii_match = self._pii_hit(text, config)
		if pii_match is not None:
			triggered_rules.append("pii_detection")
			return self._decision_for_violation(
				mode=mode,
				reason_code="pii_detected",
				detail=f"Potential PII detected: {pii_match}",
				triggered_rules=triggered_rules,
			)

		return PolicyDecision(allowed=True, action="allow", _mode=mode)

	def evaluate_tool_call(self, tool_name: str, arguments: dict, config: PolicyConfig) -> PolicyDecision:
		"""Policy for an MCP tool call: block/allow patterns, then keyword and PII checks on the arguments."""
		mode = config.enforcement_mode.lower().strip()
		if mode == "off":
			return PolicyDecision(allowed=True, action="allow", _mode=mode)

		if any(fnmatch.fnmatchcase(tool_name, p) for p in config.mcp_blocked_tools):
			return self._decision_for_violation(
				mode=mode, reason_code="tool_blocked",
				detail=f"Tool {tool_name} is blocked by organization policy.", triggered_rules=["mcp_blocked_tools"],
			)
		if config.mcp_allowed_tools and not any(fnmatch.fnmatchcase(tool_name, p) for p in config.mcp_allowed_tools):
			return self._decision_for_violation(
				mode=mode, reason_code="tool_not_allowed",
				detail=f"Tool {tool_name} is not on the organization's tool allowlist.", triggered_rules=["mcp_allowed_tools"],
			)

		text = json.dumps(arguments, ensure_ascii=False, sort_keys=True)
		keyword_hit = self._keyword_hit(text, config)
		if keyword_hit is not None:
			return self._decision_for_violation(
				mode=mode, reason_code="blocked_keyword",
				detail=f"Tool arguments matched blocked keyword: {keyword_hit}", triggered_rules=["blocked_keyword"],
			)
		pii_match = self._pii_hit(text, config)
		if pii_match is not None:
			return self._decision_for_violation(
				mode=mode, reason_code="pii_detected",
				detail=f"Potential PII detected in tool arguments: {pii_match}", triggered_rules=["pii_detection"],
			)
		return PolicyDecision(allowed=True, action="allow", _mode=mode)

	def taint_violation(self, tool_name: str, config: PolicyConfig) -> PolicyDecision:
		"""A conversation that handled untrusted tool output demanded a side-effect tool via tool_choice."""
		return self._decision_for_violation(
			mode=config.enforcement_mode.lower().strip(),
			reason_code="tool_taint_forced_sink",
			detail=f"Tool {tool_name} has side effects and cannot be forced after untrusted tool output.",
			triggered_rules=["tool_taint"],
		)

	def _decision_for_violation(
		self,
		mode: str,
		reason_code: str,
		detail: str,
		triggered_rules: list[str],
	) -> PolicyDecision:
		if mode == "log_only":
			return PolicyDecision(
				allowed=True,
				action="log_only",
				reason_code=reason_code,
				detail=detail,
				triggered_rules=triggered_rules,
				_mode=mode,
			)
		return PolicyDecision(
			allowed=False,
			action="block",
			reason_code=reason_code,
			detail=detail,
			triggered_rules=triggered_rules,
			_mode=mode,
		)

	def _model_is_blocked(self, model: str, config: PolicyConfig) -> bool:
		if config.routing_mode == "enforce" and model.startswith("cap:"):
			return False  # a capability request names no model yet; routing checks the allowlist on the one it picks
		allowlist = {item.strip() for item in config.allowed_models if item.strip()}
		if not allowlist:
			return False
		return model not in allowlist

	def is_model_on_allowlist(self, model: str, config: PolicyConfig) -> bool:
		"""True if there is no allowlist (empty = no model restriction) or model is listed.

		Matches :meth:`_model_is_blocked` / runtime chat policy checks (exact string match).
		"""
		return not self._model_is_blocked(model, config)

	def _keyword_hit(self, text: str, config: PolicyConfig) -> str | None:
		blocked_keywords = [kw.strip() for kw in config.blocked_keywords if kw.strip()]
		text_lc = text.lower()
		for keyword in blocked_keywords:
			if keyword.lower() in text_lc:
				return keyword
		return None

	def _pii_hit(self, text: str, config: PolicyConfig) -> str | None:
		if not config.pii_detection_enabled:
			return None
		if presidio_service.is_enabled():
			entities = config.pii_entities or settings.PRESIDIO_ENTITIES
			results = presidio_service.analyze(text, entities=entities)
			for result in results:
				if result.score >= settings.PRESIDIO_SCORE_THRESHOLD:
					return result.entity_type
			return None
		kinds = pii_detection.entities(text)
		return kinds[0] if kinds else None

	@staticmethod
	def _injection_hit(text: str) -> Optional[str]:
		for pattern in _INJECTION_PATTERNS:
			if pattern.search(text):
				return "prompt_injection"
		return None

	def _redact_pii(self, text: str, config: PolicyConfig) -> str:
		if presidio_service.is_enabled():
			entities = config.pii_entities or settings.PRESIDIO_ENTITIES
			results = presidio_service.analyze(text, entities=entities)
			# Filter by score threshold and sort by start DESC to avoid index shift
			hits = [r for r in results if r.score >= settings.PRESIDIO_SCORE_THRESHOLD]
			hits_sorted = sorted(hits, key=lambda r: r.start, reverse=True)
			redacted = text
			for hit in hits_sorted:
				redacted = redacted[:hit.start] + "[REDACTED]" + redacted[hit.end:]
			return redacted
		return pii_detection.redact(text)

	def evaluate_response(self, response_text: str, config: "PolicyConfig") -> "PolicyDecision":
		"""
		Evaluate policy on response text (after LLM completion).
		Returns PolicyDecision with allowed=True if no violation.
		If response_pii_redact=True and PII found, returns PolicyDecision with
		allowed=True but sets redacted_text on the decision.
		"""
		if not config.response_guardrails_enabled:
			return PolicyDecision(allowed=True)

		# Check blocked keywords in response
		if hasattr(config, 'blocked_keywords') and config.blocked_keywords:
			for kw in config.blocked_keywords:
				if kw.lower() in response_text.lower():
					return PolicyDecision(
						allowed=False,
						action="block",
						reason_code="response_keyword_blocked",
						detail="Blocked keyword found in response",
					)

		# Check PII in response
		pii_entity = self._pii_hit(response_text, config)
		if pii_entity:
			if config.response_pii_redact:
				redacted = self._redact_pii(response_text, config)
				decision = PolicyDecision(allowed=True)
				decision.redacted_text = redacted
				decision.reason_code = "response_pii_detected"
				return decision
			else:
				return PolicyDecision(
					allowed=False,
					action="block",
					reason_code="response_pii_detected",
					detail=f"PII detected in response: {pii_entity}",
				)

		return PolicyDecision(allowed=True)

	def _extract_chat_text(self, request: ChatCompletionRequest) -> str:
		parts: list[str] = []
		for message in request.messages:
			content = message.content
			if isinstance(content, str):
				parts.append(content)
			else:
				for item in content or []:
					if isinstance(item, str):
						parts.append(item)
					elif isinstance(item, dict):
						text_value = item.get("text")
						if isinstance(text_value, str):
							parts.append(text_value)
			# Pass-through fields (tool_calls, name, tool_call_id, ...) are forwarded upstream
			# verbatim, so every string in them is scanned, including JSON-encoded arguments.
			_collect_strings(message.model_extra, parts)
		# Request-level pass-through fields (tools, response_format, ...) and stop sequences are read
		# by the model too.
		_collect_strings(request.model_extra, parts)
		_collect_strings(request.stop, parts)
		return "\n".join(parts)


_MAX_JSON_LAYERS = 8  # JSON-inside-a-string nesting we will unwrap
_MAX_SCAN_NODES = 50_000
_UNICODE_ESCAPE = re.compile('\\\\u([0-9a-fA-F]{4})')


class PolicyScanLimitExceeded(Exception):
	"""The request is too large to scan completely; policy fails closed rather than scanning part of it."""


def _collect_strings(value: Any, out: list[str]) -> None:
	"""Append every piece of text in a nested structure that the upstream model will read.

	Walks iteratively (no recursion limit to hide behind). Covers dict keys, numbers, JSON-encoded
	strings (decoded, including strings inside strings) and unicode escapes (decoded even when the
	JSON is malformed), because a regex over the raw string misses text the model sees after
	decoding. Exhausting the node budget raises PolicyScanLimitExceeded (fail closed).
	"""
	stack: list[tuple[Any, int]] = [(value, 0)]
	visited = 0
	while stack:
		current, layer = stack.pop()
		visited += 1
		if visited > _MAX_SCAN_NODES:
			raise PolicyScanLimitExceeded("request has too many fields to scan against policy")
		if current is None or isinstance(current, bool):
			continue
		if isinstance(current, (int, float)):
			out.append(str(current))
		elif isinstance(current, str):
			out.append(current)
			unescaped = _UNICODE_ESCAPE.sub(lambda m: chr(int(m.group(1), 16)), current)
			if unescaped != current:
				out.append(unescaped)
			if layer < _MAX_JSON_LAYERS:
				try:
					stack.append((json.loads(current), layer + 1))
				except (ValueError, RecursionError):
					pass
		elif isinstance(current, dict):
			for key, item in current.items():
				stack.append((str(key), layer))
				stack.append((item, layer))
		elif isinstance(current, (list, tuple)):
			stack.extend((item, layer) for item in current)

policy_service = PolicyService()
