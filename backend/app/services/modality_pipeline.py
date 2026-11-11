"""One request pipeline for every non-chat endpoint (Phase 5, slice 1): embeddings, rerank, images, audio, responses.

The sequence is the part that must never differ between endpoints, so it lives once:

  model -> policy -> classify -> (refuse) -> routing -> (refuse) -> rate limit -> key choice -> call with fallback
        -> usage and cost -> audit row -> response

What does differ is small, and an endpoint states it as a ``Modality``: the text policy and classification must see, how to
size the request for rate limiting, how to make the provider call, and how to read usage back. Nothing a modality supplies
can skip a step: it is only ever asked for text, a size, a call and a usage reading.

Chat is not moved onto this: streaming, tools, the cache and experiments make it a different shape.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from fastapi import BackgroundTasks, HTTPException, Request
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.api_key import ApiKey
from app.models.team import Team, team_members
from app.models.user import User
from app.services import llm_service as ls
from app.services.classification_service import DATA_CLASS_HEADER, Classification, InvalidDataClass, classify_text
from app.services.cost_tracker import cost_tracker_service
from app.services.policy_service import POLICY_BLOCK_STATUS, policy_service, policy_store
from app.services.provider_client import ProviderEndpoint
from app.services.rate_limiter import rate_limiter_service
from app.services.routing_service import RoutingDecision
from app.services.stage_timing import timer_for_request
from app.utils.logging import get_logger

logger = get_logger(__name__)

CallFn = Callable[[Any, str, ProviderEndpoint | None], Awaitable[Any]]


@dataclass(frozen=True)
class Modality:
	"""What an endpoint tells the pipeline. Everything else about a request is the pipeline's business."""

	name: str  # for log messages
	fallback_tag: str  # appended to the model in fallback log lines
	text_of: Callable[[Any], str | None]  # the text policy and classification must see; None = could not be read (treated as unscanned)
	estimate_tokens: Callable[[Any], int]  # sizes the request for rate limiting
	call: CallFn  # (request, api_key, endpoint) -> provider response
	usage: Callable[[dict], tuple[int, int] | None]  # provider body -> (prompt, completion) tokens, or None when it reported none
	model_of: Callable[[Any], str] = lambda request: request.model


async def _team_budget(db: AsyncSession, user: User, team_id: uuid.UUID) -> Decimal | None:
	team = await db.scalar(select(Team).where(Team.id == team_id, Team.org_id == user.org_id))
	if team is None:
		raise HTTPException(status_code=404, detail="Team not found")
	member = await db.execute(select(team_members).where(team_members.c.team_id == team_id, team_members.c.user_id == user.id))
	if member.first() is None:
		raise HTTPException(status_code=403, detail="User is not a member of this team")
	return team.budget_monthly_usd


