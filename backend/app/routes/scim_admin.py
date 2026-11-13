"""Admin API for the org's SCIM token: see its status, create or rotate it (shown once), revoke it."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import CurrentUser, get_db
from app.models.organization import Organization
from app.models.scim_token import ScimToken
from app.services.admin_audit_service import get_ip, log_admin_action
from app.services.plan_service import assert_plan_allows
from app.services.scim_tokens import get_live_token, issue_token, revoke_live_token

router = APIRouter(prefix="/api/v1/scim/token", tags=["SCIM"])


class ScimTokenStatus(BaseModel):
    configured: bool
    token_prefix: str | None = None
    created_at: datetime | None = None
    last_used_at: datetime | None = None
    scim_base_url: str


class ScimTokenCreated(ScimTokenStatus):
    token: str
    rotated: bool


def _status(row: ScimToken | None, request: Request) -> ScimTokenStatus:
    base = f"{str(request.base_url).rstrip('/')}/scim/v2"
    if row is None:
        return ScimTokenStatus(configured=False, scim_base_url=base)
    return ScimTokenStatus(
        configured=True, token_prefix=row.token_prefix, created_at=row.created_at, last_used_at=row.last_used_at, scim_base_url=base
    )


def _require_admin(user: CurrentUser) -> None:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


@router.get("", response_model=ScimTokenStatus)
async def get_token_status(request: Request, current_user: CurrentUser, db: AsyncSession = Depends(get_db)) -> ScimTokenStatus:
    _require_admin(current_user)
    return _status(await get_live_token(db, current_user.org_id), request)


@router.post("", response_model=ScimTokenCreated, status_code=status.HTTP_201_CREATED)
async def create_or_rotate_token(
    request: Request, response: Response, current_user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> ScimTokenCreated:
    _require_admin(current_user)
    org = await db.get(Organization, current_user.org_id)
    if org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    assert_plan_allows(org, "sso_enabled")

    row, plaintext, rotated = await issue_token(db, current_user.org_id, current_user.id)
    await log_admin_action(
        db,
        org_id=current_user.org_id,
        actor_id=current_user.id,
        actor_email=current_user.email,
        action="scim.token_rotated" if rotated else "scim.token_created",
        resource_type="scim_token",
        resource_id=str(row.id),
        after={"token_prefix": row.token_prefix},  # never the token itself
        ip_address=get_ip(request),
    )
    await db.commit()
    await db.refresh(row)
    response.headers["Cache-Control"] = "no-store"
    return ScimTokenCreated(**_status(row, request).model_dump(), token=plaintext, rotated=rotated)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_token(request: Request, current_user: CurrentUser, db: AsyncSession = Depends(get_db)) -> Response:
    _require_admin(current_user)
    revoked = await revoke_live_token(db, current_user.org_id)
    if revoked is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No SCIM token to revoke")
    await log_admin_action(
        db,
        org_id=current_user.org_id,
        actor_id=current_user.id,
        actor_email=current_user.email,
        action="scim.token_revoked",
        resource_type="scim_token",
        resource_id=str(revoked.id),
        before={"token_prefix": revoked.token_prefix},
        ip_address=get_ip(request),
    )
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
