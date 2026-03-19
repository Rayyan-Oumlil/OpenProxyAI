"""LiteLLM wrapper — acompletion, cost calculation, streaming with capture."""

import asyncio
import fnmatch
import json
import logging
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
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.api_key import ApiKey
from app.models.llm_provider_key import LLMProviderKey
from app.models.user import User
from app.schemas.chat import ChatCompletionRequest, EmbeddingRequest
from app.services import cache_service
from app.services.audit_logger import log_request
from app.services.cost_tracker import cost_tracker_service
from app.services.crypto_service import decrypt
from app.services.policy_service import PolicyDecision, policy_service, policy_store
from app.services.rate_limiter import rate_limiter_service
from app.utils.token_estimator import estimate_tokens

logger = logging.getLogger(__name__)

_RETRYABLE_STATUS_CODES: frozenset[int] = frozenset({429, 500, 502, 503, 504})


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


# ---------------------------------------------------------------------------
# Shared request context for the decomposed chat_completion pipeline
# ---------------------------------------------------------------------------


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
	provider: str = "unknown"
	model_name: str = ""
	rl_headers: dict[str, str] = field(default_factory=dict)
	policy_metadata: dict | None = None
	policy_config: Any = None
	candidate_keys: list[str] = field(default_factory=list)
	kwargs: dict[str, Any] = field(default_factory=dict)


class LLMService:
	async def _select_provider_keys(
		self,
		db: AsyncSession,
		org_id: uuid.UUID,
		provider: str,
		model: str | None = None,
	) -> list[str]:
		"""Return ordered list of decrypted API keys: [primary, fallback1, ...].

		The primary key is selected via weighted random (preserving existing behaviour).
		Fallbacks are the remaining candidates sorted by weight descending.
		Total list is capped at settings.MAX_PROVIDER_FALLBACK_ATTEMPTS.
		"""
		rows = await db.scalars(
			select(LLMProviderKey).where(
				LLMProviderKey.org_id == org_id,
				LLMProviderKey.provider == provider,
				LLMProviderKey.is_active.is_(True),
			)
		)
		keys = [row for row in rows if row.weight > 0]
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
			primary = random.choices(candidates, weights=[k.weight for k in candidates], k=1)[0]
			fallbacks = sorted(
				[k for k in candidates if k is not primary],
				key=lambda k: k.weight,
				reverse=True,
			)
			ordered = [primary, *fallbacks][: settings.MAX_PROVIDER_FALLBACK_ATTEMPTS + 1]
			return [decrypt(k.api_key_encrypted) for k in ordered]

		env_map = {
			"openai": settings.OPENAI_API_KEY,
			"anthropic": settings.ANTHROPIC_API_KEY,
			"azure": settings.AZURE_API_KEY,
		}
		api_key = env_map.get(provider, "")
		if api_key:
			return [api_key]

		raise HTTPException(
			status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
			detail={"error": "no_provider_key", "detail": "No active key for provider"},
		)

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
	) -> None:
		background_tasks.add_task(
			log_request,
			redis=redis,
			request_id=request_id,
			org_id=user.org_id,
			user_id=user.id,
			api_key_id=api_key.id,
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
		ctx.policy_config = await policy_store.load(ctx.user.org_id, db, ctx.redis)
		decision = await policy_service.evaluate_chat_request(ctx.request, ctx.policy_config)
		ctx.policy_metadata = decision.as_metadata()

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
				request_metadata=ctx.policy_metadata,
				labels=ctx.labels,
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
				request_metadata=ctx.policy_metadata,
				labels=ctx.labels,
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
				db, ctx.user.org_id, ctx.provider, model=ctx.model_name,
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
		candidate_keys: list[str],
		call_fn: Callable[[str], Coroutine[Any, Any, Any]],
		model_label: str,
		tag: str = "",
	) -> tuple[Any, int]:
		"""Iterate candidate keys, calling *call_fn(key)* for each.

		Returns (response, fallback_count).  Retryable exceptions cause
		fallback to the next key; non-retryable exceptions propagate.
		"""
		if not candidate_keys:
			raise HTTPException(
				status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
				detail={"error": "no_provider_key", "detail": "No provider keys available"},
			)
		response = None
		last_exc: Exception | None = None
		fallback_count = 0
		for idx, key in enumerate(candidate_keys):
			if idx > 0:
				fallback_count += 1
				logger.warning("provider fallback%s attempt=%d model=%s", tag, idx + 1, model_label)
			try:
				response = await call_fn(key)
				break
			except HTTPException:
				raise
			except Exception as exc:
				if _is_retryable(exc) and idx < len(candidate_keys) - 1:
					last_exc = exc
					continue
				raise
		if response is None:
			raise last_exc  # type: ignore[misc]
		return response, fallback_count

	async def _handle_streaming_response(self, ctx: _RequestContext) -> StreamingResponse:
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
		except Exception:
			pass

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

		(stream, first_chunk), fb_count = await self._execute_with_fallback(
			ctx.candidate_keys, _stream_call, ctx.request.model, tag=" (stream)",
		)
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
				latency_ms, 200, ttft_ms=ttft_ms, request_metadata=ctx.policy_metadata, labels=ctx.labels,
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
		# Cache check — failure must never block a real LLM call
		try:
			cache_messages = [
				m.model_dump() if hasattr(m, "model_dump") else m
				for m in ctx.request.messages
			]
			cache_temperature = getattr(ctx.request, "temperature", None)
			cached_body = await cache_service.get(ctx.redis, ctx.request.model, cache_messages, cache_temperature)
			if cached_body is not None:
				cached_usage = cached_body.get("usage", {}) if isinstance(cached_body, dict) else {}
				cached_prompt = int(cached_usage.get("prompt_tokens", 0))
				cached_completion = int(cached_usage.get("completion_tokens", 0))
				cached_cost = cost_tracker_service.calculate_cost_usd(cached_body)
				cached_latency = int((time.perf_counter() - ctx.start) * 1000)
				self._schedule_log(
					ctx.background_tasks, ctx.redis, ctx.request_id, ctx.user, ctx.api_key,
					ctx.request.model, ctx.provider, cached_prompt, cached_completion, cached_cost,
					cached_latency, 200, request_metadata=ctx.policy_metadata, labels=ctx.labels,
				)
				return JSONResponse(
					content=cached_body,
					headers={
						"X-OpenProxyAI-Request-Id": str(ctx.request_id),
						"X-OpenProxyAI-Provider": ctx.provider,
						"X-OpenProxyAI-Model": ctx.request.model,
						"X-OpenProxyAI-Cost-USD": f"{cached_cost:.6f}",
						"X-OpenProxyAI-Latency-Ms": str(cached_latency),
						"X-OpenProxyAI-Cache": "hit",
						"X-OpenProxyAI-Gateway-Error": "false",
						**ctx.rl_headers,
					},
				)
		except Exception:
			pass

		async def _call(key: str) -> Any:
			call_kwargs = {**ctx.kwargs, "api_key": key}
			return await acompletion(**call_kwargs)

		response, fb_count = await self._execute_with_fallback(
			ctx.candidate_keys, _call, ctx.request.model,
		)
		if fb_count > 0:
			ctx.policy_metadata = {**(ctx.policy_metadata or {}), "fallback_count": fb_count}

		if ctx.policy_config.response_guardrails_enabled:
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
				cache_service.set(ctx.redis, ctx.request.model, cache_messages, cache_temperature, body)
			)

		self._schedule_log(
			ctx.background_tasks, ctx.redis, ctx.request_id, ctx.user, ctx.api_key,
			ctx.request.model, ctx.provider, prompt_tokens, completion_tokens, cost,
			latency_ms, 200, request_metadata=ctx.policy_metadata, labels=ctx.labels,
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
		ctx = _RequestContext(
			request=request,
			user=user,
			api_key=api_key,
			request_id=request_id,
			background_tasks=background_tasks,
			redis=redis,
			labels=_parse_labels(http_request) if http_request is not None else None,
			start=time.perf_counter(),
		)
		try:
			early = await self._build_litellm_kwargs(ctx, db)
			if early is not None:
				return early
			if request.stream:
				return await self._handle_streaming_response(ctx)
			return await self._handle_non_streaming_response(ctx, db)

		except HTTPException as exc:
			latency_ms = int((time.perf_counter() - ctx.start) * 1000)
			await log_request(
				redis=redis,
				request_id=request_id,
				org_id=user.org_id,
				user_id=user.id,
				api_key_id=api_key.id,
				model=request.model,
				provider=ctx.provider,
				prompt_tokens=0,
				completion_tokens=0,
				cost_usd=Decimal("0"),
				latency_ms=latency_ms,
				ttft_ms=None,
				status_code=exc.status_code,
				error_message=str(exc.detail),
				request_metadata=ctx.policy_metadata,
				labels=ctx.labels,
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
				request.model, ctx.provider, 0, 0, Decimal("0"),
				latency_ms, 504, error_message=str(exc),
				request_metadata=ctx.policy_metadata, labels=ctx.labels,
			)
			raise HTTPException(
				status_code=504,
				detail={"error": "provider_timeout", "detail": str(exc)},
				headers=ctx.rl_headers,
			) from exc
		except Exception as exc:
			latency_ms = int((time.perf_counter() - ctx.start) * 1000)
			logger.error("Provider error for request %s model=%s: %s", request_id, request.model, exc)
			self._schedule_log(
				background_tasks, redis, request_id, user, api_key,
				request.model, ctx.provider, 0, 0, Decimal("0"),
				latency_ms, 502, error_message=str(exc),
				request_metadata=ctx.policy_metadata, labels=ctx.labels,
			)
			raise HTTPException(
				status_code=502,
				detail={"error": "provider_error", "detail": "Upstream provider error"},
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
		start = time.perf_counter()
		provider = "unknown"
		rl_headers: dict[str, str] = {}
		policy_metadata: dict | None = None
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
					request_metadata=policy_metadata, labels=labels,
				)
				return self._policy_block_response(decision)
			size = len(request.input) if isinstance(request.input, list) else len(request.input)
			ok, rl_headers, limit_type, limit_detail, retry_after = await rate_limiter_service.check_limits(
				redis=redis, org_id=str(user.org_id), user_id=str(user.id),
				request_tokens_estimate=max(size // 4, 1),
				max_rpm=settings.DEFAULT_RATE_LIMIT_RPM, max_tpm=settings.DEFAULT_RATE_LIMIT_TPM,
				max_daily_budget_usd=Decimal(str(settings.DEFAULT_BUDGET_DAILY_USD)),
				user_daily_budget_usd=getattr(user, "budget_daily_usd", None),
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
					request_metadata=policy_metadata, labels=labels,
				)
				return JSONResponse(
					status_code=429,
					content={"error": "rate_limit_exceeded", "limit_type": limit_type, "detail": limit_detail, "retry_after": retry_after},
					headers={**rl_headers, "X-OpenProxyAI-Gateway-Error": "true"},
				)

			try:
				candidate_keys = await self._select_provider_keys(db, user.org_id, provider, model=model_name)
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

			response, fb_count = await self._execute_with_fallback(
				candidate_keys, _emb_call, request.model, tag=" (embed)",
			)
			if fb_count > 0:
				if policy_metadata is not None:
					policy_metadata["fallback_count"] = fb_count
				else:
					policy_metadata = {"fallback_count": fb_count}

			body = _to_jsonable(response)
			usage = body.get("usage", {}) if isinstance(body, dict) else {}
			prompt_tokens = int(usage.get("prompt_tokens", usage.get("total_tokens", 0)))
			cost = cost_tracker_service.calculate_cost_usd(response)
			latency_ms = int((time.perf_counter() - start) * 1000)

			self._schedule_log(
				background_tasks, redis, request_id, user, api_key,
				request.model, provider, prompt_tokens, 0, cost,
				latency_ms, 200, request_metadata=policy_metadata, labels=labels,
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
				error_message=str(exc.detail), request_metadata=policy_metadata, labels=labels,
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
				request_metadata=policy_metadata, labels=labels,
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
				request_metadata=policy_metadata, labels=labels,
			)
			raise HTTPException(
				status_code=502,
				detail={"error": "provider_error", "detail": "Upstream provider error"},
				headers=rl_headers,
			) from exc


llm_service = LLMService()
