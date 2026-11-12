"""SCIM 2.0 provisioning endpoints (/scim/v2): an identity provider creates, updates and deactivates users.

Authentication is a per-org SCIM bearer token, never a user session or API key. Every query is filtered by the token's
org (users has no row-level security, so that filter is the wall) and the token's own table is under RLS. Nothing here can
set a role: new users are viewers, and a request that carries roles is refused. DELETE deactivates (users own request
history, so the row stays).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_real_ip, get_redis
from app.models.api_key import ApiKey
from app.models.organization import Organization
from app.models.scim_token import ScimToken
from app.models.user import User
from app.services import scim_discovery, scim_limits
from app.services.admin_audit_service import log_admin_action
from app.services.plan_service import check_user_limit, get_plan_feature
from app.services.scim_errors import SCIM_MEDIA_TYPE, ScimError
from app.services.scim_resources import (
    UserChanges,
    list_response,
    page_window,
    parse_filter,
    parse_patch,
    parse_user_payload,
    to_scim_user,
)
from app.services.scim_tokens import resolve_token

router = APIRouter(prefix="/scim/v2", tags=["SCIM"])

NEW_USER_ROLE = "viewer"
PROVISIONED_PASSWORD = "scim_provisioned"  # placeholder, not a valid hash: the account cannot sign in with a password
_LAST_USED_WRITE_INTERVAL = timedelta(minutes=1)


@dataclass(frozen=True)
class ScimContext:
    token: ScimToken
    org_id: uuid.UUID
    ip: str | None
    base_url: str

    @property
    def actor(self) -> str:
        return f"scim:{self.token.token_prefix}"


def scim_response(body: dict[str, Any] | None, status_code: int = 200, headers: dict[str, str] | None = None) -> Response:
    if body is None:
        return Response(status_code=status_code, headers=headers)
    return JSONResponse(body, status_code=status_code, media_type=SCIM_MEDIA_TYPE, headers=headers)


async def scim_auth(
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> ScimContext:
    ip = get_real_ip(request)
    wait = await scim_limits.too_many_failures(redis, ip)
    if wait is not None:
        raise ScimError(429, "Too many failed attempts", headers={"Retry-After": str(wait)})

    scheme, _, presented = (request.headers.get("Authorization") or "").partition(" ")
    token = await resolve_token(db, presented.strip()) if scheme.lower() == "bearer" and presented.strip() else None
    if token is None:
        await scim_limits.record_failure(redis, ip)
        raise ScimError(401, "Missing or invalid SCIM token", headers={"WWW-Authenticate": "Bearer"})

    org = await db.get(Organization, token.org_id)
    if org is None or not org.is_active:
        raise ScimError(403, "Organization is not active")
    if get_plan_feature(org, "sso_enabled") is False:
        raise ScimError(403, "SCIM provisioning is not available on this organization's plan")

    wait = await scim_limits.org_over_limit(redis, token.org_id)
    if wait is not None:
        raise ScimError(429, "Rate limit exceeded", headers={"Retry-After": str(wait)})

    now = datetime.now(UTC).replace(tzinfo=None)
    if token.last_used_at is None or now - token.last_used_at >= _LAST_USED_WRITE_INTERVAL:
        token.last_used_at = now
        await db.commit()
    return ScimContext(token=token, org_id=token.org_id, ip=ip, base_url=str(request.base_url).rstrip("/"))


Auth = Depends(scim_auth)


async def _json_body(request: Request) -> Any:
    try:
        return await request.json()
    except ValueError as exc:
        raise ScimError(400, "Request body is not valid JSON", "invalidSyntax") from exc


def _audit_view(user: User) -> dict[str, Any]:
    return {
        "id": str(user.id),
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "is_active": user.is_active,
        "external_id": user.external_id,
    }


async def _load_user(db: AsyncSession, ctx: ScimContext, user_id: str) -> User:
    try:
        wanted = uuid.UUID(user_id)
    except ValueError:
        wanted = None
    user = await db.scalar(select(User).where(User.id == wanted, User.org_id == ctx.org_id, User.scim_managed.is_(True))) if wanted else None
    if user is None:
        raise ScimError(404, "User not found")
    return user


async def _ensure_unique(db: AsyncSession, ctx: ScimContext, changes: UserChanges, current: User | None) -> None:
    """Refuse an email or externalId that another user holds. The email is unique across ALL orgs (a database rule)."""
    email = changes.fields.get("email")
    if email is not None and (current is None or email != current.email):
        if await db.scalar(select(User.id).where(User.email == email)) is not None:
            raise ScimError(409, "userName is already in use", "uniqueness")
    external = changes.fields.get("external_id")
    if external is not None and (current is None or external != current.external_id):
        taken = await db.scalar(select(User.id).where(User.org_id == ctx.org_id, User.external_id == external))
        if taken is not None:
            raise ScimError(409, "externalId is already in use", "uniqueness")


async def _guard_last_admin(db: AsyncSession, ctx: ScimContext, user: User, changes: UserChanges) -> None:
    if changes.fields.get("active") is not False or not (user.role == "admin" and user.is_active):
        return
    active_admins = list(await db.scalars(select(User.id).where(User.org_id == ctx.org_id, User.role == "admin", User.is_active.is_(True))))
    if len(active_admins) <= 1:
        raise ScimError(400, "Cannot deactivate the last active admin of the organization", "mutability")


def _guard_elevated(user: User, changes: UserChanges) -> None:
    """A user someone promoted past viewer is no longer the identity provider's to re-point or re-enable.

    Changing the email of an admin or developer would let whoever controls the new address sign in as them through SSO
    (SSO matches on email), and re-enabling one would undo an admin's decision. Deactivating stays allowed: that is
    offboarding, and it only removes access.
    """
    if user.role == "viewer":
        return
    new_email = changes.fields.get("email")
    if new_email is not None and new_email != user.email:
        raise ScimError(403, f"The email of a {user.role} cannot be changed through SCIM", "mutability")
    if changes.fields.get("active") is True and not user.is_active:
        raise ScimError(403, f"A deactivated {user.role} cannot be re-enabled through SCIM", "mutability")


async def _enforce_user_limit(db: AsyncSession, ctx: ScimContext) -> None:
    org = await db.get(Organization, ctx.org_id)
    active = await db.scalar(select(func.count()).select_from(User).where(User.org_id == ctx.org_id, User.is_active.is_(True))) or 0
    try:
        check_user_limit(org, int(active))
    except HTTPException as exc:
        raise ScimError(403, "The plan's user limit is reached; upgrade the plan or deactivate a user", "tooMany") from exc


async def _cut_old_identity(db: AsyncSession, user: User) -> None:
    """After an email change the person behind the account may differ: unlink SSO and revoke the user's API keys."""
    user.sso_sub = None
    user.sso_connection_id = None
    await db.execute(update(ApiKey).where(ApiKey.user_id == user.id).values(is_active=False))


