"""SSO management and OIDC callback endpoints."""

from __future__ import annotations

import json
import time

from fastapi import APIRouter, Depends, HTTPException, Request, Query, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import CurrentUser, get_db, get_redis, get_real_ip
from app.models.organization import Organization
from app.schemas.sso import SSOConnectionCreateRequest, SSOConnectionResponse
from app.services import sso_service
from app.services.plan_service import assert_plan_allows

router = APIRouter(tags=["SSO"])


def _get_frontend_base_url() -> str:
    """Frontend base URL for SSO redirect; fallback to first CORS origin."""
    if settings.FRONTEND_BASE_URL:
        return settings.FRONTEND_BASE_URL.rstrip("/")
    try:
        parsed = json.loads(settings.CORS_ORIGINS)
        if isinstance(parsed, list) and parsed:
            return str(parsed[0]).rstrip("/")
    except (json.JSONDecodeError, TypeError):
        pass
    first = next(
        (o.strip().rstrip("/") for o in settings.CORS_ORIGINS.split(",") if o.strip()),
        "http://localhost:5173",
    )
    return first


def _require_admin(current_user: CurrentUser) -> CurrentUser:
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin required",
        )
    return current_user


@router.post(
    "/api/v1/sso/connections",
    response_model=SSOConnectionResponse,
    status_code=201,
)
async def create_sso_connection(
    payload: SSOConnectionCreateRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> SSOConnectionResponse:
    """Create a new SSO/OIDC connection for the current org (admin only, enterprise plan)."""
    _require_admin(current_user)
    org = await db.get(Organization, current_user.org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    assert_plan_allows(org, "sso_enabled")

    conn = await sso_service.create_sso_connection(
        db=db,
        org_id=str(current_user.org_id),
        provider_name=payload.provider_name,
        issuer_url=payload.issuer_url,
        client_id=payload.client_id,
        client_secret=payload.client_secret,
        domain_hint=payload.domain_hint,
    )
    return SSOConnectionResponse.model_validate(conn)


@router.get(
    "/api/v1/sso/connections",
    response_model=list[SSOConnectionResponse],
)
async def list_sso_connections(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> list[SSOConnectionResponse]:
    """List all SSO connections for the current org (admin only)."""
    _require_admin(current_user)
    connections = await sso_service.list_sso_connections(db, str(current_user.org_id))
    return [SSOConnectionResponse.model_validate(c) for c in connections]


@router.delete("/api/v1/sso/connections/{connection_id}", status_code=204)
async def delete_sso_connection(
    connection_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete an SSO connection (admin only)."""
    _require_admin(current_user)
    deleted = await sso_service.delete_sso_connection(
        db, str(current_user.org_id), connection_id
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="SSO connection not found")


@router.get("/api/v1/auth/sso/initiate")
async def sso_initiate(
    connection_id: str = Query(...),
    redirect_uri: str = Query(...),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> RedirectResponse:
    """Initiate OIDC authorization code flow — redirects to the IdP."""
    auth_url = await sso_service.initiate_sso(
        db=db,
        redis=redis,
        connection_id=connection_id,
        redirect_uri=redirect_uri,
    )
    return RedirectResponse(url=auth_url, status_code=302)


@router.get("/api/v1/auth/sso/callback")
async def sso_callback(
    code: str = Query(...),
    state: str = Query(...),
    redirect_uri: str = Query(default=""),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> RedirectResponse:
    """Handle OIDC callback — exchange code for tokens, JIT-provision user (C03: one-time code)."""
    access_token, refresh_token = await sso_service.handle_sso_callback(
        db=db,
        redis=redis,
        code=code,
        state=state,
        redirect_uri=redirect_uri,
        base_url=settings.APP_NAME,
    )
    one_time_code = await sso_service.create_sso_code(
        redis=redis,
        access_token=access_token,
        refresh_token=refresh_token,
    )
    frontend = _get_frontend_base_url()
    console_url = f"{frontend}/sso-callback?code={one_time_code}"
    return RedirectResponse(url=console_url, status_code=302)


class SSOExchangeRequest(BaseModel):
    code: str


class SSOExchangeResponse(BaseModel):
    access_token: str
    refresh_token: str


async def _check_sso_exchange_rate_limit(redis: Redis, ip: str) -> None:
    """Rate limit SSO exchange-code to prevent brute-force."""
    rpm = settings.SSO_EXCHANGE_RATE_LIMIT_RPM
    minute_bucket = int(time.time()) // 60
    key = f"sso_exchange_rl:{ip}:{minute_bucket}"
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, 120)
    if count > rpm:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many SSO exchange attempts",
        )


@router.post("/api/v1/auth/sso/exchange-code", response_model=SSOExchangeResponse)
async def sso_exchange_code(
    request: Request,
    payload: SSOExchangeRequest,
    redis: Redis = Depends(get_redis),
) -> SSOExchangeResponse:
    """Exchange one-time SSO code for tokens (C03)."""
    await _check_sso_exchange_rate_limit(redis, get_real_ip(request))
    access_token, refresh_token = await sso_service.exchange_sso_code(
        redis=redis, code=payload.code
    )
    return SSOExchangeResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )
