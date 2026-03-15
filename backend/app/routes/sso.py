"""SSO management and OIDC callback endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import CurrentUser, get_db, get_redis
from app.models.organization import Organization
from app.schemas.sso import SSOConnectionCreateRequest, SSOConnectionResponse
from app.services import sso_service
from app.services.plan_service import assert_plan_allows

router = APIRouter(tags=["SSO"])


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
    """Handle OIDC callback — exchange code for tokens, JIT-provision user."""
    from app.config import settings

    access_token, refresh_token = await sso_service.handle_sso_callback(
        db=db,
        redis=redis,
        code=code,
        state=state,
        redirect_uri=redirect_uri,
        base_url=settings.APP_NAME,
    )
    console_url = (
        f"/#/sso-callback?access_token={access_token}&refresh_token={refresh_token}"
    )
    return RedirectResponse(url=console_url, status_code=302)