def _action(before: User | None, changes: UserChanges) -> str:
    if before is None:
        return "user.scim_created"
    if changes.fields.get("active") is False and before.is_active:
        return "user.scim_deactivated"
    if changes.fields.get("active") is True and not before.is_active:
        return "user.scim_reactivated"
    return "user.scim_updated"


async def _save(db: AsyncSession, ctx: ScimContext, user: User | None, changes: UserChanges) -> User:
    """Create (user is None) or update, write the audit entry, commit. Any uniqueness race becomes a SCIM 409."""
    await _ensure_unique(db, ctx, changes, user)
    before = _audit_view(user) if user is not None else None
    action = _action(user, changes)
    if user is None:
        if changes.fields.get("active", True):
            await _enforce_user_limit(db, ctx)
        target = User(
            org_id=ctx.org_id, role=NEW_USER_ROLE, password_hash=PROVISIONED_PASSWORD, email=changes.fields["email"], scim_managed=True
        )
        db.add(target)
    else:
        _guard_elevated(user, changes)
        await _guard_last_admin(db, ctx, user, changes)
        if changes.fields.get("active") is True and not user.is_active:
            await _enforce_user_limit(db, ctx)
        if changes.fields.get("email") not in (None, user.email):
            await _cut_old_identity(db, user)
        target = user
    for key, value in changes.fields.items():
        if key == "active":
            target.is_active = bool(value)
        else:
            setattr(target, key, value)
    try:
        await db.flush()
        await log_admin_action(
            db,
            org_id=ctx.org_id,
            actor_id=None,
            actor_email=ctx.actor,
            action=action,
            resource_type="user",
            resource_id=str(target.id),
            before=before,
            after=_audit_view(target),
            ip_address=ctx.ip,
        )
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ScimError(409, "userName or externalId is already in use", "uniqueness") from exc
    await db.refresh(target)
    return target


# ── Discovery ──────────────────────────────────────────────────────────────


@router.get("/ServiceProviderConfig")
async def get_service_provider_config(ctx: ScimContext = Auth) -> Response:
    return scim_response(scim_discovery.service_provider_config(ctx.base_url))


@router.get("/ResourceTypes")
async def get_resource_types(ctx: ScimContext = Auth) -> Response:
    return scim_response(scim_discovery.resource_types(ctx.base_url))


@router.get("/Schemas")
async def get_schemas(ctx: ScimContext = Auth) -> Response:
    return scim_response(scim_discovery.schemas(ctx.base_url))


@router.api_route("/Groups", methods=["GET", "POST"])
@router.api_route("/Groups/{group_id}", methods=["GET", "PUT", "PATCH", "DELETE"])
async def groups_not_supported(group_id: str | None = None, ctx: ScimContext = Auth) -> Response:  # noqa: ARG001
    raise ScimError(404, "Groups are not supported; manage teams in OpenProxyAI")


# ── Users ──────────────────────────────────────────────────────────────────


@router.get("/Users")
async def list_users(request: Request, ctx: ScimContext = Auth, db: AsyncSession = Depends(get_db)) -> Response:
    wanted = parse_filter(request.query_params.get("filter"))
    offset, limit = page_window(request.query_params.get("startIndex"), request.query_params.get("count"))
    query = select(User).where(User.org_id == ctx.org_id, User.scim_managed.is_(True))
    if wanted is not None:
        attribute, value = wanted
        if attribute == "userName":
            query = query.where(func.lower(User.email) == value.lower())
        elif attribute == "externalId":
            query = query.where(User.external_id == value)
        else:
            try:
                query = query.where(User.id == uuid.UUID(value))
            except ValueError:
                query = query.where(User.id.is_(None))
    total = await db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = await db.scalars(query.order_by(User.created_at, User.id).offset(offset).limit(limit))
    resources = [to_scim_user(row, ctx.base_url) for row in rows]
    return scim_response(list_response(resources, int(total), offset + 1))


@router.post("/Users")
async def create_user(request: Request, ctx: ScimContext = Auth, db: AsyncSession = Depends(get_db)) -> Response:
    changes = parse_user_payload(await _json_body(request), creating=True)
    user = await _save(db, ctx, None, changes)
    body = to_scim_user(user, ctx.base_url)
    return scim_response(body, 201, {"Location": body["meta"]["location"]})


@router.get("/Users/{user_id}")
async def get_user(user_id: str, ctx: ScimContext = Auth, db: AsyncSession = Depends(get_db)) -> Response:
    return scim_response(to_scim_user(await _load_user(db, ctx, user_id), ctx.base_url))


@router.put("/Users/{user_id}")
async def replace_user(user_id: str, request: Request, ctx: ScimContext = Auth, db: AsyncSession = Depends(get_db)) -> Response:
    user = await _load_user(db, ctx, user_id)
    saved = await _save(db, ctx, user, parse_user_payload(await _json_body(request), creating=False))
    return scim_response(to_scim_user(saved, ctx.base_url))


@router.patch("/Users/{user_id}")
async def patch_user(user_id: str, request: Request, ctx: ScimContext = Auth, db: AsyncSession = Depends(get_db)) -> Response:
    user = await _load_user(db, ctx, user_id)
    saved = await _save(db, ctx, user, parse_patch(await _json_body(request)))
    return scim_response(to_scim_user(saved, ctx.base_url))


@router.delete("/Users/{user_id}")
async def deactivate_user(user_id: str, ctx: ScimContext = Auth, db: AsyncSession = Depends(get_db)) -> Response:
    user = await _load_user(db, ctx, user_id)
    if user.is_active:
        await _save(db, ctx, user, UserChanges({"active": False}))
    return scim_response(None, 204)
