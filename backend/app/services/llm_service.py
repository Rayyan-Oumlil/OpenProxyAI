"""LiteLLM wrapper — acompletion, cost calculation, streaming with capture."""

import json
import random
import time
import uuid
from collections.abc import AsyncGenerator
from decimal import Decimal
from typing import Any

from fastapi import BackgroundTasks, HTTPException, status
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
from app.services.audit_logger import log_request
from app.services.cost_tracker import cost_tracker_service
from app.services.crypto_service import decrypt
from app.services.policy_service import PolicyDecision, policy_service, policy_store
from app.services.rate_limiter import rate_limiter_service
from app.utils.token_estimator import estimate_tokens


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


class LLMService:
	async def _select_provider_key(
		self,
		db: AsyncSession,
		org_id: uuid.UUID,
		provider: str,
	) -> str:
		rows = await db.scalars(
			select(LLMProviderKey).where(
				LLMProviderKey.org_id == org_id,
				LLMProviderKey.provider == provider,
				LLMProviderKey.is_active.is_(True),
			)
		)
		keys = [row for row in rows if row.weight > 0]
		if keys:
			selected = random.choices(keys, weights=[k.weight for k in keys], k=1)[0]
			return decrypt(selected.api_key_encrypted)

		env_map = {
			"openai": settings.OPENAI_API_KEY,
			"anthropic": settings.ANTHROPIC_API_KEY,
			"azure": settings.AZURE_API_KEY,
		}
		api_key = env_map.get(provider, "")
		if api_key:
			return api_key

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

	async def chat_completion(
		self,
		request: ChatCompletionRequest,
		db: AsyncSession,
		redis: Redis,
		user: User,
		api_key: ApiKey,
		request_id: uuid.UUID,
		background_tasks: BackgroundTasks,
	):
		start = time.perf_counter()
		provider = "unknown"
		rl_headers: dict[str, str] = {}
		policy_metadata: dict | None = None
		try:
			provider, model_name = _split_model(request.model)
			policy_config = await policy_store.load(user.org_id, db, redis)
			decision = policy_service.evaluate_chat_request(request, policy_config)
			policy_metadata = decision.as_metadata()
			if not decision.allowed:
				latency_ms = int((time.perf_counter() - start) * 1000)
				await log_request(
					redis=redis,
					request_id=request_id,
					org_id=user.org_id,
					user_id=user.id,
					api_key_id=api_key.id,
					model=request.model,
					provider=provider,
					prompt_tokens=0,
					completion_tokens=0,
					cost_usd=Decimal("0"),
					latency_ms=latency_ms,
					ttft_ms=None,
					status_code=403,
					error_message=f"policy_blocked:{decision.reason_code}",
					request_metadata=policy_metadata,
				)
				return self._policy_block_response(decision)

			ok, rl_headers, limit_type, limit_detail, retry_after = await rate_limiter_service.check_limits(
				redis=redis,
				org_id=str(user.org_id),
				user_id=str(user.id),
				request_tokens_estimate=estimate_tokens(request),
				max_rpm=settings.DEFAULT_RATE_LIMIT_RPM,
				max_tpm=settings.DEFAULT_RATE_LIMIT_TPM,
				max_daily_budget_usd=Decimal(str(settings.DEFAULT_BUDGET_DAILY_USD)),
				user_daily_budget_usd=getattr(user, "budget_daily_usd", None),
			)
			if not ok:
				latency_ms = int((time.perf_counter() - start) * 1000)
				await log_request(
					redis=redis,
					request_id=request_id,
					org_id=user.org_id,
					user_id=user.id,
					api_key_id=api_key.id,
					model=request.model,
					provider=provider,
					prompt_tokens=0,
					completion_tokens=0,
					cost_usd=Decimal("0"),
					latency_ms=latency_ms,
					ttft_ms=None,
					status_code=429,
					error_message=f"rate_limited:{limit_type}",
					request_metadata=policy_metadata,
				)
				return JSONResponse(
					status_code=429,
					content={
						"error": "rate_limit_exceeded",
						"limit_type": limit_type,
						"detail": limit_detail,
						"retry_after": retry_after,
					},
					headers={**rl_headers, "X-OpenProxyAI-Gateway-Error": "true"},
				)

			try:
				provider_api_key = await self._select_provider_key(db, user.org_id, provider)
			except HTTPException as exc:
				raise HTTPException(
					status_code=exc.status_code,
					detail=exc.detail,
					headers={**rl_headers, **(exc.headers or {})},
				) from exc

			kwargs = request.model_dump(exclude_none=True)
			kwargs.update(
				{
					"model": request.model,
					"api_key": provider_api_key,
					"timeout": 30,
					"request_timeout": 30,
				}
			)

			if request.stream:
				kwargs["stream"] = True
				stream = await acompletion(**kwargs)
				first_chunk = await stream.__anext__()
				if getattr(first_chunk, "error", None) is not None:
					raise HTTPException(
						status_code=502,
						detail={"error": "provider_error", "detail": str(first_chunk.error)},
					)

				ttft_ms = int((time.perf_counter() - start) * 1000)
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
					async for chunk in stream:
						chunk_payload = _to_jsonable(chunk)
						if isinstance(chunk_payload, dict):
							_update_usage(chunk_payload)
						yield f"data: {json.dumps(chunk_payload)}\n\n"
					yield "data: [DONE]\n\n"
					latency_ms = int((time.perf_counter() - start) * 1000)
					cost = Decimal("0")
					if prompt_tokens > 0 or completion_tokens > 0:
						cost_response = {
							"model": request.model,
							"usage": {
								"prompt_tokens": prompt_tokens,
								"completion_tokens": completion_tokens,
								"total_tokens": prompt_tokens + completion_tokens,
							},
						}
						cost = cost_tracker_service.calculate_cost_usd(cost_response)
					self._schedule_log(
						background_tasks,
						redis,
						request_id,
						user,
						api_key,
						request.model,
						provider,
						prompt_tokens,
						completion_tokens,
						cost,
						latency_ms,
						200,
						ttft_ms=ttft_ms,
						request_metadata=policy_metadata,
					)

				return StreamingResponse(
					event_stream(),
					media_type="text/event-stream",
					headers={
						"X-OpenProxyAI-Request-Id": str(request_id),
						"X-OpenProxyAI-Provider": provider,
						"X-OpenProxyAI-Model": request.model,
						"X-OpenProxyAI-Cost-USD": "0.000000",
						"X-OpenProxyAI-TTFT-Ms": str(ttft_ms),
						"X-OpenProxyAI-Gateway-Error": "false",
						**rl_headers,
					},
				)

			response = await acompletion(**kwargs)
			body = _to_jsonable(response)
			usage = body.get("usage", {}) if isinstance(body, dict) else {}
			prompt_tokens = int(usage.get("prompt_tokens", 0))
			completion_tokens = int(usage.get("completion_tokens", 0))
			cost = cost_tracker_service.calculate_cost_usd(response)
			latency_ms = int((time.perf_counter() - start) * 1000)

			self._schedule_log(
				background_tasks,
				redis,
				request_id,
				user,
				api_key,
				request.model,
				provider,
				prompt_tokens,
				completion_tokens,
				cost,
				latency_ms,
				200,
				request_metadata=policy_metadata,
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
				redis=redis,
				request_id=request_id,
				org_id=user.org_id,
				user_id=user.id,
				api_key_id=api_key.id,
				model=request.model,
				provider=provider,
				prompt_tokens=0,
				completion_tokens=0,
				cost_usd=Decimal("0"),
				latency_ms=latency_ms,
				ttft_ms=None,
				status_code=exc.status_code,
				error_message=str(exc.detail),
				request_metadata=policy_metadata,
			)
			if rl_headers:
				raise HTTPException(
					status_code=exc.status_code,
					detail=exc.detail,
					headers={**rl_headers, **(exc.headers or {})},
				) from exc
			raise
		except TimeoutError as exc:
			latency_ms = int((time.perf_counter() - start) * 1000)
			self._schedule_log(
				background_tasks,
				redis,
				request_id,
				user,
				api_key,
				request.model,
				provider,
				0,
				0,
				Decimal("0"),
				latency_ms,
				504,
				error_message=str(exc),
				request_metadata=policy_metadata,
			)
			raise HTTPException(
				status_code=504,
				detail={"error": "provider_timeout", "detail": str(exc)},
				headers=rl_headers,
			) from exc
		except Exception as exc:
			latency_ms = int((time.perf_counter() - start) * 1000)
			self._schedule_log(
				background_tasks,
				redis,
				request_id,
				user,
				api_key,
				request.model,
				provider,
				0,
				0,
				Decimal("0"),
				latency_ms,
				502,
				error_message=str(exc),
				request_metadata=policy_metadata,
			)
			raise HTTPException(
				status_code=502,
				detail={"error": "provider_error", "detail": str(exc)},
				headers=rl_headers,
			) from exc

	async def embedding(
		self,
		request: EmbeddingRequest,
		db: AsyncSession,
		redis: Redis,
		user: User,
		api_key: ApiKey,
		request_id: uuid.UUID,
		background_tasks: BackgroundTasks,
	) -> JSONResponse:
		start = time.perf_counter()
		provider = "unknown"
		rl_headers: dict[str, str] = {}
		policy_metadata: dict | None = None
		try:
			provider, model_name = _split_model(request.model)
			policy_config = await policy_store.load(user.org_id, db, redis)
			decision = policy_service.evaluate_embedding_request(request, policy_config)
			policy_metadata = decision.as_metadata()
			if not decision.allowed:
				latency_ms = int((time.perf_counter() - start) * 1000)
				await log_request(
					redis=redis,
					request_id=request_id,
					org_id=user.org_id,
					user_id=user.id,
					api_key_id=api_key.id,
					model=request.model,
					provider=provider,
					prompt_tokens=0,
					completion_tokens=0,
					cost_usd=Decimal("0"),
					latency_ms=latency_ms,
					ttft_ms=None,
					status_code=403,
					error_message=f"policy_blocked:{decision.reason_code}",
					request_metadata=policy_metadata,
				)
				return self._policy_block_response(decision)
			size = len(request.input) if isinstance(request.input, list) else len(request.input)
			ok, rl_headers, limit_type, limit_detail, retry_after = await rate_limiter_service.check_limits(
				redis=redis,
				org_id=str(user.org_id),
				user_id=str(user.id),
				request_tokens_estimate=max(size // 4, 1),
				max_rpm=settings.DEFAULT_RATE_LIMIT_RPM,
				max_tpm=settings.DEFAULT_RATE_LIMIT_TPM,
				max_daily_budget_usd=Decimal(str(settings.DEFAULT_BUDGET_DAILY_USD)),
				user_daily_budget_usd=getattr(user, "budget_daily_usd", None),
			)
			if not ok:
				latency_ms = int((time.perf_counter() - start) * 1000)
				await log_request(
					redis=redis,
					request_id=request_id,
					org_id=user.org_id,
					user_id=user.id,
					api_key_id=api_key.id,
					model=request.model,
					provider=provider,
					prompt_tokens=0,
					completion_tokens=0,
					cost_usd=Decimal("0"),
					latency_ms=latency_ms,
					ttft_ms=None,
					status_code=429,
					error_message=f"rate_limited:{limit_type}",
					request_metadata=policy_metadata,
				)
				return JSONResponse(
					status_code=429,
					content={
						"error": "rate_limit_exceeded",
						"limit_type": limit_type,
						"detail": limit_detail,
						"retry_after": retry_after,
					},
					headers={**rl_headers, "X-OpenProxyAI-Gateway-Error": "true"},
				)

			try:
				provider_api_key = await self._select_provider_key(db, user.org_id, provider)
			except HTTPException as exc:
				raise HTTPException(
					status_code=exc.status_code,
					detail=exc.detail,
					headers={**rl_headers, **(exc.headers or {})},
				) from exc

			response = await aembedding(
				model=request.model,
				input=request.input,
				api_key=provider_api_key,
				encoding_format=request.encoding_format,
				timeout=30,
			)
			body = _to_jsonable(response)
			usage = body.get("usage", {}) if isinstance(body, dict) else {}
			prompt_tokens = int(usage.get("prompt_tokens", usage.get("total_tokens", 0)))
			cost = cost_tracker_service.calculate_cost_usd(response)
			latency_ms = int((time.perf_counter() - start) * 1000)

			self._schedule_log(
				background_tasks,
				redis,
				request_id,
				user,
				api_key,
				request.model,
				provider,
				prompt_tokens,
				0,
				cost,
				latency_ms,
				200,
				request_metadata=policy_metadata,
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
				redis=redis,
				request_id=request_id,
				org_id=user.org_id,
				user_id=user.id,
				api_key_id=api_key.id,
				model=request.model,
				provider=provider,
				prompt_tokens=0,
				completion_tokens=0,
				cost_usd=Decimal("0"),
				latency_ms=latency_ms,
				ttft_ms=None,
				status_code=exc.status_code,
				error_message=str(exc.detail),
				request_metadata=policy_metadata,
			)
			if rl_headers:
				raise HTTPException(
					status_code=exc.status_code,
					detail=exc.detail,
					headers={**rl_headers, **(exc.headers or {})},
				) from exc
			raise
		except TimeoutError as exc:
			latency_ms = int((time.perf_counter() - start) * 1000)
			self._schedule_log(
				background_tasks,
				redis,
				request_id,
				user,
				api_key,
				request.model,
				provider,
				0,
				0,
				Decimal("0"),
				latency_ms,
				504,
				error_message=str(exc),
				request_metadata=policy_metadata,
			)
			raise HTTPException(
				status_code=504,
				detail={"error": "provider_timeout", "detail": str(exc)},
				headers=rl_headers,
			) from exc
		except Exception as exc:
			latency_ms = int((time.perf_counter() - start) * 1000)
			self._schedule_log(
				background_tasks,
				redis,
				request_id,
				user,
				api_key,
				request.model,
				provider,
				0,
				0,
				Decimal("0"),
				latency_ms,
				502,
				error_message=str(exc),
				request_metadata=policy_metadata,
			)
			raise HTTPException(
				status_code=502,
				detail={"error": "provider_error", "detail": str(exc)},
				headers=rl_headers,
			) from exc


llm_service = LLMService()

