"""The admission steps every endpoint shares, chat included: policy -> classify -> route -> refusals -> rate limit.

Chat and the other endpoints differ in what they hand in (a chat request is scanned with its tools and messages, a rerank with its
documents; chat resolves experiments and tool taint, the others do not), so each passes small callables for those parts. What
must never differ is the *order* and the *outcomes*, and those live here once:

1. the org's policy is loaded and the request evaluated
2. the request is classified
3. routing is decided (when the org has it on)
4. ``between`` runs (team lookup, which may itself refuse with a 404/403, before any refusal is answered)
5. a policy block is refused (446), then a routing block (446): neither spends rate-limit budget
6. the rate limits are checked (429)

Callers log the refusal in their own way: the gate returns what to answer and the error to record, it writes nothing.
Key choice and the provider call stay with the caller.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.services import llm_service as ls
from app.services.policy_service import PolicyDecision, policy_store
from app.services.rate_limiter import rate_limiter_service
from app.services.stage_timing import StageTimer


@dataclass
class Gate:
	config: Any = None
	decision: PolicyDecision | None = None
	classification: Any = None
	routing: Any = None
	rl_headers: dict[str, str] | None = None
	refusal: JSONResponse | None = None  # when set, answer with this and do not call the provider
	error: str | None = None  # what to record in the audit row for that refusal


async def admit(
	*,
	db: AsyncSession,
	redis: Redis,
	user: Any,
	model_of: Callable[[], str],  # read when the limits are checked: routing may have settled on a different model by then
	timer: StageTimer,
	evaluate: Callable[[Any], Awaitable[PolicyDecision]],
	classify: Callable[[Any], Awaitable[Any]],
	route: Callable[[Any, Any], Awaitable[Any]],
	between: Callable[[Any, Any, Any], Awaitable[Decimal | None]],
	estimate_tokens: int,
	team_id: uuid.UUID | None,
) -> Gate:
	gate = Gate()
	with timer.stage("policy"):
		gate.config = await policy_store.load(user.org_id, db, redis)
		gate.decision = await evaluate(gate.config)
	with timer.stage("classify"):
		gate.classification = await classify(gate.config)
	if gate.config.routing_mode != "off":
		with timer.stage("route"):
			gate.routing = await route(gate.config, gate.classification)
	team_budget = await between(gate.config, gate.classification, gate.routing)
	if not gate.decision.allowed:
		gate.refusal, gate.error = ls.LLMService._policy_block_response(gate.decision), f"policy_blocked:{gate.decision.reason_code}"
		return gate
	if gate.routing is not None and gate.routing.blocked:
		gate.refusal, gate.error = ls.LLMService._routing_block_response(gate.routing), "policy_blocked:no_authorized_model"
		return gate
	with timer.stage("rate_limit"):
		ok, headers, limit_type, limit_detail, retry_after = await rate_limiter_service.check_limits(
			redis=redis, org_id=str(user.org_id), user_id=str(user.id), request_tokens_estimate=max(estimate_tokens, 1),
			max_rpm=settings.DEFAULT_RATE_LIMIT_RPM, max_tpm=settings.DEFAULT_RATE_LIMIT_TPM,
			max_daily_budget_usd=Decimal(str(settings.DEFAULT_BUDGET_DAILY_USD)), user_daily_budget_usd=getattr(user, "budget_daily_usd", None),
			team_id=str(team_id) if team_id else None, team_budget_monthly_usd=team_budget, model=model_of(), policy_config=gate.config,
		)
	gate.rl_headers = {**headers, "X-OpenProxyAI-Data-Class": gate.classification.data_class, **ls.LLMService._route_headers(gate.routing)}
	if not ok:
		gate.error = f"rate_limited:{limit_type}"
		gate.refusal = JSONResponse(
			status_code=429,
			content={"error": "rate_limit_exceeded", "limit_type": limit_type, "detail": limit_detail, "retry_after": retry_after},
			headers={**gate.rl_headers, "X-OpenProxyAI-Gateway-Error": "true"},
		)
	return gate
