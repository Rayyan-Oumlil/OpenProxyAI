"""Invite lifecycle — create, list pending, revoke, and accept invitations."""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Organization
from app.models.user import User
from app.models.user_invite import UserInvite
from app.services.plan_service import check_user_limit
from app.utils.crypto import hash_password

_INVITE_EXPIRY_DAYS = 7


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


async def create_invite(
    db: AsyncSession,
    org_id: uuid.UUID,
    email: str,
    role: str,
    invited_by_id: uuid.UUID,
    base_url: str = "https://app.openproxyai.com",
) -> tuple[UserInvite, str]:
    """Generate an invite token, persist the hash, and return (model, invite_url)."""
    raw_token = secrets.token_urlsafe(32)
    token_hash = _hash_token(raw_token)

    now = _utc_now().replace(tzinfo=None)
    expires_at = now + timedelta(days=_INVITE_EXPIRY_DAYS)

    invite = UserInvite(
        org_id=org_id,
        email=email.lower().strip(),
        role=role,
        token_hash=token_hash,
        invited_by=invited_by_id,
        expires_at=expires_at,
    )
    db.add(invite)
    await db.commit()
    await db.refresh(invite)

    invite_url = f"{base_url}/accept-invite?token={raw_token}"
    return invite, invite_url


async def get_pending_invites(db: AsyncSession, org_id: uuid.UUID) -> list[UserInvite]:
    """Return invites that are not yet accepted and have not expired."""
    now = _utc_now().replace(tzinfo=None)
    result = await db.scalars(
        select(UserInvite).where(
            UserInvite.org_id == org_id,
            UserInvite.accepted_at.is_(None),
            UserInvite.expires_at > now,
        )
    )
    return list(result)


async def revoke_invite(
    db: AsyncSession, org_id: uuid.UUID, invite_id: uuid.UUID
) -> bool:
    """Delete an invite belonging to the org. Returns True if found, False otherwise."""
    invite = await db.scalar(
        select(UserInvite).where(
            UserInvite.id == invite_id,
            UserInvite.org_id == org_id,
        )
    )
    if invite is None:
        return False

    await db.delete(invite)
    await db.commit()
    return True


async def accept_invite(
    db: AsyncSession,
    token: str,
    name: str,
    password: str,
) -> User:
    """Validate token, create user in the existing org, and mark invite accepted."""
    token_hash = _hash_token(token)

    invite = await db.scalar(
        select(UserInvite).where(UserInvite.token_hash == token_hash)
    )

    if invite is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invite not found",
        )

    now = _utc_now().replace(tzinfo=None)

    if invite.expires_at < now:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Invite has expired",
        )

    if invite.accepted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Invite already accepted",
        )

    # Enforce per-plan user limit
    org = await db.get(Organization, invite.org_id)
    if org is not None:
        result = await db.execute(
            select(func.count()).where(
                User.org_id == invite.org_id,
                User.is_active == True,  # noqa: E712
            )
        )
        active_count = result.scalar_one()
        check_user_limit(org, active_count)

    # Check the invited email is not already taken
    normalized_email = invite.email.lower().strip()
    existing = await db.scalar(select(User).where(User.email == normalized_email))
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists",
        )

    user = User(
        org_id=invite.org_id,
        email=normalized_email,
        name=name,
        password_hash=hash_password(password),
        role=invite.role,
        is_active=True,
    )
    db.add(user)
    await db.flush()

    invite.accepted_at = now
    await db.commit()
    await db.refresh(user)
    return user
