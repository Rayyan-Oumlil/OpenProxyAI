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
from typing import Any, NamedTuple

import litellm
from fastapi import BackgroundTasks, HTTPException, Request, status
from fastapi.responses import JSONResponse, StreamingResponse
from litellm import acompletion, aembedding, aimage_generation, arerank, aresponses, aspeech, atranscription  # noqa: F401  (the provider entry points modalities.py calls through this module, so tests replace them in one place)
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
from app.schemas.chat import ChatCompletionRequest, Message, _substitute_variables
from app.services import behavior as behavior_mod
from app.services import cache_service
from app.services.policy_service import POLICY_BLOCK_STATUS
from app.services.refusal_explanations import explain_policy
from app.services.routing_service import CAPABILITY_PREFIX, RoutingDecision, decide, load_candidates, may_leave_registry
from app.utils.region import org_data_region, region_of
from app.services.classification_service import (
	DATA_CLASS_HEADER,
	Classification,
	InvalidDataClass,
	classify_chat_request,
)
from app.services.provider_client import ProviderEndpoint, openai_client_for
from app.utils.provider_endpoint import filter_allowed_endpoints
from app.services.cache_service import CacheOverride
from app.services.audit_logger import log_request
from app.services.payload_capture import capture_payload, should_capture
from app.services.cost_tracker import cost_tracker_service
from app.services.circuit_breaker_service import (
	is_circuit_open,
	record_failure as circuit_record_failure,
	record_success as circuit_record_success,
)
from app.services.adaptive_sampling_service import get_error_rate, get_latency_p99
from app.services.key_secrets import resolve_secret
from app.services.external_secret_error import ExternalSecretError
from app.services.eval_service import _extract_prompt_text, run_eval_hook
from app.services.mcp_taint import ChatTaintResult, load_trust_rules, restrict_chat_request
from app.services.policy_service import PolicyDecision, policy_service
from app.services.stage_timing import StageTimer, timer_for_request
from app.utils.logging import get_logger
from app.utils.token_estimator import estimate_tokens

logger = get_logger(__name__)


def _provider_error_public_detail(exc: Exception) -> str:
	"""Avoid leaking internals in production; full message when DEBUG."""
	return str(exc) if settings.DEBUG else "Upstream provider error"


_RETRYABLE_STATUS_CODES: frozenset[int] = frozenset({429, 500, 502, 503, 504})

class ProviderKeyCandidate(NamedTuple):
	"""One provider key to try. key_id is None for env-provided keys; api_base None means the provider's own endpoint."""

	key_id: uuid.UUID | None
	api_key: str
	api_base: str | None = None
	is_internal: bool = False


def with_endpoint(call_kwargs: dict[str, Any], api_key: str, endpoint: ProviderEndpoint | None) -> dict[str, Any]:
	"""For a key with a custom endpoint, call it through the connection guard; otherwise leave the call exactly as it was."""
	if endpoint is None:
		return call_kwargs
	return {**call_kwargs, "api_base": endpoint.api_base, "client": openai_client_for(api_key, endpoint)}


def _is_retryable(exc: Exception) -> bool:
	"""Return True if the exception represents a transient provider error (ADR-9)."""
	status_code = getattr(exc, "status_code", None)
	return isinstance(status_code, int) and status_code in _RETRYABLE_STATUS_CODES


def split_model(model_name: str) -> tuple[str, str]:
	"""``provider/name`` into its two parts; anything else is a 400, here and in the playground and policy preview."""
	if "/" not in model_name:
		raise HTTPException(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail={"error": "invalid_model", "detail": "Model must be provider/model (e.g. openai/gpt-4o)"},
		)
	provider, model = model_name.split("/", 1)
	if not provider or not model:
		raise HTTPException(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail={"error": "invalid_model", "detail": "Model must be provider/model (e.g. openai/gpt-4o)"},
		)
	return provider, model


_DETACHED_TASKS: set[asyncio.Task] = set()


def _log_detached(**kwargs: Any) -> None:
	"""Fire-and-forget audit write for paths that re-raise an HTTPException.

	FastAPI drops BackgroundTasks when a route raises, so these writes run as a detached task
	(log_request opens its own org-scoped session) instead of being awaited inline.
	"""
	task = asyncio.create_task(log_request(**kwargs))
	_DETACHED_TASKS.add(task)
	task.add_done_callback(_DETACHED_TASKS.discard)


def _extra_delta_text(delta: dict[str, Any]) -> list[str]:
	"""Billable stream text other than `content`: tool-call names/arguments and reasoning."""
	parts: list[str] = []
	for call in delta.get("tool_calls") or []:
		function = call.get("function") if isinstance(call, dict) else None
		if isinstance(function, dict):
			parts.extend(function[k] for k in ("name", "arguments") if isinstance(function.get(k), str))
	parts.extend(delta[k] for k in ("reasoning_content", "reasoning") if isinstance(delta.get(k), str))
	return parts


