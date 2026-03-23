"""LiteLLM wrapper — acompletion, cost calculation, streaming with capture."""

import asyncio
import fnmatch
import json
import random
import time
import uuid
from collections.abc import AsyncGenerator, Callable, Coroutine
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import litellm
from fastapi import BackgroundTasks, HTTPException, Request, status
from fastapi.responses import JSONResponse, StreamingResponse
from litellm import acompletion, aembedding
from redis.asyncio import Redis
from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.api_key import ApiKey
from app.models.experiment import Experiment
from app.models.llm_provider_key import LLMProviderKey
from app.models.prompt_template import PromptTemplate
from app.models.organization import Organization
from app.models.team import Team, team_members
from app.models.user import User
from app.schemas.chat import ChatCompletionRequest, EmbeddingRequest, Message, _substitute_variables
from app.services import cache_service
from app.services.cache_service import CacheOverride
from app.services.audit_logger import log_request
from app.services.cost_tracker import cost_tracker_service
from app.services.circuit_breaker_service import (
	is_circuit_open,
	record_failure as circuit_record_failure,
	record_success as circuit_record_success,
)
from app.services.adaptive_sampling_service import get_error_rate, get_latency_p99
from app.services.crypto_service import decrypt
from app.services.eval_service import _extract_prompt_text, run_eval_hook
from app.services.policy_service import PolicyDecision, policy_service, policy_store
from app.services.rate_limiter import rate_limiter_service
from app.utils.logging import get_logger
from app.utils.token_estimator import estimate_tokens

logger = get_logger(__name__)


def _provider_error_public_detail(exc: Exception) -> str:
	"""Avoid leaking internals in production; full message when DEBUG."""
	return str(exc) if settings.DEBUG else "Upstream provider error"


_RETRYABLE_STATUS_CODES: frozenset[int] = frozenset({429, 500, 502, 503, 504})

# (key_id, decrypted_key) — key_id is None for env-provided keys
ProviderKeyCandidate = tuple[uuid.UUID | None, str]


def _is_retryable(exc: Exception) -> bool:
	"""Return True if the exception represents a transient provider error (ADR-9)."""
	status_code = getattr(exc, "status_code", None)
	return isinstance(status_code, int) and status_code in _RETRYABLE_STATUS_CODES


def _split_model(model_name: str) -> tuple[str, str]:
	if "/" not in model_name:
		raise HTTPException(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail={"error": "invalid_model", "detail": "Model not supported"},
		)
	provider, model = model_name.split("/", 1)
	if not provider or not model:
		raise HTTPException(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail={"error": "invalid_model", "detail": "Model not supported"},
		)
	return provider, model


def _to_jsonable(value: Any) -> Any:
	if hasattr(value, "model_dump"):
		return value.model_dump(exclude_none=True)
	if hasattr(value, "dict"):
		return value.dict()
	if isinstance(value, (dict, list, str, int, float, bool)) or value is None:
		return value
	return json.loads(json.dumps(value, default=str))


def _parse_team_id(request: Request) -> uuid.UUID | None:
	"""Parse and validate the x-openproxy-team-id header.

	Returns None when the header is absent.
	Raises HTTP 400 on invalid UUID format.
	"""
	raw = request.headers.get("x-openproxy-team-id")
	if not raw or not raw.strip():
		return None
	try:
		return uuid.UUID(raw.strip())
	except (ValueError, TypeError):
		raise HTTPException(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail="x-openproxy-team-id must be a valid UUID",
		)


def _parse_labels(request: Request) -> dict[str, str] | None:
	"""Parse and validate the x-openproxy-labels header.

	Returns None when the header is absent.
	Raises HTTP 400 on any validation failure — never silently swallows bad input.
	"""
	raw = request.headers.get("x-openproxy-labels")
	if not raw:
		return None
	try:
		labels = json.loads(raw)
	except (json.JSONDecodeError, ValueError):
		raise HTTPException(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail="x-openproxy-labels must be valid JSON",
		)
	if not isinstance(labels, dict):
		raise HTTPException(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail="x-openproxy-labels must be a JSON object",
		)
	if len(labels) > 10:
		raise HTTPException(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail="x-openproxy-labels: maximum 10 keys",
		)
	for k, v in labels.items():
		if not isinstance(k, str) or not isinstance(v, str):
			raise HTTPException(
				status_code=status.HTTP_400_BAD_REQUEST,
				detail="x-openproxy-labels: keys and values must be strings",
			)
		if len(k) > 64 or len(v) > 64:
			raise HTTPException(
				status_code=status.HTTP_400_BAD_REQUEST,
				detail="x-openproxy-labels: keys and values must be \u226464 chars",
			)
	return labels


async def _resolve_prompt_template(
	db: AsyncSession,
	org_id: uuid.UUID,
	prompt_id: uuid.UUID,
	variables: dict[str, str],
) -> list[Message]:
	"""Load PromptTemplate, substitute variables, return [system?, user] messages."""
	vars_str = {k: str(v) for k, v in (variables or {}).items()}
	result = await db.execute(
		select(PromptTemplate).where(
			PromptTemplate.id == prompt_id,
			PromptTemplate.org_id == org_id,
			PromptTemplate.is_active.is_(True),
		)
	)
	tpl = result.scalar_one_or_none()
	if tpl is None:
		raise HTTPException(
			status_code=status.HTTP_404_NOT_FOUND,
			detail={"error": "prompt_not_found", "prompt_id": str(prompt_id)},
		)
	messages: list[Message] = []
	if tpl.system_message:
		messages.append(
			Message(role="system", content=_substitute_variables(tpl.system_message, vars_str))
		)
	messages.append(
		Message(role="user", content=_substitute_variables(tpl.user_template, vars_str))
	)
	return messages


# ---------------------------------------------------------------------------
# Shared request context for the decomposed chat_completion pipeline
# ---------------------------------------------------------------------------


def _parse_cache_override(request: Request | None) -> CacheOverride | None:
	"""Parse x-openproxy-cache header: skip | no-store | no-cache."""
	if request is None:
		return None
	raw = request.headers.get("x-openproxy-cache")
	if not raw:
		return None
	v = raw.strip().lower()
	if v in ("skip", "no-store", "no-cache"):
		return v  # type: ignore[return-value]
	return None


def _parse_retries_header(request: Request | None) -> int | None:
	"""Parse x-openproxy-retries header (0–5). Per-request override for max fallback attempts."""
	if request is None:
		return None
	raw = request.headers.get("x-openproxy-retries")
	if not raw or not raw.strip():
		return None
	try:
		val = int(raw.strip())
		if 0 <= val <= 5:
			return val
	except (ValueError, TypeError):
		pass
	return None


