"""Invite management endpoints — POST /, GET /, DELETE /{invite_id}."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import CurrentUser, get_db
from app.models.user_invite import UserInvite
from app.schemas.invite import InviteCreateRequest, InviteCreatedResponse, InviteResponse
from app.services import invite_service
from app.services.admin_audit_service import get_ip, log_admin_action

router = APIRouter(prefix="/api/v1/invites", tags=["Invites"])


def _require_admin(current_user) -> None:  # type: ignore[no-untyped-def]
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )


@router.post("/", response_model=InviteCreatedResponse, status_code=status.HTTP_201_CREATED)
async def create_invite(
    payload: InviteCreateRequest,
    request: Request,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> InviteCreatedResponse:
    _require_admin(current_user)

    await log_admin_action(
        db,
        org_id=current_user.org_id,
        actor_id=current_user.id,
        actor_email=current_user.email,
        action="invite.sent",
        resource_type="invite",
        resource_id=payload.email,
        before=None,
        after={"email": payload.email, "role": payload.role},
        ip_address=get_ip(request),
    )

    invite, invite_url = await invite_service.create_invite(
        db=db,
        org_id=current_user.org_id,
        email=payload.email,
        role=payload.role,
        invited_by_id=current_user.id,
    )
    return InviteCreatedResponse(
        id=invite.id,
        org_id=invite.org_id,
        email=invite.email,
        role=invite.role,
        invited_by=invite.invited_by,
        expires_at=invite.expires_at,
        accepted_at=invite.accepted_at,
        created_at=invite.created_at,
        invite_url=invite_url,
    )


@router.get("/", response_model=list[InviteResponse])
async def list_pending_invites(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> list[InviteResponse]:
    _require_admin(current_user)
    invites = await invite_service.get_pending_invites(db=db, org_id=current_user.org_id)
    return [InviteResponse.model_validate(inv) for inv in invites]


@router.delete("/{invite_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_invite(
    invite_id: uuid.UUID,
    request: Request,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> None:
    _require_admin(current_user)

    # Look up the invite first so we can capture before state for the audit log
    invite = await db.scalar(
        select(UserInvite).where(
            UserInvite.id == invite_id,
            UserInvite.org_id == current_user.org_id,
        )
    )
    if invite is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invite not found",
        )

    await log_admin_action(
        db,
        org_id=current_user.org_id,
        actor_id=current_user.id,
        actor_email=current_user.email,
        action="invite.revoked",
        resource_type="invite",
        resource_id=str(invite_id),
        before={"email": invite.email, "role": invite.role},
        after=None,
        ip_address=get_ip(request),
    )

    found = await invite_service.revoke_invite(
        db=db, org_id=current_user.org_id, invite_id=invite_id
    )
    if not found:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invite not found",
        )
