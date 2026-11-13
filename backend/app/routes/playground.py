"""Prompt Playground — model comparison and saved prompt templates."""

import asyncio
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import CurrentUser, get_db, get_redis
from app.models.prompt_template import PromptTemplate
from app.schemas.playground import (
    PlaygroundCompareRequest,
    PlaygroundCompareResponse,
    PlaygroundCompareResult,
    PromptTemplateCreate,
    PromptTemplateResponse,
    PromptTemplateUpdate,
)
from app.services import behavior as behavior_mod
from app.services.classification_service import classify_chat_request
from app.services.llm_service import llm_service, split_model
from app.services.model_runner import CallPlan, RunOutcome, execute_plan, plan_call
from app.services.policy_service import POLICY_BLOCK_STATUS, policy_service, policy_store
from app.services.refusal_explanations import explain_policy
from app.services.rate_limiter import rate_limiter_service

router = APIRouter(prefix="/api/v1", tags=["Playground"])

_PLAYGROUND_WRITE_ROLES = frozenset({"admin", "developer"})
PLAYGROUND_TIMEOUT_SECONDS = 30


def _estimate_tokens_from_messages(messages: list[dict]) -> int:
    """Conservative token estimate for rate limiting."""
    content_chars = sum(len(str(m.get("content") or "")) for m in messages)
    return max(content_chars // 4, 1)


# ── Prompt Templates CRUD ────────────────────────────────────────────────


@router.post("/prompt-templates", response_model=PromptTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_prompt_template(
    payload: PromptTemplateCreate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> PromptTemplateResponse:
    if current_user.role not in _PLAYGROUND_WRITE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or developer role required",
        )

    # With the org's promotion gate on, nothing goes live without a passing eval run: a new template starts as a draft.
    gated = (await policy_store.load(current_user.org_id, db, redis)).prompt_promotion_gate
    template = PromptTemplate(
        org_id=current_user.org_id,
        name=payload.name,
        description=payload.description,
        system_message=payload.system_message,
        user_template=payload.user_template,
        variables_schema=[v.model_dump() for v in payload.variables_schema],
        version=1,
        is_active=not gated,
        status="draft" if gated else "active",
        created_by=current_user.id,
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)

    return PromptTemplateResponse(
        id=str(template.id),
        org_id=str(template.org_id),
        name=template.name,
        description=template.description,
        system_message=template.system_message,
        user_template=template.user_template,
        variables_schema=template.variables_schema or [],
        version=template.version,
        is_active=template.is_active,
        status=template.status,
        created_by=str(template.created_by) if template.created_by else None,
        created_at=template.created_at.isoformat(),
        updated_at=template.updated_at.isoformat(),
    )


@router.get("/prompt-templates", response_model=list[PromptTemplateResponse])
async def list_prompt_templates(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    page: int = 1,
    page_size: int = 50,
) -> list[PromptTemplateResponse]:
    offset = (page - 1) * page_size
    rows = await db.scalars(
        select(PromptTemplate)
        .where(
            PromptTemplate.org_id == current_user.org_id,
            PromptTemplate.status.in_(("active", "draft")),
        )
        .order_by(PromptTemplate.updated_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    return [
        PromptTemplateResponse(
            id=str(t.id),
            org_id=str(t.org_id),
            name=t.name,
            description=t.description,
            system_message=t.system_message,
            user_template=t.user_template,
            variables_schema=t.variables_schema or [],
            version=t.version,
            is_active=t.is_active,
            status=t.status,
            created_by=str(t.created_by) if t.created_by else None,
            created_at=t.created_at.isoformat(),
            updated_at=t.updated_at.isoformat(),
        )
        for t in rows
    ]


@router.get("/prompt-templates/{template_id}", response_model=PromptTemplateResponse)
async def get_prompt_template(
    template_id: UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> PromptTemplateResponse:
    template = await db.scalar(
        select(PromptTemplate).where(
            PromptTemplate.id == template_id,
            PromptTemplate.org_id == current_user.org_id,
        )
    )
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    return PromptTemplateResponse(
        id=str(template.id),
        org_id=str(template.org_id),
        name=template.name,
        description=template.description,
        system_message=template.system_message,
        user_template=template.user_template,
        variables_schema=template.variables_schema or [],
        version=template.version,
        is_active=template.is_active,
        status=template.status,
        created_by=str(template.created_by) if template.created_by else None,
        created_at=template.created_at.isoformat(),
        updated_at=template.updated_at.isoformat(),
    )


def _as_response(t: PromptTemplate) -> PromptTemplateResponse:
    return PromptTemplateResponse(
        id=str(t.id),
        org_id=str(t.org_id),
        name=t.name,
        description=t.description,
        system_message=t.system_message,
        user_template=t.user_template,
        variables_schema=t.variables_schema or [],
        version=t.version,
        is_active=t.is_active,
        status=t.status,
        created_by=str(t.created_by) if t.created_by else None,
        created_at=t.created_at.isoformat(),
        updated_at=t.updated_at.isoformat(),
    )


@router.put("/prompt-templates/{template_id}", response_model=PromptTemplateResponse)
async def update_prompt_template(
    template_id: UUID,
    payload: PromptTemplateUpdate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> PromptTemplateResponse:
    if current_user.role not in _PLAYGROUND_WRITE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or developer role required",
        )

    template = await db.scalar(
        select(PromptTemplate).where(
            PromptTemplate.id == template_id,
            PromptTemplate.org_id == current_user.org_id,
            PromptTemplate.status.in_(("active", "draft")),
        )
    )
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        await db.refresh(template)
        return PromptTemplateResponse(
            id=str(template.id),
            org_id=str(template.org_id),
            name=template.name,
            description=template.description,
            system_message=template.system_message,
            user_template=template.user_template,
            variables_schema=template.variables_schema or [],
            version=template.version,
            is_active=template.is_active,
            status=template.status,
            created_by=str(template.created_by) if template.created_by else None,
            created_at=template.created_at.isoformat(),
            updated_at=template.updated_at.isoformat(),
        )

    if template.status == "draft":
        # A draft is edited in place: it is not live and has no history to keep. Any eval run of its old content no longer
        # counts toward promotion, because runs vouch for a fingerprint of the content they tested.
        for field in ("name", "description", "system_message", "user_template"):
            if field in updates:
                setattr(template, field, updates[field])
        await db.commit()
        await db.refresh(template)
        return _as_response(template)

    gated = (await policy_store.load(current_user.org_id, db, redis)).prompt_promotion_gate
    if gated and await db.scalar(
        select(PromptTemplate.id).where(
            PromptTemplate.org_id == template.org_id, PromptTemplate.name == template.name, PromptTemplate.status == "draft"
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "draft_exists", "detail": "This prompt already has a draft waiting to be promoted. Edit that one or promote it first."},
        )
    highest = await db.scalar(
        select(func.max(PromptTemplate.version)).where(PromptTemplate.org_id == template.org_id, PromptTemplate.name == template.name)
    )
    new_version = (highest or template.version) + 1
    new_template = PromptTemplate(
        org_id=template.org_id,
        name=updates.get("name", template.name),
        description=updates.get("description", template.description),
        system_message=updates.get("system_message", template.system_message),
        user_template=updates.get("user_template", template.user_template),
        variables_schema=template.variables_schema or [],
        version=new_version,
        is_active=not gated,
        status="draft" if gated else "active",
        created_by=current_user.id,
    )
    if not gated:
        template.is_active = False
        template.status = "retired"
    db.add(new_template)
    await db.commit()
    await db.refresh(new_template)

    return PromptTemplateResponse(
        id=str(new_template.id),
        org_id=str(new_template.org_id),
        name=new_template.name,
        description=new_template.description,
        system_message=new_template.system_message,
        user_template=new_template.user_template,
        variables_schema=new_template.variables_schema or [],
        version=new_template.version,
        is_active=new_template.is_active,
        status=new_template.status,
        created_by=str(new_template.created_by) if new_template.created_by else None,
        created_at=new_template.created_at.isoformat(),
        updated_at=new_template.updated_at.isoformat(),
    )


@router.delete("/prompt-templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_prompt_template(
    template_id: UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> None:
    if current_user.role not in _PLAYGROUND_WRITE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or developer role required",
        )

    template = await db.scalar(
        select(PromptTemplate).where(
            PromptTemplate.id == template_id,
            PromptTemplate.org_id == current_user.org_id,
        )
    )
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    template.is_active = False
    template.status = "retired"
    await db.commit()


@router.get("/prompt-templates/{template_id}/versions", response_model=list[PromptTemplateResponse])
async def list_template_versions(
    template_id: UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> list[PromptTemplateResponse]:
    base = await db.scalar(
        select(PromptTemplate).where(
            PromptTemplate.id == template_id,
            PromptTemplate.org_id == current_user.org_id,
        )
    )
    if base is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    rows = await db.scalars(
        select(PromptTemplate)
        .where(
            PromptTemplate.org_id == current_user.org_id,
            PromptTemplate.name == base.name,
        )
        .order_by(PromptTemplate.version.desc())
    )
    return [
        PromptTemplateResponse(
            id=str(t.id),
            org_id=str(t.org_id),
            name=t.name,
            description=t.description,
            system_message=t.system_message,
            user_template=t.user_template,
            variables_schema=t.variables_schema or [],
            version=t.version,
            is_active=t.is_active,
            status=t.status,
            created_by=str(t.created_by) if t.created_by else None,
            created_at=t.created_at.isoformat(),
            updated_at=t.updated_at.isoformat(),
        )
        for t in rows
    ]


# ── Playground Compare ────────────────────────────────────────────────────


@router.post("/playground/compare", response_model=PlaygroundCompareResponse)
async def playground_compare(
    payload: PlaygroundCompareRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> PlaygroundCompareResponse:
    if current_user.role not in _PLAYGROUND_WRITE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or developer role required",
        )

    messages_list = [{"role": m.role, "content": m.content} for m in payload.messages]
    est_tokens = _estimate_tokens_from_messages(messages_list) * len(payload.models)
    policy_config = await policy_store.load(current_user.org_id, db, redis)

    # Policy evaluation — playground must respect the same guardrails as the proxy
    from app.schemas.chat import ChatCompletionRequest as _CCR

    for model_name in payload.models:
        synth_request = _CCR.model_construct(model=model_name, messages=payload.messages)
        decision = await policy_service.evaluate_chat_request(synth_request, policy_config)
        if not decision.allowed:
            raise HTTPException(
                status_code=POLICY_BLOCK_STATUS,
                detail={
                    "error": "policy_violation",
                    "detail": decision.detail or "Blocked by policy.",
                    "reason_code": decision.reason_code,
                    "explanation": explain_policy(decision.reason_code),
                },
            )

    ok, _, limit_type, limit_detail, retry_after = await rate_limiter_service.check_limits(
        redis=redis,
        org_id=str(current_user.org_id),
        user_id=str(current_user.id),
        request_tokens_estimate=est_tokens,
        max_rpm=settings.DEFAULT_RATE_LIMIT_RPM,
        max_tpm=settings.DEFAULT_RATE_LIMIT_TPM,
        max_daily_budget_usd=Decimal(str(settings.DEFAULT_BUDGET_DAILY_USD)),
        user_daily_budget_usd=getattr(current_user, "budget_daily_usd", None),
        model=payload.models[0] if payload.models else "",
        policy_config=policy_config,
    )
    if not ok:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "rate_limit_exceeded",
                "limit_type": limit_type,
                "detail": limit_detail,
                "retry_after": retry_after,
            },
        )

    # Every model is checked before any is called: a request that names an unknown provider is a 400, not a partial result.
    for model_name in payload.models:
        split_model(model_name)

    # How sensitive is this prompt, and which of the chosen models may see it? Planning uses the database session, which
    # concurrent tasks cannot share, so each model is planned in turn; the calls themselves (no session) then run together.
    # The prompt is classified and the registry loaded once for all of them.
    classification = await classify_chat_request(_CCR.model_construct(model="", messages=payload.messages), policy_config, None)
    routing_inputs = await llm_service.routing_inputs(db, current_user.org_id, policy_config) if policy_config.routing_mode != "off" else ([], "us")
    requested = behavior_mod.Behavior(**payload.behavior.model_dump(exclude_none=True)) if payload.behavior is not None else behavior_mod.Behavior()
    behavior = behavior_mod.settle(policy_config.behavior_defaults, policy_config.behavior_ceiling, requested)
    planned_messages = behavior_mod.with_citation_instruction(messages_list) if behavior is not None and behavior.effective.citations else messages_list
    plans: list[CallPlan | RunOutcome] = []
    for model in payload.models:
        plans.append(
            await plan_call(
                db=db, redis=redis, org_id=current_user.org_id, user_id=current_user.id, model=model, messages=planned_messages,
                policy_config=policy_config, source="playground", temperature=payload.temperature, max_tokens=payload.max_tokens,
                timeout=PLAYGROUND_TIMEOUT_SECONDS, check_policy=False, classification=classification, routing_inputs=routing_inputs,
                behavior=behavior,
            )
        )

    async def _finish(plan: CallPlan | RunOutcome) -> RunOutcome:
        if isinstance(plan, RunOutcome):
            return plan  # refused or no key: already logged, nothing to call
        return await execute_plan(plan, redis=redis, org_id=current_user.org_id, user_id=current_user.id)

    outcomes = await asyncio.gather(*(_finish(plan) for plan in plans))
    return PlaygroundCompareResponse(
        results=[
            PlaygroundCompareResult(
                model=model, content=outcome.content, prompt_tokens=outcome.prompt_tokens, completion_tokens=outcome.completion_tokens,
                cost_usd=outcome.cost_usd, latency_ms=outcome.latency_ms, ttft_ms=None, error=outcome.error,
            )
            for model, outcome in zip(payload.models, outcomes, strict=True)
        ]
    )