async def run_modality(
	modality: Modality,
	request: Any,
	*,
	db: AsyncSession,
	redis: Redis,
	user: User,
	api_key: ApiKey,
	request_id: uuid.UUID,
	background_tasks: BackgroundTasks,
	http_request: Request | None = None,
) -> JSONResponse:
	model = modality.model_of(request)
	labels = ls._parse_labels(http_request) if http_request is not None else None
	session_id = ls._parse_session_id_header(http_request) if http_request is not None else None
	team_id = getattr(api_key, "team_id", None) or (ls._parse_team_id(http_request) if http_request is not None else None)
	team_budget: Decimal | None = await _team_budget(db, user, team_id) if team_id is not None else None

	start = time.perf_counter()
	provider = "unknown"
	rl_headers: dict[str, str] = {}
	policy_metadata: dict | None = None
	timer = timer_for_request(http_request, start)
	classification: Classification | None = None
	routing: RoutingDecision | None = None

	def metadata(meta: dict | None) -> dict:
		out = {**(meta or {})}
		if classification is not None:
			out["data_class"] = classification.as_metadata()
		if routing is not None:
			out["routing"] = routing.as_metadata()
		stages = timer.as_list()
		if stages:
			out["stages"] = stages
		if session_id:
			out["session_id"] = session_id
		return out

	def refuse_log(status_code: int, error: str) -> None:
		background_tasks.add_task(
			ls.log_request, redis=redis, request_id=request_id, org_id=user.org_id, user_id=user.id, api_key_id=api_key.id,
			model=model, provider=provider, prompt_tokens=0, completion_tokens=0, cost_usd=Decimal("0"),
			latency_ms=int((time.perf_counter() - start) * 1000), ttft_ms=None, status_code=status_code, error_message=error,
			request_metadata=metadata(policy_metadata), labels=labels, team_id=team_id,
		)

	try:
		provider, model_name = ls.split_model(model)
		text = modality.text_of(request)
		with timer.stage("policy"):
			policy_config = await policy_store.load(user.org_id, db, redis)
			decision = await policy_service.evaluate_text_request(model, text or "", policy_config)
		policy_metadata = decision.as_metadata()
		with timer.stage("classify"):
			try:
				classification = await classify_text(text, policy_config, http_request.headers.get(DATA_CLASS_HEADER) if http_request is not None else None)
			except InvalidDataClass as exc:
				raise HTTPException(status_code=400, detail={"error": "invalid_data_class", "detail": str(exc)}) from exc
		if not decision.allowed:
			refuse_log(POLICY_BLOCK_STATUS, f"policy_blocked:{decision.reason_code}")
			return ls.LLMService._policy_block_response(decision)
		if policy_config.routing_mode != "off":
			with timer.stage("route"):
				candidates, region = await ls.llm_service.routing_inputs(db, user.org_id)
				routing = ls.route_decision(candidates, region, policy_config, classification.data_class, model)
			if routing.blocked:
				refuse_log(POLICY_BLOCK_STATUS, "policy_blocked:no_authorized_model")
				return ls.LLMService._routing_block_response(routing)
		with timer.stage("rate_limit"):
			ok, rl_headers, limit_type, limit_detail, retry_after = await rate_limiter_service.check_limits(
				redis=redis, org_id=str(user.org_id), user_id=str(user.id), request_tokens_estimate=max(modality.estimate_tokens(request), 1),
				max_rpm=settings.DEFAULT_RATE_LIMIT_RPM, max_tpm=settings.DEFAULT_RATE_LIMIT_TPM,
				max_daily_budget_usd=Decimal(str(settings.DEFAULT_BUDGET_DAILY_USD)), user_daily_budget_usd=getattr(user, "budget_daily_usd", None),
				team_id=str(team_id) if team_id else None, team_budget_monthly_usd=team_budget, model=model, policy_config=policy_config,
			)
		rl_headers = {**rl_headers, "X-OpenProxyAI-Data-Class": classification.data_class, **ls.LLMService._route_headers(routing)}
		if not ok:
			refuse_log(429, f"rate_limited:{limit_type}")
			return JSONResponse(
				status_code=429,
				content={"error": "rate_limit_exceeded", "limit_type": limit_type, "detail": limit_detail, "retry_after": retry_after},
				headers={**rl_headers, "X-OpenProxyAI-Gateway-Error": "true"},
			)

		retries_override = ls._parse_retries_header(http_request) if http_request is not None else None
		try:
			candidate_keys = await ls.llm_service._select_provider_keys(
				db, user.org_id, provider, model=model_name, redis=redis, max_attempts=retries_override,
				only_key_id=routing.key_id if routing is not None and routing.mode == "enforce" else None,
			)
		except HTTPException as exc:
			raise HTTPException(status_code=exc.status_code, detail=exc.detail, headers={**rl_headers, **(exc.headers or {})}) from exc

		async def call(key: str, endpoint: ProviderEndpoint | None = None) -> Any:
			return await modality.call(request, key, endpoint)

		with timer.stage("upstream"):
			response, fallback_count, provider_key_id = await ls.llm_service._execute_with_fallback(
				candidate_keys, call, model, tag=modality.fallback_tag, redis=redis
			)
		if fallback_count > 0:
			policy_metadata = {**(policy_metadata or {}), "fallback_count": fallback_count}

		body = ls._to_jsonable(response)
		reported = modality.usage(body if isinstance(body, dict) else {})
		prompt_tokens, completion_tokens = reported if reported is not None else (max(modality.estimate_tokens(request), 0), 0)
		try:
			cost = cost_tracker_service.calculate_cost_usd(response)
		except Exception as exc:  # an unpriced model must not turn a call that already succeeded (and was paid for) into an error
			logger.warning("Could not price %s call to %s: %s", modality.name, model, exc)
			cost = Decimal("0")
			policy_metadata = {**(policy_metadata or {}), "cost_unknown": True}
		latency_ms = int((time.perf_counter() - start) * 1000)
		ls.LLMService._schedule_log(
			background_tasks, redis, request_id, user, api_key, model, provider, prompt_tokens, completion_tokens, cost, latency_ms, 200,
			request_metadata=metadata(policy_metadata), labels=labels, team_id=team_id, provider_key_id=provider_key_id,
		)
		return JSONResponse(
			content=body,
			headers={
				"X-OpenProxyAI-Request-Id": str(request_id), "X-OpenProxyAI-Provider": provider, "X-OpenProxyAI-Model": model,
				"X-OpenProxyAI-Cost-USD": f"{cost:.6f}", "X-OpenProxyAI-Latency-Ms": str(latency_ms), "X-OpenProxyAI-Gateway-Error": "false",
				**rl_headers,
			},
		)
	except HTTPException as exc:
		ls._log_detached(
			redis=redis, request_id=request_id, org_id=user.org_id, user_id=user.id, api_key_id=api_key.id, model=model, provider=provider,
			prompt_tokens=0, completion_tokens=0, cost_usd=Decimal("0"), latency_ms=int((time.perf_counter() - start) * 1000), ttft_ms=None,
			status_code=exc.status_code, error_message=str(exc.detail), request_metadata=metadata(policy_metadata), labels=labels, team_id=team_id,
		)
		if rl_headers:
			raise HTTPException(status_code=exc.status_code, detail=exc.detail, headers={**rl_headers, **(exc.headers or {})}) from exc
		raise
	except TimeoutError as exc:
		ls.LLMService._schedule_log(
			background_tasks, redis, request_id, user, api_key, model, provider, 0, 0, Decimal("0"), int((time.perf_counter() - start) * 1000), 504,
			error_message=str(exc), request_metadata=metadata(policy_metadata), labels=labels, team_id=team_id,
		)
		raise HTTPException(status_code=504, detail={"error": "provider_timeout", "detail": str(exc)}, headers=rl_headers) from exc
	except Exception as exc:
		logger.error("Provider error for %s %s model=%s: %s", modality.name, request_id, model, exc)
		ls.LLMService._schedule_log(
			background_tasks, redis, request_id, user, api_key, model, provider, 0, 0, Decimal("0"), int((time.perf_counter() - start) * 1000), 502,
			error_message=str(exc), request_metadata=metadata(policy_metadata), labels=labels, team_id=team_id,
		)
		raise HTTPException(
			status_code=502, detail={"error": "provider_error", "detail": ls._provider_error_public_detail(exc)}, headers=rl_headers
		) from exc