class _AccountedStreamingResponse(StreamingResponse):
	"""StreamingResponse whose accounting hook also runs when the body generator never starts."""

	def __init__(self, *args: Any, on_close: Callable[[], Coroutine[Any, Any, None]], **kwargs: Any) -> None:
		super().__init__(*args, **kwargs)
		self._on_close = on_close

	async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
		try:
			await super().__call__(scope, receive, send)
		finally:
			await self._on_close()

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


def _is_cache_unsafe(request: ChatCompletionRequest) -> bool:
	"""Tool-calling and structured-output requests must bypass the cache.

	The cache key covers model, messages and temperature only, so the same messages with
	different tools / response_format would be served each other's cached answer.
	"""
	extras = request.model_extra or {}
	if any(extras.get(k) for k in ("tools", "functions", "tool_choice", "function_call", "response_format")):
		return True
	return any(m.role == "tool" or (m.model_extra or {}).get("tool_calls") for m in request.messages)


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
	classification: Classification | None = None
	routing: RoutingDecision | None = None
	routing_notes: dict = field(default_factory=dict)  # why routing changed something (experiment skipped, fallback refused)
	requested_model: str = ""  # what the caller asked for, before any experiment variant replaced it
	route_key_id: uuid.UUID | None = None  # enforce: the registry key that serves the model, and the only key used
	fallback_key_id: uuid.UUID | None = None  # enforce: the same, for an authorized x-openproxy-fallback-model
	stages: StageTimer | None = None
	behavior: behavior_mod.Resolved | None = None  # the behaviour settings for this call, after the org's defaults and ceiling
	behavior_plan: behavior_mod.Plan | None = None  # the provider parameters they became for the model last called

	def __post_init__(self) -> None:
		if self.stages is None:
			self.stages = timer_for_request(self.http_request, self.start)


def _build_request_metadata(ctx: _RequestContext, extra: dict | None = None) -> dict:
	"""Build request_metadata for logging, merging policy_metadata, experiment_info, session_id."""
	metadata = {**(ctx.policy_metadata or {})}
	if ctx.behavior is not None:
		metadata["behavior"] = {**ctx.behavior.as_metadata(), **(ctx.behavior_plan.as_metadata() if ctx.behavior_plan else {})}
	stages = ctx.stages.as_list() if ctx.stages else []
	if stages:
		metadata = {**metadata, "stages": stages}
	if ctx.experiment_info:
		metadata = {**metadata, "experiment": ctx.experiment_info}
	if ctx.session_id:
		metadata = {**metadata, "session_id": ctx.session_id}
	if ctx.classification is not None:
		metadata = {**metadata, "data_class": ctx.classification.as_metadata()}
	if ctx.routing is not None:
		metadata = {**metadata, "routing": {**ctx.routing.as_metadata(), **ctx.routing_notes}}
	if extra:
		metadata = {**metadata, **extra}
	return metadata


def route_decision(candidates: list, region: str, config, data_class: str, model: str) -> RoutingDecision | None:
	"""The routing decision for ``model`` under the org's policy; None when routing is off. One place binds policy to the core."""
	return decide(
		candidates, mode=config.routing_mode, data_class=data_class, org_region=region, max_risk=config.max_risk_rating,
		allows_model=lambda m: policy_service.is_model_on_allowlist(m, config), requested=model,
	)


