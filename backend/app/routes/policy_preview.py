"""What would happen to this request? ``POST /api/v1/policy/preview`` (admins only).

It runs the same steps the gateway runs before it calls a provider (classify, policy, route) and stops there: no
upstream call, no audit row, nothing counted against rate limits or budgets, nothing cached. Routing is always
shown as enforce would decide it, so an org can see the effect before turning enforcement on. The decision itself
comes from the functions the real pipeline uses; e2e tests hold the two together.
"""

from __future__ import annotations

import dataclasses

from fastapi import APIRouter, Depends, HTTPException, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import CurrentUser, get_db, get_redis
from app.models.llm_provider_key import LLMProviderKey
from app.schemas.chat import ChatCompletionRequest
from app.schemas.policy_preview import (
	DataClassOut,
	FallbackOut,
	PolicyOut,
	PolicyPreviewRequest,
	PolicyPreviewResponse,
	RoutingOut,
)
from app.services.classification_service import classify_chat_request
from app.services.llm_service import llm_service, route_decision, split_model
from app.services.policy_service import policy_service, policy_store
from app.services.refusal_explanations import explain_policy
from app.services.routing_service import CAPABILITY_PREFIX

router = APIRouter(prefix="/api/v1/policy", tags=["Policy"])

# What a real request also goes through that a preview deliberately skips.
_NOT_EVALUATED = ["rate_limit", "budget", "cache", "experiments", "tool_taint", "upstream"]


@router.post("/preview", response_model=PolicyPreviewResponse)
async def preview_policy(
	payload: PolicyPreviewRequest,
	current_user: CurrentUser,
	db: AsyncSession = Depends(get_db),
	redis: Redis = Depends(get_redis),
) -> PolicyPreviewResponse:
	if current_user.role != "admin":
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only organization admins can preview policy")
	for model in (payload.model, payload.fallback_model):
		if model is not None and not model.startswith(CAPABILITY_PREFIX):
			split_model(model)  # the same 400 the real endpoint gives for a malformed model

	stored = await policy_store.load(current_user.org_id, db, redis)
	enforcing = dataclasses.replace(stored, routing_mode="enforce")  # preview what enforcement would do
	request = ChatCompletionRequest(model=payload.model, messages=payload.messages)

	try:
		classification = await classify_chat_request(request, enforcing, payload.data_class)
	except ValueError as exc:  # InvalidDataClass; the schema already rejects unknown classes, so this is defence in depth
		raise HTTPException(status_code=422, detail={"error": "invalid_data_class", "detail": str(exc)}) from exc
	policy = await policy_service.evaluate_chat_request(request, enforcing)

	candidates, region = await llm_service.routing_inputs(db, current_user.org_id, enforcing)
	decision = route_decision(candidates, region, enforcing, classification.data_class, payload.model)
	key = await db.get(LLMProviderKey, decision.key_id) if decision.key_id else None
	fallback = None
	if payload.fallback_model:
		fb = route_decision(candidates, region, enforcing, classification.data_class, payload.fallback_model)
		fallback = FallbackOut(model=fb.model or payload.fallback_model, authorized=fb.model is not None, reason=fb.reason)

	if not policy.allowed:
		verdict = "blocked_by_policy"
	elif decision.model is None:
		verdict = "blocked_by_routing" if stored.routing_mode == "enforce" else "would_block_if_enforced"
	else:
		verdict = "allowed"

	return PolicyPreviewResponse(
		verdict=verdict,
		data_class=DataClassOut(**{"class": classification.data_class, "source": classification.source, "entities": list(classification.entities)}),
		policy=PolicyOut(
			mode=stored.enforcement_mode, allowed=policy.allowed, action=policy.action, reason_code=policy.reason_code,
			detail=policy.detail, triggered_rules=list(policy.triggered_rules or []),
			explanation=None if policy.allowed else explain_policy(policy.reason_code),
		),
		routing=RoutingOut(
			current_mode=stored.routing_mode, requested=payload.model, model=decision.model, reason=decision.reason,
			authorized=list(decision.authorized), excluded=dict(decision.excluded), key_alias=key.key_alias if key is not None else None,
			explanation=decision.explanation,
		),
		fallback=fallback,
		not_evaluated=list(_NOT_EVALUATED),
	)