def _parse_fallback_model_header(request: Request | None) -> str | None:
	"""Parse x-openproxy-fallback-model header (provider/model). Used when primary fails."""
	if request is None:
		return None
	raw = request.headers.get("x-openproxy-fallback-model")
	if not raw or not raw.strip():
		return None
	s = raw.strip()
	if "/" in s and len(s) < 80:
		return s
	return None


def _parse_session_id_header(request: Request | None) -> str | None:
	"""Parse x-openproxy-session-id header. UUID or opaque string, max 64 chars."""
	if request is None:
		return None
	raw = request.headers.get("x-openproxy-session-id")
	if not raw or not raw.strip():
		return None
	s = raw.strip()
	if len(s) > 64:
		return None
	try:
		uuid.UUID(s)
		return s
	except (ValueError, TypeError):
		pass
	if s and not any(c in s for c in "\r\n\t"):
		return s
	return None


@dataclass
class _RequestContext:
	request: ChatCompletionRequest
	user: User
	api_key: ApiKey
	request_id: uuid.UUID
	background_tasks: BackgroundTasks
	redis: Redis
	labels: dict[str, str] | None
	start: float
	http_request: Request | None = None
	provider: str = "unknown"
	model_name: str = ""
	rl_headers: dict[str, str] = field(default_factory=dict)
	policy_metadata: dict | None = None
	policy_config: Any = None
	candidate_keys: list[ProviderKeyCandidate] = field(default_factory=list)
	kwargs: dict[str, Any] = field(default_factory=dict)
	team_id: uuid.UUID | None = None
	team_budget_monthly_usd: Decimal | None = None
	experiment_info: dict | None = None
	max_fallback_attempts: int | None = None  # x-openproxy-retries override
	fallback_model: str | None = None  # x-openproxy-fallback-model override
	session_id: str | None = None  # x-openproxy-session-id for trace grouping


def _build_request_metadata(ctx: _RequestContext, extra: dict | None = None) -> dict:
	"""Build request_metadata for logging, merging policy_metadata, experiment_info, session_id."""
	metadata = {**(ctx.policy_metadata or {})}
	if ctx.experiment_info:
		metadata = {**metadata, "experiment": ctx.experiment_info}
	if ctx.session_id:
		metadata = {**metadata, "session_id": ctx.session_id}
	if extra:
		metadata = {**metadata, **extra}
	return metadata