class LLMService:
	async def _select_provider_keys(
		self,
		db: AsyncSession,
		org_id: uuid.UUID,
		provider: str,
		model: str | None = None,
		redis: Redis | None = None,
		max_attempts: int | None = None,
		only_key_id: uuid.UUID | None = None,
	) -> list[ProviderKeyCandidate]:
		"""Return ordered list of (key_id, decrypted_key) tuples: [primary, fallback1, ...].

		With ``only_key_id`` (routing enforced) the model's registry key is the only candidate: no other key of the
		provider and never an environment key, because either could be cleared for less sensitive data.

		key_id is None for env-provided keys. Strategy: simple_shuffle (weighted random),
		round_robin, or lowest_latency. Fallbacks sorted by weight descending.
		Total list capped at max_attempts+1. Only keys matching data_region or 'global' eligible.
		"""
		limit = (max_attempts + 1) if max_attempts is not None else (settings.MAX_PROVIDER_FALLBACK_ATTEMPTS + 1)
		org = await db.get(Organization, org_id)
		data_region = region_of(org)
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
		if only_key_id is not None:
			conditions.append(LLMProviderKey.id == only_key_id)
		if settings.PROVIDER_HEALTH_CHECK_ENABLED:
			conditions.append(LLMProviderKey.health_status != "unhealthy")
		rows = await db.scalars(select(LLMProviderKey).where(*conditions))
		keys = [row for row in rows if row.weight > 0]
		keys, endpoints_dropped = await filter_allowed_endpoints(keys)
		if not keys and endpoints_dropped:
			# Never fall through to the gateway's own key: the data was meant for a private endpoint.
			raise HTTPException(
				status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
				detail={
					"error": "no_provider_key",
					"detail": "Every provider endpoint configured for this provider failed validation. Check the keys' api_base values.",
				},
			)
		if only_key_id is not None and not keys:
			raise HTTPException(
				status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
				detail={
					"error": "no_provider_key",
					"detail": "The provider key assigned to this model in the registry is not available. No other key is used.",
				},
			)
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
			resolved: list[ProviderKeyCandidate] = []
			for k in ordered:
				try:
					resolved.append(ProviderKeyCandidate(k.id, await resolve_secret(k), k.api_base, k.is_internal))
				except ExternalSecretError as exc:
					# Never a silent fall back: the key is skipped, the reason is logged with no secret in it, and if nothing is left the
					# caller gets the "no provider keys" error below.
					logger.error("provider key %s could not be read from its secret manager: %s", k.id, exc)
			if not resolved:
				raise HTTPException(
					status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
					detail={"error": "no_provider_key", "detail": "No provider keys available: a key held in a secret manager could not be read"},
				)
			return resolved

		env_map = {
			"openai": settings.OPENAI_API_KEY,
			"anthropic": settings.ANTHROPIC_API_KEY,
			"azure": settings.AZURE_API_KEY,
		}
		api_key = env_map.get(provider, "")
		# Env keys have no region tag, so only regions the operator opted in may use them.
		shared_regions = {r.strip().lower() for r in settings.SHARED_KEY_REGIONS.split(",") if r.strip()}
		if api_key and data_region in shared_regions:
			return [ProviderKeyCandidate(None, api_key)]

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
	def _may_leave_registry(ctx: _RequestContext) -> bool:
		"""False when routing is enforced and this request is above the ceiling for destinations the registry does not govern."""
		if ctx.routing is None or ctx.classification is None:
			return True
		return may_leave_registry(ctx.routing.mode, ctx.classification.data_class, settings.OFF_REGISTRY_MAX_DATA_CLASS)

	@staticmethod
	def _schedule_eval(ctx: _RequestContext, response_text: str) -> None:
		"""Hand an experiment request and its response to the evaluation hook, unless that would send it somewhere ungoverned."""
		if not (ctx.experiment_info and (settings.EVAL_HOOK_URL or settings.EVAL_LLM_MODEL)):
			return
		if not LLMService._may_leave_registry(ctx):
			return
		exp_id = ctx.experiment_info.get("experiment_id")
		var_id = ctx.experiment_info.get("variant_id")
		ctx.background_tasks.add_task(
			run_eval_hook,
			ctx.request_id,
			ctx.user.org_id,
			uuid.UUID(exp_id) if exp_id else None,
			uuid.UUID(var_id) if var_id else None,
			_extract_prompt_text(ctx.request.messages),
			response_text,
		)

	@staticmethod
	def _schedule_capture(ctx: _RequestContext, response_text: str) -> None:
		"""Keep the redacted prompt and answer for evaluation, only if the org opted in and this request was sampled.

		Off at the default rate of 0, never above the operator's data-class ceiling, and run in the background after
		the response is built, so it cannot change what the caller receives.
		"""
		if not response_text or ctx.classification is None:
			return
		if not should_capture(
			sample_rate=getattr(ctx.policy_config, "payload_capture_sample_rate", 0.0),
			data_class=ctx.classification.data_class,
			ceiling=settings.PAYLOAD_CAPTURE_MAX_DATA_CLASS,
		):
			return
		ctx.background_tasks.add_task(capture_payload, ctx.user.org_id, ctx.request_id, ctx.request.messages, response_text)

	@staticmethod
	def _route_headers(routing: RoutingDecision | None) -> dict[str, str]:
		if routing is None:
			return {}
		return {"X-OpenProxyAI-Route-Model": routing.model or "none", "X-OpenProxyAI-Route-Reason": routing.reason}

	@staticmethod
	def _routing_block_response(routing: RoutingDecision) -> JSONResponse:
		return JSONResponse(
			status_code=POLICY_BLOCK_STATUS,
			content={
				"error": "routing_blocked",
				"reason_code": "no_authorized_model",
				"detail": "No model authorized for this request's data class can serve it.",
				"explanation": routing.explanation,
				"route_reason": routing.reason,
				"data_class": routing.data_class,
				"requested_model": routing.requested,
			},
			headers={
				"X-OpenProxyAI-Gateway-Error": "true",
				"X-OpenProxyAI-Policy-Action": "block",
				"X-OpenProxyAI-Data-Class": routing.data_class,
				**LLMService._route_headers(routing),
			},
		)

	@staticmethod
	async def routing_inputs(db: AsyncSession, org_id: uuid.UUID) -> tuple[list, str]:
		"""The org's routable registry and its data region (one query each; the session is already org-scoped)."""
		return await load_candidates(db, org_id), await org_data_region(db, org_id)

	async def _decide_route(self, ctx: _RequestContext, db: AsyncSession) -> None:
		"""Decide which registry model may serve this request; in enforce mode, also constrain how it is served.

		``log_only`` records the same decision but changes nothing. ``enforce`` makes the decision binding:
		the model must be authorized, it is served only by its registry key, an experiment variant that is not
		authorized is dropped in favor of the model the caller asked for, and an x-openproxy-fallback-model that
		is not authorized is ignored. Nothing is ever swapped for a different model than the caller asked for.
		"""
		config = ctx.policy_config
		mode = config.routing_mode
		candidates, region = await self.routing_inputs(db, ctx.user.org_id)

		def decide_for(model: str) -> RoutingDecision:
			return route_decision(candidates, region, config, ctx.classification.data_class, model)

		decision = decide_for(ctx.request.model)
		if mode == "enforce" and decision.model is None and ctx.experiment_info and ctx.requested_model != ctx.request.model:
			original = decide_for(ctx.requested_model)
			if original.model is not None:
				ctx.routing_notes["experiment_skipped"] = f"variant {ctx.request.model} is not authorized"
				ctx.request = ctx.request.model_copy(update={"model": ctx.requested_model})
				ctx.provider, ctx.model_name = split_model(ctx.requested_model)
				ctx.experiment_info = None
				decision = original
		ctx.routing = decision

		if mode != "enforce":
			return
		if decision.model is not None:
			if decision.model != ctx.request.model:  # a cap:NAME request, now a concrete model
				ctx.request = ctx.request.model_copy(update={"model": decision.model})
				ctx.provider, ctx.model_name = split_model(decision.model)
			ctx.route_key_id = decision.key_id
		if ctx.fallback_model:
			fallback = decide_for(ctx.fallback_model)
			if fallback.model is None:
				ctx.routing_notes["fallback_model_refused"] = fallback.reason
				ctx.fallback_model = None
			else:
				ctx.fallback_model, ctx.fallback_key_id = fallback.model, fallback.key_id

	@staticmethod
	def _policy_block_response(decision: PolicyDecision) -> JSONResponse:
		return JSONResponse(
			status_code=POLICY_BLOCK_STATUS,
			content={
				"error": "policy_violation",
				"detail": decision.detail or "Request blocked by policy.",
				"reason_code": decision.reason_code,
				"explanation": explain_policy(decision.reason_code),
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

	async def _apply_tool_taint(self, ctx: _RequestContext, db: AsyncSession) -> ChatTaintResult | None:
		"""Strip sink tools from a conversation that has handled untrusted tool output (see mcp_taint)."""
		mode = ctx.policy_config.enforcement_mode.lower().strip()
		if mode == "off" or not any(m.role == "tool" for m in ctx.request.messages):
			return None
		rules = await load_trust_rules(db, ctx.user.org_id)
		result = restrict_chat_request(ctx.request, rules, enforce=mode != "log_only")
		if result.request is not ctx.request:
			ctx.request = result.request
		return result

	async def _build_litellm_kwargs(
		self,
		ctx: _RequestContext,
		db: AsyncSession,
	) -> JSONResponse | None:
		"""Policy eval, rate limit, key selection, kwargs build.

		Returns a JSONResponse when the request should be short-circuited
		(policy block or rate limit), otherwise None.
		"""
		ctx.requested_model = ctx.request.model
		is_capability_request = ctx.request.model.startswith(CAPABILITY_PREFIX)
		if is_capability_request:
			ctx.provider, ctx.model_name = "unknown", ""  # a "cap:NAME" request is resolved to a concrete model by routing
			resolved_model, experiment_info = ctx.request.model, None
		else:
			ctx.provider, ctx.model_name = split_model(ctx.request.model)
			resolved_model, experiment_info = await self._resolve_experiment(
				db, ctx.user.org_id, ctx.request.model
			)
		if experiment_info:
			ctx.request = ctx.request.model_copy(update={"model": resolved_model})
			ctx.provider, ctx.model_name = split_model(resolved_model)
			ctx.experiment_info = experiment_info

		from app.services.request_gate import admit  # here, not at the top: the gate itself imports this module

		taint: ChatTaintResult | None = None

		async def evaluate(config: Any) -> PolicyDecision:
			nonlocal taint
			ctx.policy_config = config
			taint = await self._apply_tool_taint(ctx, db)
			decision = await policy_service.evaluate_chat_request(ctx.request, config)
			if decision.allowed and taint is not None and taint.forced_sink:
				decision = policy_service.taint_violation(taint.forced_sink, config)
			ctx.policy_metadata = decision.as_metadata()
			return decision

		async def classify(config: Any) -> Classification:
			try:
				ctx.classification = await classify_chat_request(
					ctx.request, config,
					ctx.http_request.headers.get(DATA_CLASS_HEADER) if ctx.http_request is not None else None,
				)
			except InvalidDataClass as exc:
				raise HTTPException(status_code=400, detail={"error": "invalid_data_class", "detail": str(exc)}) from exc
			if taint is not None and taint.tainted:
				ctx.policy_metadata["tool_taint"] = {"removed": list(taint.removed), "forced_sink": taint.forced_sink}
			if is_capability_request and config.routing_mode != "enforce":
				raise HTTPException(
					status_code=status.HTTP_400_BAD_REQUEST,
					detail={"error": "invalid_model", "detail": "Capability routing (cap:NAME) needs routing_mode=enforce in the organization's policy"},
				)
			return ctx.classification

		async def route(_config: Any, _classification: Any) -> RoutingDecision | None:
			await self._decide_route(ctx, db)
			return ctx.routing

		async def between(config: Any, _classification: Any, _routing: Any) -> Decimal | None:
			# Validate x-openproxy-fallback-model against policy allowlist when present
			if ctx.fallback_model and config.allowed_models:
				allowlist = {m.strip() for m in config.allowed_models if m.strip()}
				if allowlist and ctx.fallback_model not in allowlist:
					ctx.fallback_model = None  # Ignore header if model not allowed

			# Resolve team context from x-openproxy-team-id (optional)
			if ctx.team_id is not None:
				team = await db.scalar(select(Team).where(Team.id == ctx.team_id, Team.org_id == ctx.user.org_id))
				if team is None:
					raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
				member_row = await db.execute(
					select(team_members).where(team_members.c.team_id == ctx.team_id, team_members.c.user_id == ctx.user.id)
				)
				if member_row.first() is None:
					raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is not a member of this team")
				ctx.team_budget_monthly_usd = team.budget_monthly_usd
			return ctx.team_budget_monthly_usd

		def settle_behavior(config: Any) -> behavior_mod.Resolved | None:
			try:
				header = ctx.http_request.headers.get(behavior_mod.HEADER) if ctx.http_request is not None else None
				requested = behavior_mod.merge(
					behavior_mod.from_mapping(ctx.request.behavior) if ctx.request.behavior is not None else behavior_mod.Behavior(),
					behavior_mod.parse_header(header),
				)
			except behavior_mod.InvalidBehavior as exc:
				raise HTTPException(status_code=400, detail={"error": "invalid_behavior", "detail": str(exc)}) from exc
			ctx.behavior = behavior_mod.settle(getattr(config, "behavior_defaults", None), getattr(config, "behavior_ceiling", None), requested)
			return ctx.behavior

		gate = await admit(
			db=db, redis=ctx.redis, user=ctx.user, model_of=lambda: ctx.request.model, timer=ctx.stages, evaluate=evaluate, classify=classify,
			route=route, between=between, estimate_tokens=estimate_tokens(ctx.request), team_id=ctx.team_id, behavior=settle_behavior,
		)
		if gate.rl_headers is not None:
			ctx.rl_headers = gate.rl_headers
		if gate.refusal is not None:
			ctx.background_tasks.add_task(log_request,
				redis=ctx.redis, request_id=ctx.request_id, org_id=ctx.user.org_id, user_id=ctx.user.id, api_key_id=ctx.api_key.id,
				model=ctx.request.model, provider=ctx.provider, prompt_tokens=0, completion_tokens=0, cost_usd=Decimal("0"),
				latency_ms=int((time.perf_counter() - ctx.start) * 1000), ttft_ms=None, status_code=gate.refusal.status_code,
				error_message=gate.error, request_metadata=_build_request_metadata(ctx), labels=ctx.labels, team_id=ctx.team_id,
			)
			return gate.refusal

		try:
			ctx.candidate_keys = await self._select_provider_keys(
				db, ctx.user.org_id, ctx.provider, model=ctx.model_name, redis=ctx.redis,
				max_attempts=ctx.max_fallback_attempts, only_key_id=ctx.route_key_id,
			)
		except HTTPException as exc:
			raise HTTPException(
				status_code=exc.status_code,
				detail=exc.detail,
				headers={**ctx.rl_headers, **(exc.headers or {})},
			) from exc

		if ctx.behavior is not None and ctx.behavior.effective.citations:
			ctx.request = ctx.request.model_copy(update={"messages": [
				Message.model_validate(m) for m in behavior_mod.with_citation_instruction([m.model_dump() for m in ctx.request.messages])
			]})
		ctx.kwargs = self._provider_kwargs(ctx, ctx.request.model)
		return None

	@staticmethod
	def _provider_kwargs(ctx: _RequestContext, model: str) -> dict[str, Any]:
		"""What to send the provider for ``model``: the request as the caller made it, plus the behaviour settings as parameters this
		model accepts (the caller's own temperature, max_tokens and reasoning_effort win, lowered to the org's ceiling if it has one)."""
		kwargs = ctx.request.model_dump(exclude_none=True, exclude={"behavior"})
		kwargs.update({"model": model, "timeout": 30, "request_timeout": 30})
		if ctx.behavior is not None:
			provider, model_name = split_model(model)
			ctx.behavior_plan = behavior_mod.plan_params(
				resolved=ctx.behavior, explicit=kwargs, supported=behavior_mod.supported_params(provider, model_name),
			)
			kwargs.update(ctx.behavior_plan.params)
			for name in ctx.behavior_plan.remove:
				kwargs.pop(name, None)
		return kwargs

	@staticmethod
	async def _execute_with_fallback(
		candidates: list[ProviderKeyCandidate],
		call_fn: Callable[..., Coroutine[Any, Any, Any]],
		model_label: str,
		tag: str = "",
		redis: Redis | None = None,
	) -> tuple[Any, int, uuid.UUID | None]:
		"""Iterate candidate keys, calling *call_fn(api_key)* for each (plus ``endpoint=`` for a key with a custom endpoint).

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
		for idx, candidate in enumerate(candidates):
			key_id, api_key = candidate[0], candidate[1]
			api_base = candidate[2] if len(candidate) > 2 else None
			endpoint = ProviderEndpoint(api_base, bool(candidate[3]) if len(candidate) > 3 else False) if api_base else None
			if idx > 0:
				fallback_count += 1
				logger.warning("provider fallback%s attempt=%d model=%s", tag, idx + 1, model_label)
			try:
				response = await (call_fn(api_key, endpoint=endpoint) if endpoint else call_fn(api_key))
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
			prompt_cost, completion_cost = litellm.cost_per_token(
				model=ctx.request.model,
				prompt_tokens=estimated_prompt,
				completion_tokens=max_completion,
			)
			estimated_cost = prompt_cost + completion_cost
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

		# Providers only report usage on streams when asked; strip the extra chunk if the client did not.
		client_wants_usage = bool((ctx.kwargs.get("stream_options") or {}).get("include_usage"))
		ctx.kwargs["stream"] = True

		async def _stream_call(key: str, endpoint: ProviderEndpoint | None = None) -> tuple[Any, Any]:
			stream_options = {**(ctx.kwargs.get("stream_options") or {}), "include_usage": True}
			call_kwargs = with_endpoint({**ctx.kwargs, "api_key": key, "stream_options": stream_options}, key, endpoint)
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
			with ctx.stages.stage("upstream"):
				(stream, first_chunk), fb_count, provider_key_id = await self._execute_with_fallback(
					ctx.candidate_keys, _stream_call, ctx.request.model, tag=" (stream)", redis=ctx.redis,
				)
		except Exception as exc:
			# Retry with x-openproxy-fallback-model when primary keys all fail
			if _is_retryable(exc) and ctx.fallback_model and not getattr(ctx, "_used_fallback_model", False):
				ctx._used_fallback_model = True
				fb_provider, fb_model_name = split_model(ctx.fallback_model)
				ctx.request = ctx.request.model_copy(update={"model": ctx.fallback_model})
				ctx.provider, ctx.model_name = fb_provider, fb_model_name
				ctx.candidate_keys = await self._select_provider_keys(
					db, ctx.user.org_id, ctx.provider, model=fb_model_name,
					redis=ctx.redis, max_attempts=ctx.max_fallback_attempts,
					only_key_id=ctx.fallback_key_id,
				)
				ctx.kwargs = {**self._provider_kwargs(ctx, ctx.fallback_model), "stream": True}
				with ctx.stages.stage("upstream"):
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

		stream_state = {"completed": False, "recorded": False}
		collected_chunks: list[str] = []  # response text, for guardrails and eval
		usage_chunks: list[str] = []  # everything billable: text, tool-call arguments, reasoning

		def _record_stream() -> None:
			"""Record cost + audit row exactly once, however the response ends (done, disconnect, never started)."""
			nonlocal prompt_tokens, completion_tokens
			if stream_state["recorded"]:
				return
			stream_state["recorded"] = True
			completed = stream_state["completed"]
			if prompt_tokens == 0:
				request_messages = [m.model_dump(exclude_none=True) for m in ctx.request.messages]
				try:
					prompt_tokens = litellm.token_counter(model=ctx.request.model, messages=request_messages)
				except Exception as exc:
					logger.warning("Stream prompt token estimate failed for request %s: %s", ctx.request_id, exc)
					prompt_tokens = len(json.dumps(request_messages, default=str)) // 4 + 1
				# tools / response_format are part of the prompt the provider bills
				prompt_tokens += len(json.dumps(ctx.request.model_extra or {}, default=str)) // 4
			if completion_tokens == 0 and usage_chunks:
				streamed_text = "".join(usage_chunks)
				try:
					completion_tokens = litellm.token_counter(model=ctx.request.model, text=streamed_text)
				except Exception as exc:
					logger.warning("Stream completion token estimate failed for request %s: %s", ctx.request_id, exc)
					completion_tokens = len(streamed_text) // 4 + 1
			latency_ms = int((time.perf_counter() - ctx.start) * 1000)
			cost = Decimal("0")
			if prompt_tokens > 0 or completion_tokens > 0:
				cost, estimated = cost_tracker_service.price_or_fallback({
					"model": ctx.request.model,
					"usage": {
						"prompt_tokens": prompt_tokens,
						"completion_tokens": completion_tokens,
						"total_tokens": prompt_tokens + completion_tokens,
					},
				})
				if estimated:
					ctx.policy_metadata = {**(ctx.policy_metadata or {}), "cost_estimated": True}
			if completed:
				self._schedule_log(
					ctx.background_tasks, ctx.redis, ctx.request_id, ctx.user, ctx.api_key,
					ctx.request.model, ctx.provider, prompt_tokens, completion_tokens, cost,
					latency_ms, 200, ttft_ms=ttft_ms, request_metadata=_build_request_metadata(ctx), labels=ctx.labels,
					team_id=ctx.team_id, provider_key_id=provider_key_id,
				)
				return
			# Client went away mid-stream: FastAPI may not run BackgroundTasks, so detach the write.
			_log_detached(
				redis=ctx.redis, request_id=ctx.request_id, org_id=ctx.user.org_id, user_id=ctx.user.id,
				api_key_id=ctx.api_key.id, provider_key_id=provider_key_id, model=ctx.request.model,
				provider=ctx.provider, prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
				cost_usd=cost, latency_ms=latency_ms, ttft_ms=ttft_ms, status_code=499,
				error_message="client_disconnected", request_metadata=_build_request_metadata(ctx),
				labels=ctx.labels, team_id=ctx.team_id,
			)

		async def _close_stream() -> None:
			"""Runs when the response ends for any reason, including before the body generator ever started."""
			try:
				_record_stream()
			finally:
				aclose = getattr(stream, "aclose", None)
				if aclose is not None:
					try:
						await aclose()
					except Exception as exc:
						logger.debug("Closing upstream stream failed for request %s: %s", ctx.request_id, exc)

		async def event_stream() -> AsyncGenerator[str, None]:
			try:
				first_payload = _to_jsonable(first_chunk)
				if isinstance(first_payload, dict):
					_update_usage(first_payload)
					for choice in first_payload.get("choices", []):
						first_delta = choice.get("delta", {})
						if first_delta.get("content"):
							collected_chunks.append(first_delta["content"])
							usage_chunks.append(first_delta["content"])
						usage_chunks.extend(_extra_delta_text(first_delta))
				yield f"data: {json.dumps(first_payload)}\n\n"
				async for chunk in stream:
					chunk_payload = _to_jsonable(chunk)
					if isinstance(chunk_payload, dict):
						_update_usage(chunk_payload)
						for choice in chunk_payload.get("choices", []):
							delta = choice.get("delta", {})
							content = delta.get("content")
							if content:
								collected_chunks.append(content)
								usage_chunks.append(content)
							usage_chunks.extend(_extra_delta_text(delta))
					if not client_wants_usage and isinstance(chunk_payload, dict) and "usage" in chunk_payload:
						chunk_payload = {k: v for k, v in chunk_payload.items() if k != "usage"}
						if not chunk_payload.get("choices"):
							continue
					yield f"data: {json.dumps(chunk_payload)}\n\n"
				yield "data: [DONE]\n\n"
				stream_state["completed"] = True
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
				self._schedule_eval(ctx, "".join(collected_chunks))
				self._schedule_capture(ctx, "".join(collected_chunks))
			finally:
				_record_stream()

		return _AccountedStreamingResponse(
			event_stream(),
				on_close=_close_stream,
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
		# The cache key covers model, messages and temperature. A behaviour setting that changes anything else (reasoning effort, length)
		# would be answered from an entry made without it, so those calls skip the cache.
		skip_cache = _is_cache_unsafe(ctx.request) or (ctx.behavior_plan is not None and ctx.behavior_plan.changes_more_than_temperature)
		cache_override = "skip" if skip_cache else _parse_cache_override(ctx.http_request)
		# Cache check — failure must never block a real LLM call
		try:
			cache_messages = [
				m.model_dump() if hasattr(m, "model_dump") else m
				for m in ctx.request.messages
			]
			cache_temperature = ctx.kwargs.get("temperature")
			with ctx.stages.stage("cache"):
				cached_body, cache_tier = await cache_service.get(
					ctx.redis,
					ctx.request.model,
					cache_messages,
					cache_temperature,
					org_id=ctx.user.org_id,
					db=db,
					cache_override=cache_override,
					allow_semantic=self._may_leave_registry(ctx),
				)
			if cached_body is not None and cache_tier:
				cached_usage = cached_body.get("usage", {}) if isinstance(cached_body, dict) else {}
				cached_prompt = int(cached_usage.get("prompt_tokens", 0))
				cached_completion = int(cached_usage.get("completion_tokens", 0))
				cached_cost, _ = cost_tracker_service.price_or_fallback(cached_body)
				cached_latency = int((time.perf_counter() - ctx.start) * 1000)
				request_metadata = _build_request_metadata(ctx, {"cache": cache_tier})
				self._schedule_log(
					ctx.background_tasks, ctx.redis, ctx.request_id, ctx.user, ctx.api_key,
					ctx.request.model, ctx.provider, cached_prompt, cached_completion, cached_cost,
					cached_latency, 200, request_metadata=request_metadata, labels=ctx.labels,
					team_id=ctx.team_id,
				)
				cached_content = ""
				if isinstance(cached_body, dict):
					for c in cached_body.get("choices", []) or []:
						msg = c.get("message", {})
						if isinstance(msg, dict) and msg.get("content"):
							cached_content = msg["content"]
							break
				self._schedule_eval(ctx, cached_content)
				self._schedule_capture(ctx, cached_content)
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

		async def _call(key: str, endpoint: ProviderEndpoint | None = None) -> Any:
			call_kwargs = with_endpoint({**ctx.kwargs, "api_key": key}, key, endpoint)
			return await acompletion(**call_kwargs)

		response, fb_count, provider_key_id = None, 0, None
		try:
			with ctx.stages.stage("upstream"):
				response, fb_count, provider_key_id = await self._execute_with_fallback(
					ctx.candidate_keys, _call, ctx.request.model, redis=ctx.redis,
				)
		except Exception as exc:
			# Retry with x-openproxy-fallback-model when primary keys all fail
			if _is_retryable(exc) and ctx.fallback_model and not getattr(ctx, "_used_fallback_model", False):
				ctx._used_fallback_model = True
				fb_provider, fb_model_name = split_model(ctx.fallback_model)
				ctx.request = ctx.request.model_copy(update={"model": ctx.fallback_model})
				ctx.provider, ctx.model_name = fb_provider, fb_model_name
				ctx.candidate_keys = await self._select_provider_keys(
					db, ctx.user.org_id, ctx.provider, model=fb_model_name,
					redis=ctx.redis, max_attempts=ctx.max_fallback_attempts,
					only_key_id=ctx.fallback_key_id,
				)
				ctx.kwargs = self._provider_kwargs(ctx, ctx.fallback_model)
				with ctx.stages.stage("upstream"):
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
						status_code=POLICY_BLOCK_STATUS,
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
		cost, estimated = cost_tracker_service.price_or_fallback(response)
		if estimated:
			ctx.policy_metadata = {**(ctx.policy_metadata or {}), "cost_estimated": True}
		latency_ms = int((time.perf_counter() - ctx.start) * 1000)

		if cache_service.is_enabled():
			cache_messages = [
				m.model_dump() if hasattr(m, "model_dump") else m
				for m in ctx.request.messages
			]
			cache_temperature = ctx.kwargs.get("temperature")
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
					allow_semantic=self._may_leave_registry(ctx),
				)
			)

		request_metadata = _build_request_metadata(ctx, {"cache": "miss"})
		self._schedule_log(
			ctx.background_tasks, ctx.redis, ctx.request_id, ctx.user, ctx.api_key,
			ctx.request.model, ctx.provider, prompt_tokens, completion_tokens, cost,
			latency_ms, 200, request_metadata=request_metadata, labels=ctx.labels,
			team_id=ctx.team_id, provider_key_id=provider_key_id,
		)

		answer = response.choices[0].message.content or "" if response.choices else ""
		self._schedule_eval(ctx, answer)
		self._schedule_capture(ctx, answer)

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
			_log_detached(
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


llm_service = LLMService()
