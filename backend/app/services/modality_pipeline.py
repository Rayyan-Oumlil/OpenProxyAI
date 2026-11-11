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
from fastapi.responses import JSONResponse, Response
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
from app.services.policy_service import POLICY_BLOCK_STATUS, PolicyScanLimitExceeded, policy_service, policy_store
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
	# The request carries content that cannot be read (audio). Policy still scans ``text_of``, but classification treats the
	# request as uninspected, which the org's class map raises like any other "could not scan" (confidential by default).
	opaque_input: Callable[[Any], bool] = lambda request: False
	# Refuses a request the org's policy does not allow for this endpoint (raises HTTPException). Runs after the org's policy is loaded.
	check: Callable[[Any, Any], None] | None = None
	call_type: str | None = None  # LiteLLM's name for this kind of call, so it is priced as what it is
	units: Callable[[Any], int] = lambda request: 1  # how many billable units a call is (images), for the fallback price
	# For modalities whose answer is text (a transcript): the same response guardrails chat has. ``output_text`` reads it from the
	# provider body, ``with_output_text`` writes a redacted version back.
	output_text: Callable[[dict], str | None] | None = None
	with_output_text: Callable[[dict, Callable[[str], str]], dict] | None = None  # (body, redact) -> body with every text part redacted
	# For modalities whose answer is not JSON (speech): turns the provider response into the HTTP response.
	render: Callable[[Any, dict[str, str]], Response] | None = None


async def _team_budget(db: AsyncSession, user: User, team_id: uuid.UUID) -> Decimal | None:
	team = await db.scalar(select(Team).where(Team.id == team_id, Team.org_id == user.org_id))
	if team is None:
		raise HTTPException(status_code=404, detail="Team not found")
	member = await db.execute(select(team_members).where(team_members.c.team_id == team_id, team_members.c.user_id == user.id))
	if member.first() is None:
		raise HTTPException(status_code=403, detail="User is not a member of this team")
	return team.budget_monthly_usd


def _guard_output(modality: Modality, body: dict, config: Any) -> dict:
	"""The org's response guardrails on a text answer: a block is a 446 when enforcing (and only logged otherwise), PII is redacted
	when the org asked for redaction. The same rules chat applies to its answer."""
	text = modality.output_text(body) if modality.output_text else None
	if not text:
		return body
	decision = policy_service.evaluate_response(text, config)
	if not decision.allowed:
		if config.enforcement_mode.lower().strip() == "enforce":
			raise HTTPException(
				status_code=POLICY_BLOCK_STATUS,
				detail={"error": {"message": decision.reason_code or "Response blocked by policy", "code": "response_policy_violation"}},
			)
		logger.warning("response guardrail violation: reason=%s", decision.reason_code)
		return body
	if decision.redacted_text is not None and modality.with_output_text is not None:
		return modality.with_output_text(body, lambda text: policy_service._redact_pii(text, config))
	return body


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
		out = {**(meta or {}), "modality": modality.name}
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
		try:
			text = modality.text_of(request)
		except PolicyScanLimitExceeded:
			refuse_log(POLICY_BLOCK_STATUS, "policy_blocked:scan_limit_exceeded")
			return JSONResponse(
				status_code=POLICY_BLOCK_STATUS,
				content={"error": "policy_violation", "reason_code": "scan_limit_exceeded", "detail": "The request is too large to scan completely, so it was refused."},
				headers={"X-OpenProxyAI-Gateway-Error": "true", "X-OpenProxyAI-Policy-Action": "block"},
			)
		with timer.stage("policy"):
			policy_config = await policy_store.load(user.org_id, db, redis)
			if modality.check is not None:
				modality.check(request, policy_config)
			decision = await policy_service.evaluate_text_request(model, text or "", policy_config)
		policy_metadata = decision.as_metadata()
		with timer.stage("classify"):
			try:
				classification = await classify_text(None if modality.opaque_input(request) else text, policy_config, http_request.headers.get(DATA_CLASS_HEADER) if http_request is not None else None)
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

		body = {} if modality.render is not None else ls._to_jsonable(response)
		if modality.output_text is not None and policy_config.response_guardrails_enabled and isinstance(body, dict):
			body = _guard_output(modality, body, policy_config)
		reported = modality.usage(body if isinstance(body, dict) else {})
		prompt_tokens, completion_tokens = reported if reported is not None else (max(modality.estimate_tokens(request), 0), 0)
		try:
			cost = cost_tracker_service.calculate_cost_usd(response, call_type=modality.call_type)
		except Exception as exc:
			# An unpriced model must not turn a call that already succeeded into an error, and must not be free either (that would let
			# spend go uncounted against budgets): charge a flat fallback per unit and say it is an estimate.
			logger.warning("Could not price %s call to %s: %s", modality.name, model, exc)
			cost = Decimal(str(settings.UNPRICED_CALL_COST_USD)) * modality.units(request)
			policy_metadata = {**(policy_metadata or {}), "cost_estimated": True}
		latency_ms = int((time.perf_counter() - start) * 1000)
		ls.LLMService._schedule_log(
			background_tasks, redis, request_id, user, api_key, model, provider, prompt_tokens, completion_tokens, cost, latency_ms, 200,
			request_metadata=metadata(policy_metadata), labels=labels, team_id=team_id, provider_key_id=provider_key_id,
		)
		gateway_headers = {
			"X-OpenProxyAI-Request-Id": str(request_id), "X-OpenProxyAI-Provider": provider, "X-OpenProxyAI-Model": model,
			"X-OpenProxyAI-Cost-USD": f"{cost:.6f}", "X-OpenProxyAI-Latency-Ms": str(latency_ms), "X-OpenProxyAI-Gateway-Error": "false",
			**rl_headers,
		}
		if modality.render is not None:
			return modality.render(response, gateway_headers)
		return JSONResponse(content=body, headers=gateway_headers)
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