class LLMService:
	async def _select_provider_keys(
		self,
		db: AsyncSession,
		org_id: uuid.UUID,
		provider: str,
		model: str | None = None,
		redis: Redis | None = None,
		max_attempts: int | None = None,
	) -> list[ProviderKeyCandidate]:
		"""Return ordered list of (key_id, decrypted_key) tuples: [primary, fallback1, ...].

		key_id is None for env-provided keys. Strategy: simple_shuffle (weighted random),
		round_robin, or lowest_latency. Fallbacks sorted by weight descending.
		Total list capped at max_attempts+1. Only keys matching data_region or 'global' eligible.
		"""
		limit = (max_attempts + 1) if max_attempts is not None else (settings.MAX_PROVIDER_FALLBACK_ATTEMPTS + 1)
		org = await db.get(Organization, org_id)
		data_region = (org.data_region or "us").strip().lower() if org else "us"
		org_settings = (getattr(org, "settings", None) or {}) if org else {}
		strategy = org_settings.get("router", {}).get("strategy") or getattr(
			settings, "ROUTER_STRATEGY", "simple_shuffle"
		)

		conditions = [
			LLMProviderKey.org_id == org_id,
			LLMProviderKey.provider == provider,
			LLMProviderKey.is_active.is_(True),
			or_(
				LLMProviderKey.region == data_region,
				LLMProviderKey.region == "global",
			),
		]
		if settings.PROVIDER_HEALTH_CHECK_ENABLED:
			conditions.append(LLMProviderKey.health_status != "unhealthy")
		rows = await db.scalars(select(LLMProviderKey).where(*conditions))
		keys = [row for row in rows if row.weight > 0]
		# Filter out keys with open circuit (CIRCUIT_BREAKER_ENABLED)
		if keys and redis and getattr(settings, "CIRCUIT_BREAKER_ENABLED", False):
			eligible = []
			for k in keys:
				if not await is_circuit_open(redis, k.id):
					eligible.append(k)
			keys = eligible
			if not keys:
				raise HTTPException(
					status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
					detail={
						"error": "no_provider_key",
						"detail": "All provider keys have open circuit breakers. Retry after cooldown.",
						"retry_after": getattr(settings, "CIRCUIT_BREAKER_COOLDOWN_SECONDS", 60),
					},
					headers={"Retry-After": str(getattr(settings, "CIRCUIT_BREAKER_COOLDOWN_SECONDS", 60))},
				)
		if keys:
			if model:
				matched = [
					k for k in keys
					if k.model_patterns
					and any(fnmatch.fnmatch(model, pattern) for pattern in k.model_patterns)
				]
				candidates = matched if matched else keys
			else:
				candidates = keys
			# Effective weights: when adaptive LB enabled, penalize high latency/error
			weights_list = [k.weight for k in candidates]
			if (
				redis
				and getattr(settings, "ADAPTIVE_LB_ENABLED", False)
				and getattr(settings, "ADAPTIVE_LB_WEIGHT_FLOOR", 0.1)
			):
				floor = float(settings.ADAPTIVE_LB_WEIGHT_FLOOR)
				weights_list = []
				for k in candidates:
					p99 = await get_latency_p99(redis, k.id)
					err = await get_error_rate(redis, k.id)
					if p99 is None and err is None:
						health = 1.0
					else:
						lat_penalty = (p99 or 0) / 10000
						err_penalty = (err or 0) * 10
						health = 1.0 / (1.0 + lat_penalty + err_penalty)
					effective = max(floor, health) * k.weight
					weights_list.append(max(1, int(effective)) if effective >= 1 else 1)
			primary = None
			if strategy == "round_robin" and redis and len(candidates) > 0:
				rr_key = f"rl:rr:{org_id}:{provider}"
				idx = await redis.incr(rr_key)
				await redis.expire(rr_key, 86400)
				primary = candidates[int(idx) % len(candidates)]
			elif strategy == "lowest_latency":
				primary = random.choices(candidates, weights=weights_list, k=1)[0]
			if primary is None:
				primary = random.choices(candidates, weights=weights_list, k=1)[0]
			# Fallbacks by effective weight (desc)
			weights_by_key = dict(zip(candidates, weights_list))
			fallbacks = sorted(
				[k for k in candidates if k is not primary],
				key=lambda k: weights_by_key.get(k, k.weight),
				reverse=True,
			)
			ordered = [primary, *fallbacks][: limit]
			return [(k.id, decrypt(k.api_key_encrypted)) for k in ordered]

		env_map = {
			"openai": settings.OPENAI_API_KEY,
			"anthropic": settings.ANTHROPIC_API_KEY,
			"azure": settings.AZURE_API_KEY,
		}
		api_key = env_map.get(provider, "")
		if api_key:
			return [(None, api_key)]

		raise HTTPException(
			status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
			detail={
				"error": "no_provider_key",
				"detail": f"No provider keys available for region '{data_region}'. Add provider keys tagged with region '{data_region}' or 'global'.",
			},
		)

	async def _resolve_experiment(
		self,
		db: AsyncSession,
		org_id: uuid.UUID,
		requested_model: str,
	) -> tuple[str, dict | None]:
		"""Resolve A/B experiment: if active experiment exists for requested_model, pick variant by weight.

		Returns (resolved_model, experiment_info) where experiment_info is
		{"experiment_id": str, "variant_model": str, "original_model": str} or None.
		"""
		from app.database import set_session_org_id

		await set_session_org_id(db, org_id)
		experiment = await db.scalar(
			select(Experiment)
			.where(
				Experiment.org_id == org_id,
				Experiment.target_model == requested_model,
				Experiment.is_active.is_(True),
			)
			.options(selectinload(Experiment.variants))
			.limit(1)
		)
		if experiment is None or not experiment.variants:
			return requested_model, None

		weights = [v.traffic_weight for v in experiment.variants]
		if sum(weights) <= 0:
			return requested_model, None

		variant = random.choices(experiment.variants, weights=weights, k=1)[0]
		experiment_info = {
			"experiment_id": str(experiment.id),
			"variant_id": str(variant.id),
			"variant_model": variant.model,
			"original_model": requested_model,
		}
		return variant.model, experiment_info

	@staticmethod
	def _schedule_log(
		background_tasks: BackgroundTasks,
		redis: Redis,
		request_id: uuid.UUID,
		user: User,
		api_key: ApiKey,
		model: str,
		provider: str,
		prompt_tokens: int,
		completion_tokens: int,
		cost_usd: Decimal,
		latency_ms: int,
		status_code: int,
		ttft_ms: int | None = None,
		error_message: str | None = None,
		request_metadata: dict | None = None,
		labels: dict[str, str] | None = None,
		team_id: uuid.UUID | None = None,
		provider_key_id: uuid.UUID | None = None,
	) -> None:
		background_tasks.add_task(
			log_request,
			redis=redis,
			request_id=request_id,
			org_id=user.org_id,
			user_id=user.id,
			api_key_id=api_key.id,
			provider_key_id=provider_key_id,
			model=model,
			provider=provider,
			prompt_tokens=prompt_tokens,
			completion_tokens=completion_tokens,
			cost_usd=cost_usd,
			latency_ms=latency_ms,
			ttft_ms=ttft_ms,
			status_code=status_code,
			error_message=error_message,
			request_metadata=request_metadata,
			labels=labels,
			team_id=team_id,
		)

	@staticmethod
	def _policy_block_response(decision: PolicyDecision) -> JSONResponse:
		return JSONResponse(
			status_code=403,
			content={
				"error": "policy_violation",
				"detail": decision.detail or "Request blocked by policy.",
				"reason_code": decision.reason_code,
				"triggered_rules": decision.triggered_rules or [],
			},
			headers={
				"X-OpenProxyAI-Gateway-Error": "true",
				"X-OpenProxyAI-Policy-Action": decision.action,
				"X-OpenProxyAI-Policy-Reason": decision.reason_code or "unknown",
			},
		)

	# ------------------------------------------------------------------
	# Decomposed pipeline steps for chat_completion
	# ------------------------------------------------------------------

	async def _build_litellm_kwargs(
		self,
		ctx: _RequestContext,
		db: AsyncSession,
	) -> JSONResponse | None:
		"""Policy eval, rate limit, key selection, kwargs build.

		Returns a JSONResponse when the request should be short-circuited
		(policy block or rate limit), otherwise None.
		"""
		ctx.provider, ctx.model_name = _split_model(ctx.request.model)
		resolved_model, experiment_info = await self._resolve_experiment(
			db, ctx.user.org_id, ctx.request.model
		)
		if experiment_info:
			ctx.request = ctx.request.model_copy(update={"model": resolved_model})
			ctx.provider, ctx.model_name = _split_model(resolved_model)
			ctx.experiment_info = experiment_info

		ctx.policy_config = await policy_store.load(ctx.user.org_id, db, ctx.redis)
		decision = await policy_service.evaluate_chat_request(ctx.request, ctx.policy_config)
		ctx.policy_metadata = decision.as_metadata()

		# Validate x-openproxy-fallback-model against policy allowlist when present
		if ctx.fallback_model and ctx.policy_config.allowed_models:
			allowlist = {m.strip() for m in ctx.policy_config.allowed_models if m.strip()}
			if allowlist and ctx.fallback_model not in allowlist:
				ctx.fallback_model = None  # Ignore header if model not allowed

		# Resolve team context from x-openproxy-team-id (optional)
		if ctx.team_id is not None:
			team = await db.scalar(
				select(Team).where(
					Team.id == ctx.team_id,
					Team.org_id == ctx.user.org_id,
				)
			)
			if team is None:
				raise HTTPException(
					status_code=status.HTTP_404_NOT_FOUND,
					detail="Team not found",
				)
			member_row = await db.execute(
				select(team_members).where(
					team_members.c.team_id == ctx.team_id,
					team_members.c.user_id == ctx.user.id,
				)
			)
			if member_row.first() is None:
				raise HTTPException(
					status_code=status.HTTP_403_FORBIDDEN,
					detail="User is not a member of this team",
				)
			ctx.team_budget_monthly_usd = team.budget_monthly_usd

		if not decision.allowed:
			latency_ms = int((time.perf_counter() - ctx.start) * 1000)
			await log_request(
				redis=ctx.redis,
				request_id=ctx.request_id,
				org_id=ctx.user.org_id,
				user_id=ctx.user.id,
				api_key_id=ctx.api_key.id,
				model=ctx.request.model,
				provider=ctx.provider,
				prompt_tokens=0,
				completion_tokens=0,
				cost_usd=Decimal("0"),
				latency_ms=latency_ms,
				ttft_ms=None,
				status_code=403,
				error_message=f"policy_blocked:{decision.reason_code}",
				request_metadata=_build_request_metadata(ctx),
				labels=ctx.labels,
				team_id=ctx.team_id,
			)
			return self._policy_block_response(decision)

		ok, ctx.rl_headers, limit_type, limit_detail, retry_after = (
			await rate_limiter_service.check_limits(
				redis=ctx.redis,
				org_id=str(ctx.user.org_id),
				user_id=str(ctx.user.id),
				request_tokens_estimate=estimate_tokens(ctx.request),
				max_rpm=settings.DEFAULT_RATE_LIMIT_RPM,
				max_tpm=settings.DEFAULT_RATE_LIMIT_TPM,
				max_daily_budget_usd=Decimal(str(settings.DEFAULT_BUDGET_DAILY_USD)),
				user_daily_budget_usd=getattr(ctx.user, "budget_daily_usd", None),
				team_id=str(ctx.team_id) if ctx.team_id else None,
				team_budget_monthly_usd=ctx.team_budget_monthly_usd,
				model=ctx.request.model,
				policy_config=ctx.policy_config,
			)
		)
		if not ok:
			latency_ms = int((time.perf_counter() - ctx.start) * 1000)
			await log_request(
				redis=ctx.redis,
				request_id=ctx.request_id,
				org_id=ctx.user.org_id,
				user_id=ctx.user.id,
				api_key_id=ctx.api_key.id,
				model=ctx.request.model,
				provider=ctx.provider,
				prompt_tokens=0,
				completion_tokens=0,
				cost_usd=Decimal("0"),
				latency_ms=latency_ms,
				ttft_ms=None,
				status_code=429,
				error_message=f"rate_limited:{limit_type}",
				request_metadata=_build_request_metadata(ctx),
				labels=ctx.labels,
				team_id=ctx.team_id,
			)
			return JSONResponse(
				status_code=429,
				content={
					"error": "rate_limit_exceeded",
					"limit_type": limit_type,
					"detail": limit_detail,
					"retry_after": retry_after,
				},
				headers={**ctx.rl_headers, "X-OpenProxyAI-Gateway-Error": "true"},
			)

		try:
			ctx.candidate_keys = await self._select_provider_keys(
				db, ctx.user.org_id, ctx.provider, model=ctx.model_name, redis=ctx.redis,
				max_attempts=ctx.max_fallback_attempts,
			)
		except HTTPException as exc:
			raise HTTPException(
				status_code=exc.status_code,
				detail=exc.detail,
				headers={**ctx.rl_headers, **(exc.headers or {})},
			) from exc

		ctx.kwargs = ctx.request.model_dump(exclude_none=True)
		ctx.kwargs.update({"model": ctx.request.model, "timeout": 30, "request_timeout": 30})
		return None

	@staticmethod
	async def _execute_with_fallback(
		candidates: list[ProviderKeyCandidate],
		call_fn: Callable[[str], Coroutine[Any, Any, Any]],
		model_label: str,
		tag: str = "",
		redis: Redis | None = None,
	) -> tuple[Any, int, uuid.UUID | None]:
		"""Iterate candidate keys, calling *call_fn(api_key)* for each.

		Returns (response, fallback_count, winning_key_id). winning_key_id is None for env keys.
		Retryable exceptions cause fallback to the next key; non-retryable propagate.
		When circuit breaker enabled, records failures/success per key.
		"""
		if not candidates:
			raise HTTPException(
				status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
				detail={"error": "no_provider_key", "detail": "No provider keys available"},
			)
		response = None
		last_exc: Exception | None = None
		fallback_count = 0
		winning_key_id: uuid.UUID | None = None
		for idx, (key_id, api_key) in enumerate(candidates):
			if idx > 0:
				fallback_count += 1
				logger.warning("provider fallback%s attempt=%d model=%s", tag, idx + 1, model_label)
			try:
				response = await call_fn(api_key)
				winning_key_id = key_id
				await circuit_record_success(redis, key_id)
				break
			except HTTPException:
				raise
			except Exception as exc:
				if _is_retryable(exc):
					await circuit_record_failure(redis, key_id)
					if idx < len(candidates) - 1:
						last_exc = exc
						continue
				raise
		if response is None:
			raise last_exc  # type: ignore[misc]
		return response, fallback_count, winning_key_id

	async def _handle_streaming_response(
		self, ctx: _RequestContext, db: AsyncSession
	) -> StreamingResponse:
		"""Budget pre-flight, streaming fallback, event_stream generator."""
		# Best-effort budget pre-flight — never blocks on estimation failure
		try:
			messages_list = [
				m.model_dump() if hasattr(m, "model_dump") else m
				for m in ctx.request.messages
			]
			estimated_prompt = litellm.token_counter(model=ctx.request.model, messages=messages_list)
			max_completion = getattr(ctx.request, "max_tokens", None) or 4096
			estimated_cost = litellm.completion_cost(
				model=ctx.request.model,
				prompt_tokens=estimated_prompt,
				completion_tokens=max_completion,
			)
			today = datetime.now(timezone.utc).date().isoformat()
			org_spend_raw = await ctx.redis.get(f"rl:usd:{ctx.user.org_id}:{today}")
			org_spend = Decimal(str(
				org_spend_raw.decode() if isinstance(org_spend_raw, bytes) else (org_spend_raw or "0")
			))
			org_remaining = max(Decimal(str(settings.DEFAULT_BUDGET_DAILY_USD)) - org_spend, Decimal("0"))

			remaining_budget = org_remaining
			user_budget = getattr(ctx.user, "budget_daily_usd", None)
			if user_budget is not None:
				user_spend_raw = await ctx.redis.get(f"rl:usd:user:{ctx.user.id}:{today}")
				user_spend = Decimal(str(
					user_spend_raw.decode() if isinstance(user_spend_raw, bytes) else (user_spend_raw or "0")
				))
				user_remaining = max(Decimal(str(user_budget)) - user_spend, Decimal("0"))
				remaining_budget = min(org_remaining, user_remaining)
			if Decimal(str(estimated_cost)) > remaining_budget:
				raise HTTPException(
					status_code=402,
					detail={"error": "budget_exceeded", "detail": "Estimated request cost exceeds remaining daily budget"},
				)
		except HTTPException:
			raise
		except Exception as exc:
			logger.warning("Budget pre-flight failed (continuing): %s", exc)

		ctx.kwargs["stream"] = True

		async def _stream_call(key: str) -> tuple[Any, Any]:
			call_kwargs = {**ctx.kwargs, "api_key": key}
			stream = await acompletion(**call_kwargs)
			first = await stream.__anext__()
			if getattr(first, "error", None) is not None:
				raise HTTPException(
					status_code=502,
					detail={"error": "provider_error", "detail": str(first.error)},
				)
			return stream, first

		stream, first_chunk, fb_count, provider_key_id = None, None, 0, None
		try:
			(stream, first_chunk), fb_count, provider_key_id = await self._execute_with_fallback(
				ctx.candidate_keys, _stream_call, ctx.request.model, tag=" (stream)", redis=ctx.redis,
			)
		except Exception as exc:
			# Retry with x-openproxy-fallback-model when primary keys all fail
			if _is_retryable(exc) and ctx.fallback_model and not getattr(ctx, "_used_fallback_model", False):
				ctx._used_fallback_model = True
				fb_provider, fb_model_name = _split_model(ctx.fallback_model)
				ctx.request = ctx.request.model_copy(update={"model": ctx.fallback_model})
				ctx.provider, ctx.model_name = fb_provider, fb_model_name
				ctx.candidate_keys = await self._select_provider_keys(
					db, ctx.user.org_id, ctx.provider, model=fb_model_name,
					redis=ctx.redis, max_attempts=ctx.max_fallback_attempts,
				)
				ctx.kwargs = ctx.request.model_dump(exclude_none=True)
				ctx.kwargs.update({"model": ctx.fallback_model, "timeout": 30, "request_timeout": 30, "stream": True})
				(stream, first_chunk), fb_count, provider_key_id = await self._execute_with_fallback(
					ctx.candidate_keys, _stream_call, ctx.fallback_model, tag=" (stream+fallback-model)", redis=ctx.redis,
				)
				ctx.policy_metadata = {
					**(ctx.policy_metadata or {}),
					"fallback_model_used": ctx.fallback_model,
				}
			else:
				raise

		if fb_count > 0:
			ctx.policy_metadata = {**(ctx.policy_metadata or {}), "fallback_count": fb_count}

		ttft_ms = int((time.perf_counter() - ctx.start) * 1000)
		prompt_tokens = 0
		completion_tokens = 0

		def _update_usage(chunk_body: dict[str, Any]) -> None:
			nonlocal prompt_tokens, completion_tokens
			usage = chunk_body.get("usage", {})
			if not isinstance(usage, dict):
				return
			prompt_tokens = max(prompt_tokens, int(usage.get("prompt_tokens", 0) or 0))
			completion_tokens = max(completion_tokens, int(usage.get("completion_tokens", 0) or 0))

		async def event_stream() -> AsyncGenerator[str, None]:
			first_payload = _to_jsonable(first_chunk)
			if isinstance(first_payload, dict):
				_update_usage(first_payload)
			yield f"data: {json.dumps(first_payload)}\n\n"
			collected_chunks: list[str] = []
			async for chunk in stream:
				chunk_payload = _to_jsonable(chunk)
				if isinstance(chunk_payload, dict):
					_update_usage(chunk_payload)
					for choice in chunk_payload.get("choices", []):
						delta = choice.get("delta", {})
						content = delta.get("content")
						if content:
							collected_chunks.append(content)
				yield f"data: {json.dumps(chunk_payload)}\n\n"
			yield "data: [DONE]\n\n"
			if (
				hasattr(ctx.policy_config, "response_guardrails_enabled")
				and ctx.policy_config.response_guardrails_enabled
			):
				try:
					from app.services.policy_service import PolicyService
					policy_svc = PolicyService()
					full_response_text = "".join(collected_chunks)
					decision_resp = policy_svc.evaluate_response(full_response_text, ctx.policy_config)
					if not decision_resp.allowed:
						logger.warning(
							"Response guardrail violation (stream already delivered): request_id=%s reason=%s",
							ctx.request_id, decision_resp.reason_code,
						)
				except Exception as exc:
					logger.error("Response guardrail check failed for request %s: %s", ctx.request_id, exc)
			latency_ms = int((time.perf_counter() - ctx.start) * 1000)
			cost = Decimal("0")
			if prompt_tokens > 0 or completion_tokens > 0:
				cost = cost_tracker_service.calculate_cost_usd({
					"model": ctx.request.model,
					"usage": {
						"prompt_tokens": prompt_tokens,
						"completion_tokens": completion_tokens,
						"total_tokens": prompt_tokens + completion_tokens,
					},
				})
			self._schedule_log(
				ctx.background_tasks, ctx.redis, ctx.request_id, ctx.user, ctx.api_key,
				ctx.request.model, ctx.provider, prompt_tokens, completion_tokens, cost,
				latency_ms, 200, ttft_ms=ttft_ms, request_metadata=_build_request_metadata(ctx), labels=ctx.labels,
				team_id=ctx.team_id, provider_key_id=provider_key_id,
			)
			if ctx.experiment_info and (settings.EVAL_HOOK_URL or settings.EVAL_LLM_MODEL):
				full_response_text = "".join(collected_chunks)
				prompt_text = _extract_prompt_text(ctx.request.messages)
				exp_id = ctx.experiment_info.get("experiment_id")
				var_id = ctx.experiment_info.get("variant_id")
				ctx.background_tasks.add_task(
					run_eval_hook,
					ctx.request_id,
					ctx.user.org_id,
					uuid.UUID(exp_id) if exp_id else None,
					uuid.UUID(var_id) if var_id else None,
					prompt_text,
					full_response_text,
				)

		return StreamingResponse(
			event_stream(),
			media_type="text/event-stream",
			headers={
				"X-OpenProxyAI-Request-Id": str(ctx.request_id),
				"X-OpenProxyAI-Provider": ctx.provider,
				"X-OpenProxyAI-Model": ctx.request.model,
				"X-OpenProxyAI-Cost-USD": "0.000000",
				"X-OpenProxyAI-TTFT-Ms": str(ttft_ms),
				"X-OpenProxyAI-Gateway-Error": "false",
				**ctx.rl_headers,
			},
		)

	async def _handle_non_streaming_response(
		self,
		ctx: _RequestContext,
		db: AsyncSession,
	) -> JSONResponse:
		"""Cache check, fallback call, response guardrail, cost/log, return."""
		cache_override = _parse_cache_override(ctx.http_request)
		# Cache check — failure must never block a real LLM call
		try:
			cache_messages = [
				m.model_dump() if hasattr(m, "model_dump") else m
				for m in ctx.request.messages
			]
			cache_temperature = getattr(ctx.request, "temperature", None)
			cached_body, cache_tier = await cache_service.get(
				ctx.redis,
				ctx.request.model,
				cache_messages,
				cache_temperature,
				org_id=ctx.user.org_id,
				db=db,
				cache_override=cache_override,
			)
			if cached_body is not None and cache_tier:
				cached_usage = cached_body.get("usage", {}) if isinstance(cached_body, dict) else {}
				cached_prompt = int(cached_usage.get("prompt_tokens", 0))
				cached_completion = int(cached_usage.get("completion_tokens", 0))
				cached_cost = cost_tracker_service.calculate_cost_usd(cached_body)
				cached_latency = int((time.perf_counter() - ctx.start) * 1000)
				request_metadata = _build_request_metadata(ctx, {"cache": cache_tier})
				self._schedule_log(
					ctx.background_tasks, ctx.redis, ctx.request_id, ctx.user, ctx.api_key,
					ctx.request.model, ctx.provider, cached_prompt, cached_completion, cached_cost,
					cached_latency, 200, request_metadata=request_metadata, labels=ctx.labels,
					team_id=ctx.team_id,
				)
				if ctx.experiment_info and (settings.EVAL_HOOK_URL or settings.EVAL_LLM_MODEL):
					cached_content = ""
					if isinstance(cached_body, dict):
						for c in cached_body.get("choices", []) or []:
							msg = c.get("message", {})
							if isinstance(msg, dict) and msg.get("content"):
								cached_content = msg["content"]
								break
					prompt_text = _extract_prompt_text(ctx.request.messages)
					exp_id = ctx.experiment_info.get("experiment_id")
					var_id = ctx.experiment_info.get("variant_id")
					ctx.background_tasks.add_task(
						run_eval_hook,
						ctx.request_id,
						ctx.user.org_id,
						uuid.UUID(exp_id) if exp_id else None,
						uuid.UUID(var_id) if var_id else None,
						prompt_text,
						cached_content,
					)
				return JSONResponse(
					content=cached_body,
					headers={
						"X-OpenProxyAI-Request-Id": str(ctx.request_id),
						"X-OpenProxyAI-Provider": ctx.provider,
						"X-OpenProxyAI-Model": ctx.request.model,
						"X-OpenProxyAI-Cost-USD": f"{cached_cost:.6f}",
						"X-OpenProxyAI-Latency-Ms": str(cached_latency),
						"X-OpenProxyAI-Cache": cache_tier,
						"X-OpenProxyAI-Gateway-Error": "false",
					**ctx.rl_headers,
				},
			)
		except Exception as exc:
			logger.warning("Cache check failed (continuing): %s", exc)

		async def _call(key: str) -> Any:
			call_kwargs = {**ctx.kwargs, "api_key": key}
			return await acompletion(**call_kwargs)

		response, fb_count, provider_key_id = None, 0, None
		try:
			response, fb_count, provider_key_id = await self._execute_with_fallback(
				ctx.candidate_keys, _call, ctx.request.model, redis=ctx.redis,
			)
		except Exception as exc:
			# Retry with x-openproxy-fallback-model when primary keys all fail
			if _is_retryable(exc) and ctx.fallback_model and not getattr(ctx, "_used_fallback_model", False):
				ctx._used_fallback_model = True
				fb_provider, fb_model_name = _split_model(ctx.fallback_model)
				ctx.request = ctx.request.model_copy(update={"model": ctx.fallback_model})
				ctx.provider, ctx.model_name = fb_provider, fb_model_name
				ctx.candidate_keys = await self._select_provider_keys(
					db, ctx.user.org_id, ctx.provider, model=fb_model_name,
					redis=ctx.redis, max_attempts=ctx.max_fallback_attempts,
				)
				ctx.kwargs = ctx.request.model_dump(exclude_none=True)
				ctx.kwargs.update({"model": ctx.fallback_model, "timeout": 30, "request_timeout": 30})
				response, fb_count, provider_key_id = await self._execute_with_fallback(
					ctx.candidate_keys, _call, ctx.fallback_model, redis=ctx.redis,
				)
				ctx.policy_metadata = {
					**(ctx.policy_metadata or {}),
					"fallback_model_used": ctx.fallback_model,
				}
			else:
				raise

		if fb_count > 0:
			ctx.policy_metadata = {**(ctx.policy_metadata or {}), "fallback_count": fb_count}

		if ctx.policy_config.response_guardrails_enabled:
			if not response.choices:
				raise HTTPException(
					status_code=502,
					detail={"error": "provider_error", "detail": "Empty response from provider"},
				)
			resp_content = response.choices[0].message.content or ""
			resp_decision = policy_service.evaluate_response(resp_content, ctx.policy_config)
			if not resp_decision.allowed:
				if ctx.policy_config.enforcement_mode == "enforce":
					raise HTTPException(
						status_code=446,
						detail={"error": {"message": resp_decision.reason_code or "Response blocked by policy", "code": "response_policy_violation"}},
					)
				else:
					logger.warning("response guardrail violation: reason=%s", resp_decision.reason_code)
			elif resp_decision.redacted_text is not None:
				response.choices[0].message.content = resp_decision.redacted_text

		body = _to_jsonable(response)
		usage = body.get("usage", {}) if isinstance(body, dict) else {}
		prompt_tokens = int(usage.get("prompt_tokens", 0))
		completion_tokens = int(usage.get("completion_tokens", 0))
		cost = cost_tracker_service.calculate_cost_usd(response)
		latency_ms = int((time.perf_counter() - ctx.start) * 1000)

		if cache_service.is_enabled():
			cache_messages = [
				m.model_dump() if hasattr(m, "model_dump") else m
				for m in ctx.request.messages
			]
			cache_temperature = getattr(ctx.request, "temperature", None)
			asyncio.create_task(
				cache_service.set(
					ctx.redis,
					ctx.request.model,
					cache_messages,
					cache_temperature,
					body,
					org_id=ctx.user.org_id,
					db=db,
					cache_override=cache_override,
				)
			)

		request_metadata = _build_request_metadata(ctx, {"cache": "miss"})
		self._schedule_log(
			ctx.background_tasks, ctx.redis, ctx.request_id, ctx.user, ctx.api_key,
			ctx.request.model, ctx.provider, prompt_tokens, completion_tokens, cost,
			latency_ms, 200, request_metadata=request_metadata, labels=ctx.labels,
			team_id=ctx.team_id, provider_key_id=provider_key_id,
		)

		if ctx.experiment_info and (settings.EVAL_HOOK_URL or settings.EVAL_LLM_MODEL):
			prompt_text = _extract_prompt_text(ctx.request.messages)
			resp_content = response.choices[0].message.content or "" if response.choices else ""
			exp_id = ctx.experiment_info.get("experiment_id")
			var_id = ctx.experiment_info.get("variant_id")
			ctx.background_tasks.add_task(
				run_eval_hook,
				ctx.request_id,
				ctx.user.org_id,
				uuid.UUID(exp_id) if exp_id else None,
				uuid.UUID(var_id) if var_id else None,
				prompt_text,
				resp_content,
			)

		return JSONResponse(
			content=body,
			headers={
				"X-OpenProxyAI-Request-Id": str(ctx.request_id),
				"X-OpenProxyAI-Provider": ctx.provider,
				"X-OpenProxyAI-Model": ctx.request.model,
				"X-OpenProxyAI-Cost-USD": f"{cost:.6f}",
				"X-OpenProxyAI-Latency-Ms": str(latency_ms),
				"X-OpenProxyAI-Cache": "miss",
				"X-OpenProxyAI-Gateway-Error": "false",
				**ctx.rl_headers,
			},
		)

	# ------------------------------------------------------------------
	# Public entry point
	# ------------------------------------------------------------------

	async def chat_completion(
		self,
		request: ChatCompletionRequest,
		db: AsyncSession,
		redis: Redis,
		user: User,
		api_key: ApiKey,
		request_id: uuid.UUID,
		background_tasks: BackgroundTasks,
		http_request: Request | None = None,
	):
		# Resolve prompt_id → messages before policy/model selection
		if request.prompt_id is not None:
			resolved = await _resolve_prompt_template(
				db, user.org_id, request.prompt_id, request.variables or {}
			)
			request = request.model_copy(
				update={"messages": resolved, "prompt_id": None, "variables": None}
			)
		# API key's team_id takes precedence; fall back to x-openproxy-team-id header
		team_id = getattr(api_key, "team_id", None) or (
			_parse_team_id(http_request) if http_request is not None else None
		)
		retries_override = _parse_retries_header(http_request) if http_request is not None else None
		fallback_model = _parse_fallback_model_header(http_request) if http_request is not None else None
		session_id = _parse_session_id_header(http_request) if http_request is not None else None
		ctx = _RequestContext(
			request=request,
			user=user,
			api_key=api_key,
			request_id=request_id,
			background_tasks=background_tasks,
			redis=redis,
			labels=_parse_labels(http_request) if http_request is not None else None,
			start=time.perf_counter(),
			http_request=http_request,
			team_id=team_id,
			max_fallback_attempts=retries_override,
			fallback_model=fallback_model,
			session_id=session_id,
		)
		try:
			early = await self._build_litellm_kwargs(ctx, db)
			if early is not None:
				return early
			if request.stream:
				return await self._handle_streaming_response(ctx, db)
			return await self._handle_non_streaming_response(ctx, db)

		except HTTPException as exc:
			latency_ms = int((time.perf_counter() - ctx.start) * 1000)
			await log_request(
				redis=redis,
				request_id=request_id,
				org_id=user.org_id,
				user_id=user.id,
				api_key_id=api_key.id,
				model=ctx.request.model,
				provider=ctx.provider,
				prompt_tokens=0,
				completion_tokens=0,
				cost_usd=Decimal("0"),
				latency_ms=latency_ms,
				ttft_ms=None,
				status_code=exc.status_code,
				error_message=str(exc.detail),
				request_metadata=_build_request_metadata(ctx),
				labels=ctx.labels,
				team_id=ctx.team_id,
			)
			if ctx.rl_headers:
				raise HTTPException(
					status_code=exc.status_code,
					detail=exc.detail,
					headers={**ctx.rl_headers, **(exc.headers or {})},
				) from exc
			raise
		except TimeoutError as exc:
			latency_ms = int((time.perf_counter() - ctx.start) * 1000)
			self._schedule_log(
				background_tasks, redis, request_id, user, api_key,
				ctx.request.model, ctx.provider, 0, 0, Decimal("0"),
				latency_ms, 504, error_message=str(exc),
				request_metadata=_build_request_metadata(ctx), labels=ctx.labels,
				team_id=ctx.team_id,
			)
			raise HTTPException(
				status_code=504,
				detail={"error": "provider_timeout", "detail": str(exc)},
				headers=ctx.rl_headers,
			) from exc
		except Exception as exc:
			latency_ms = int((time.perf_counter() - ctx.start) * 1000)
			logger.error("Provider error for request %s model=%s: %s", request_id, ctx.request.model, exc)
			self._schedule_log(
				background_tasks, redis, request_id, user, api_key,
				ctx.request.model, ctx.provider, 0, 0, Decimal("0"),
				latency_ms, 502, error_message=str(exc),
				request_metadata=_build_request_metadata(ctx), labels=ctx.labels,
				team_id=ctx.team_id,
			)
			raise HTTPException(
				status_code=502,
				detail={"error": "provider_error", "detail": _provider_error_public_detail(exc)},
				headers=ctx.rl_headers,
			) from exc

	# ------------------------------------------------------------------
	# Embedding endpoint (uses _execute_with_fallback)
	# ------------------------------------------------------------------

	async def embedding(
		self,
		request: EmbeddingRequest,
		db: AsyncSession,
		redis: Redis,
		user: User,
		api_key: ApiKey,
		request_id: uuid.UUID,
		background_tasks: BackgroundTasks,
		http_request: Request | None = None,
	) -> JSONResponse:
		labels = _parse_labels(http_request) if http_request is not None else None
		session_id = _parse_session_id_header(http_request) if http_request is not None else None
		# API key's team_id takes precedence; fall back to x-openproxy-team-id header
		team_id = getattr(api_key, "team_id", None) or (
			_parse_team_id(http_request) if http_request is not None else None
		)
		team_budget_monthly_usd: Decimal | None = None
		if team_id is not None:
			team = await db.scalar(
				select(Team).where(
					Team.id == team_id,
					Team.org_id == user.org_id,
				)
			)
			if team is None:
				raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
			member_row = await db.execute(
				select(team_members).where(
					team_members.c.team_id == team_id,
					team_members.c.user_id == user.id,
				)
			)
			if member_row.first() is None:
				raise HTTPException(
					status_code=status.HTTP_403_FORBIDDEN,
					detail="User is not a member of this team",
				)
			team_budget_monthly_usd = team.budget_monthly_usd

		start = time.perf_counter()
		provider = "unknown"
		rl_headers: dict[str, str] = {}
		policy_metadata: dict | None = None

		def _emb_request_metadata(meta: dict | None) -> dict:
			out = {**(meta or {})}
			if session_id:
				out["session_id"] = session_id
			return out

		try:
			provider, model_name = _split_model(request.model)
			policy_config = await policy_store.load(user.org_id, db, redis)
			decision = await policy_service.evaluate_embedding_request(request, policy_config)
			policy_metadata = decision.as_metadata()
			if not decision.allowed:
				latency_ms = int((time.perf_counter() - start) * 1000)
				await log_request(
					redis=redis, request_id=request_id, org_id=user.org_id, user_id=user.id,
					api_key_id=api_key.id, model=request.model, provider=provider,
					prompt_tokens=0, completion_tokens=0, cost_usd=Decimal("0"),
					latency_ms=latency_ms, ttft_ms=None, status_code=403,
					error_message=f"policy_blocked:{decision.reason_code}",
					request_metadata=_emb_request_metadata(policy_metadata), labels=labels,
					team_id=team_id,
				)
				return self._policy_block_response(decision)
			size = len(request.input) if isinstance(request.input, list) else len(request.input)
			ok, rl_headers, limit_type, limit_detail, retry_after = await rate_limiter_service.check_limits(
				redis=redis, org_id=str(user.org_id), user_id=str(user.id),
				request_tokens_estimate=max(size // 4, 1),
				max_rpm=settings.DEFAULT_RATE_LIMIT_RPM, max_tpm=settings.DEFAULT_RATE_LIMIT_TPM,
				max_daily_budget_usd=Decimal(str(settings.DEFAULT_BUDGET_DAILY_USD)),
				user_daily_budget_usd=getattr(user, "budget_daily_usd", None),
				team_id=str(team_id) if team_id else None,
				team_budget_monthly_usd=team_budget_monthly_usd,
				model=request.model, policy_config=policy_config,
			)
			if not ok:
				latency_ms = int((time.perf_counter() - start) * 1000)
				await log_request(
					redis=redis, request_id=request_id, org_id=user.org_id, user_id=user.id,
					api_key_id=api_key.id, model=request.model, provider=provider,
					prompt_tokens=0, completion_tokens=0, cost_usd=Decimal("0"),
					latency_ms=latency_ms, ttft_ms=None, status_code=429,
					error_message=f"rate_limited:{limit_type}",
					request_metadata=_emb_request_metadata(policy_metadata), labels=labels,
					team_id=team_id,
				)
				return JSONResponse(
					status_code=429,
					content={"error": "rate_limit_exceeded", "limit_type": limit_type, "detail": limit_detail, "retry_after": retry_after},
					headers={**rl_headers, "X-OpenProxyAI-Gateway-Error": "true"},
				)

			retries_override = _parse_retries_header(http_request) if http_request is not None else None
			try:
				candidate_keys = await self._select_provider_keys(
					db, user.org_id, provider, model=model_name, redis=redis,
					max_attempts=retries_override,
				)
			except HTTPException as exc:
				raise HTTPException(
					status_code=exc.status_code, detail=exc.detail,
					headers={**rl_headers, **(exc.headers or {})},
				) from exc

			async def _emb_call(key: str) -> Any:
				return await aembedding(
					model=request.model, input=request.input, api_key=key,
					encoding_format=request.encoding_format, timeout=30,
				)

			response, fb_count, provider_key_id = await self._execute_with_fallback(
				candidate_keys, _emb_call, request.model, tag=" (embed)", redis=redis,
			)
			if fb_count > 0:
				policy_metadata = {**(policy_metadata or {}), "fallback_count": fb_count}

			body = _to_jsonable(response)
			usage = body.get("usage", {}) if isinstance(body, dict) else {}
			prompt_tokens = int(usage.get("prompt_tokens", usage.get("total_tokens", 0)))
			cost = cost_tracker_service.calculate_cost_usd(response)
			latency_ms = int((time.perf_counter() - start) * 1000)

			self._schedule_log(
				background_tasks, redis, request_id, user, api_key,
				request.model, provider, prompt_tokens, 0, cost,
				latency_ms, 200, request_metadata=_emb_request_metadata(policy_metadata), labels=labels,
				team_id=team_id, provider_key_id=provider_key_id,
			)

			return JSONResponse(
				content=body,
				headers={
					"X-OpenProxyAI-Request-Id": str(request_id),
					"X-OpenProxyAI-Provider": provider,
					"X-OpenProxyAI-Model": request.model,
					"X-OpenProxyAI-Cost-USD": f"{cost:.6f}",
					"X-OpenProxyAI-Latency-Ms": str(latency_ms),
					"X-OpenProxyAI-Gateway-Error": "false",
					**rl_headers,
				},
			)
		except HTTPException as exc:
			latency_ms = int((time.perf_counter() - start) * 1000)
			await log_request(
				redis=redis, request_id=request_id, org_id=user.org_id, user_id=user.id,
				api_key_id=api_key.id, model=request.model, provider=provider,
				prompt_tokens=0, completion_tokens=0, cost_usd=Decimal("0"),
				latency_ms=latency_ms, ttft_ms=None, status_code=exc.status_code,
				error_message=str(exc.detail), request_metadata=_emb_request_metadata(policy_metadata), labels=labels,
				team_id=team_id,
			)
			if rl_headers:
				raise HTTPException(
					status_code=exc.status_code, detail=exc.detail,
					headers={**rl_headers, **(exc.headers or {})},
				) from exc
			raise
		except TimeoutError as exc:
			latency_ms = int((time.perf_counter() - start) * 1000)
			self._schedule_log(
				background_tasks, redis, request_id, user, api_key,
				request.model, provider, 0, 0, Decimal("0"),
				latency_ms, 504, error_message=str(exc),
				request_metadata=_emb_request_metadata(policy_metadata), labels=labels,
				team_id=team_id,
			)
			raise HTTPException(
				status_code=504,
				detail={"error": "provider_timeout", "detail": str(exc)},
				headers=rl_headers,
			) from exc
		except Exception as exc:
			latency_ms = int((time.perf_counter() - start) * 1000)
			logger.error("Provider error for embedding %s model=%s: %s", request_id, request.model, exc)
			self._schedule_log(
				background_tasks, redis, request_id, user, api_key,
				request.model, provider, 0, 0, Decimal("0"),
				latency_ms, 502, error_message=str(exc),
				request_metadata=_emb_request_metadata(policy_metadata), labels=labels,
				team_id=team_id,
			)
			raise HTTPException(
				status_code=502,
				detail={"error": "provider_error", "detail": _provider_error_public_detail(exc)},
				headers=rl_headers,
			) from exc


llm_service = LLMService()
