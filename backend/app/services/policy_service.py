"""Policy service for pre-provider request guardrails and policy metadata."""

from __future__ import annotations

import fnmatch
import json
import re
import re as _re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.schemas.chat import ChatCompletionRequest, EmbeddingRequest
from app.utils.logging import get_logger
from app.services import presidio_service

logger = get_logger(__name__)

# ── Redis key helpers ────────────────────────────────────────────────────────

_POLICY_CACHE_TTL = 60  # seconds
_POLICY_CACHE_KEY = "policy:config:{org_id}"


# ── Policy config (per-org, loaded from DB / Redis) ──────────────────────────


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
	_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
	_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
	_CC_RE = re.compile(r"\b(?:\d[ -]*?){13,19}\b")

	async def evaluate_chat_request(
		self,
		request: ChatCompletionRequest,
		config: PolicyConfig | None = None,
	) -> PolicyDecision:
		cfg = config or PolicyConfig.from_settings()
		text = self._extract_chat_text(request)
		decision = self._evaluate(model=request.model, text=text, config=cfg)
		if self._skip_injection(decision, cfg):
			return decision
		injection = await self._check_injection_async(text, cfg)
		return injection if injection is not None else decision

	async def evaluate_embedding_request(
		self,
		request: EmbeddingRequest,
		config: PolicyConfig | None = None,
	) -> PolicyDecision:
		cfg = config or PolicyConfig.from_settings()
		if isinstance(request.input, list):
			text = "\n".join(str(item) for item in request.input)
		else:
			text = str(request.input)
		decision = self._evaluate(model=request.model, text=text, config=cfg)
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
		# Fallback: regex-based detection
		if self._EMAIL_RE.search(text):
			return "email"
		if self._SSN_RE.search(text):
			return "ssn"
		if self._CC_RE.search(text):
			return "payment_card"
		return None

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
		# Fallback: regex substitutions
		redacted = self._EMAIL_RE.sub("[REDACTED]", text)
		redacted = self._SSN_RE.sub("[REDACTED]", redacted)
		redacted = self._CC_RE.sub("[REDACTED]", redacted)
		return redacted

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
				continue
			for item in content:
				if isinstance(item, str):
					parts.append(item)
				elif isinstance(item, dict):
					text_value = item.get("text")
					if isinstance(text_value, str):
						parts.append(text_value)
		return "\n".join(parts)


policy_service = PolicyService()
