"""Prompt Playground — model comparison and saved prompt templates."""

import asyncio
import fnmatch
import random
import time
import uuid
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from litellm import acompletion
from redis.asyncio import Redis
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import CurrentUser, get_db, get_redis
from app.models.llm_provider_key import LLMProviderKey
from app.models.prompt_template import PromptTemplate
from app.schemas.playground import (
    PlaygroundCompareRequest,
    PlaygroundCompareResponse,
    PlaygroundCompareResult,
    PromptTemplateCreate,
    PromptTemplateResponse,
    PromptTemplateUpdate,
)
from app.models.organization import Organization
from app.services.audit_logger import log_request
from app.services.cost_tracker import cost_tracker_service
from app.services.crypto_service import decrypt
from app.services.policy_service import policy_service, policy_store
from app.services.rate_limiter import rate_limiter_service

router = APIRouter(prefix="/api/v1", tags=["Playground"])

_PLAYGROUND_WRITE_ROLES = frozenset({"admin", "developer"})


def _estimate_tokens_from_messages(messages: list[dict]) -> int:
    """Conservative token estimate for rate limiting."""
    content_chars = sum(len(str(m.get("content") or "")) for m in messages)
    return max(content_chars // 4, 1)


async def _select_provider_key(
    db: AsyncSession,
    org_id: UUID,
    provider: str,
    model: str | None = None,
    data_region: str = "us",
) -> str:
    """Return decrypted API key for the provider (mirrors LLMService logic including region filter)."""
    rows = await db.scalars(
        select(LLMProviderKey).where(
            LLMProviderKey.org_id == org_id,
            LLMProviderKey.provider == provider,
            LLMProviderKey.is_active.is_(True),
            or_(
                LLMProviderKey.region == data_region,
                LLMProviderKey.region == "global",
            ),
        )
    )
    keys = [row for row in rows if row.weight > 0]
    if keys:
        if model:
            matched = [
                k
                for k in keys
                if k.model_patterns
                and any(fnmatch.fnmatch(model, p) for p in k.model_patterns)
            ]
            candidates = matched if matched else keys
        else:
            candidates = keys
        primary = random.choices(candidates, weights=[k.weight for k in candidates], k=1)[0]
        raw = decrypt(primary.api_key_encrypted)
        return raw

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


def _split_model(model_name: str) -> tuple[str, str]:
    if "/" not in model_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "invalid_model", "detail": "Model must be provider/model (e.g. openai/gpt-4)"},
        )
    provider, model = model_name.split("/", 1)
    if not provider or not model:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "invalid_model", "detail": "Model not supported"},
        )
    return provider, model


# ── Prompt Templates CRUD ────────────────────────────────────────────────


@router.post("/prompt-templates", response_model=PromptTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_prompt_template(
    payload: PromptTemplateCreate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> PromptTemplateResponse:
    if current_user.role not in _PLAYGROUND_WRITE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or developer role required",
        )

    template = PromptTemplate(
        org_id=current_user.org_id,
        name=payload.name,
        description=payload.description,
        system_message=payload.system_message,
        user_template=payload.user_template,
        variables_schema=[v.model_dump() for v in payload.variables_schema],
        version=1,
        is_active=True,
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
            PromptTemplate.is_active.is_(True),
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
        created_by=str(template.created_by) if template.created_by else None,
        created_at=template.created_at.isoformat(),
        updated_at=template.updated_at.isoformat(),
    )


@router.put("/prompt-templates/{template_id}", response_model=PromptTemplateResponse)
async def update_prompt_template(
    template_id: UUID,
    payload: PromptTemplateUpdate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
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
            PromptTemplate.is_active.is_(True),
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
            created_by=str(template.created_by) if template.created_by else None,
            created_at=template.created_at.isoformat(),
            updated_at=template.updated_at.isoformat(),
        )

    new_version = template.version + 1
    new_template = PromptTemplate(
        org_id=template.org_id,
        name=updates.get("name", template.name),
        description=updates.get("description", template.description),
        system_message=updates.get("system_message", template.system_message),
        user_template=updates.get("user_template", template.user_template),
        variables_schema=template.variables_schema or [],
        version=new_version,
        is_active=True,
        created_by=current_user.id,
    )
    template.is_active = False
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
    background_tasks: BackgroundTasks,
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
                status_code=403,
                detail={
                    "error": "policy_violation",
                    "detail": decision.detail or "Blocked by policy.",
                    "reason_code": decision.reason_code,
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

    # Load org data_region for provider key selection
    org = await db.get(Organization, current_user.org_id)
    data_region = (org.data_region or "us").strip().lower() if org else "us"

    async def _run_one(model: str) -> PlaygroundCompareResult:
        req_id = uuid.uuid4()
        start = time.perf_counter()
        provider, model_name = _split_model(model)
        try:
            api_key = await _select_provider_key(
                db, current_user.org_id, provider, model_name, data_region=data_region,
            )
        except HTTPException:
            raise

        kwargs = {
            "model": model,
            "messages": messages_list,
            "api_key": api_key,
            "timeout": 30,
            "request_timeout": 30,
        }
        if payload.temperature is not None:
            kwargs["temperature"] = payload.temperature
        if payload.max_tokens is not None:
            kwargs["max_tokens"] = payload.max_tokens

        try:
            response = await acompletion(**kwargs)
            latency_ms = int((time.perf_counter() - start) * 1000)
            usage = getattr(response, "usage", None) or {}
            prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
            completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
            cost = cost_tracker_service.calculate_cost_usd(response)
            content = ""
            if response.choices:
                content = getattr(response.choices[0].message, "content", "") or ""

            background_tasks.add_task(
                log_request,
                redis=redis,
                request_id=req_id,
                org_id=current_user.org_id,
                user_id=current_user.id,
                api_key_id=None,
                model=model,
                provider=provider,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cost_usd=cost,
                latency_ms=latency_ms,
                ttft_ms=None,
                status_code=200,
                request_metadata={"source": "playground"},
                labels=None,
            )

            return PlaygroundCompareResult(
                model=model,
                content=content,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cost_usd=cost,
                latency_ms=latency_ms,
                ttft_ms=None,
                error=None,
            )
        except Exception as exc:
            latency_ms = int((time.perf_counter() - start) * 1000)
            err_msg = str(exc)
            background_tasks.add_task(
                log_request,
                redis=redis,
                request_id=req_id,
                org_id=current_user.org_id,
                user_id=current_user.id,
                api_key_id=None,
                model=model,
                provider=provider,
                prompt_tokens=0,
                completion_tokens=0,
                cost_usd=Decimal("0"),
                latency_ms=latency_ms,
                ttft_ms=None,
                status_code=502,
                error_message=err_msg,
                request_metadata={"source": "playground"},
                labels=None,
            )
            return PlaygroundCompareResult(
                model=model,
                content="",
                prompt_tokens=0,
                completion_tokens=0,
                cost_usd=Decimal("0"),
                latency_ms=latency_ms,
                ttft_ms=None,
                error=err_msg,
            )

    tasks = [_run_one(m) for m in payload.models]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    out: list[PlaygroundCompareResult] = []
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            model = payload.models[i]
            provider, _ = _split_model(model)
            out.append(
                PlaygroundCompareResult(
                    model=model,
                    content="",
                    prompt_tokens=0,
                    completion_tokens=0,
                    cost_usd=Decimal("0"),
                    latency_ms=0,
                    ttft_ms=None,
                    error=str(r),
                )
            )
        else:
            out.append(r)

    return PlaygroundCompareResponse(results=out)
