"""WebAssembly policy plugins: /api/v1/policy-plugins (admins only). Phase 5, slice 5.11.

An uploaded module is validated against the sandbox contract before it is stored, hashed, and every change is written to the admin audit
log with the hash. Enabling or removing a plugin updates the org's policy at once (the policy cache is cleared).
"""

from __future__ import annotations

import base64
import binascii
import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import CurrentUser, get_db, get_redis
from app.models.policy_plugin import PolicyPlugin
from app.services import policy_plugins, wasm_runtime
from app.services.admin_audit_service import get_ip, log_admin_action
from app.services.policy_service import policy_store

router = APIRouter(prefix="/api/v1/policy-plugins", tags=["Policy plugins"])

Name = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9_-]{0,58}[a-z0-9]$|^[a-z0-9]$")]
_ADMIN_ONLY = "Only organization admins can manage policy plugins"


class PluginCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name
    module_b64: str = Field(min_length=4, max_length=(wasm_runtime.MAX_MODULE_BYTES * 4) // 3 + 8, description="The .wasm file, base64 encoded.")
    enabled: bool = True


class PluginUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool


class PluginResponse(BaseModel):
    id: uuid.UUID
    name: str
    sha256: str
    size_bytes: int
    enabled: bool
    created_at: datetime


def _response(row: PolicyPlugin) -> PluginResponse:
    return PluginResponse(id=row.id, name=row.name, sha256=row.sha256, size_bytes=row.size_bytes, enabled=row.enabled, created_at=row.created_at)


def _require_admin(user) -> None:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=_ADMIN_ONLY)


async def _sync_policy(db: AsyncSession, redis, org_id: uuid.UUID) -> None:
    """The org's policy lists exactly its enabled plugins, so the decision path never has to query for them."""
    rows = (await db.scalars(select(PolicyPlugin).where(PolicyPlugin.org_id == org_id, PolicyPlugin.enabled.is_(True)).order_by(PolicyPlugin.created_at, PolicyPlugin.id))).all()
    config = await policy_store.load(org_id, db, redis)
    config.wasm_plugins = [{"id": str(r.id), "name": r.name, "sha256": r.sha256} for r in rows]
    await policy_store.save(org_id, config, db, redis)


async def _audit(db, user, request: Request, action: str, row: PolicyPlugin) -> None:
    await log_admin_action(
        db, org_id=user.org_id, actor_id=user.id, actor_email=user.email, action=action, resource_type="policy_plugin", resource_id=str(row.id),
        after={"name": row.name, "sha256": row.sha256, "size_bytes": row.size_bytes, "enabled": row.enabled}, ip_address=get_ip(request),
    )


@router.get("", response_model=list[PluginResponse])
async def list_plugins(current_user: CurrentUser, db: AsyncSession = Depends(get_db)) -> list[PluginResponse]:
    _require_admin(current_user)
    rows = await db.scalars(select(PolicyPlugin).where(PolicyPlugin.org_id == current_user.org_id).order_by(PolicyPlugin.name))
    return [_response(r) for r in rows]


@router.post("", response_model=PluginResponse, status_code=status.HTTP_201_CREATED)
async def upload_plugin(
    payload: PluginCreate, request: Request, current_user: CurrentUser, db: AsyncSession = Depends(get_db), redis=Depends(get_redis)
) -> PluginResponse:
    _require_admin(current_user)
    try:
        data = base64.b64decode(payload.module_b64, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=422, detail={"error": "invalid_plugin", "detail": "module_b64 is not valid base64"}) from None
    try:
        digest = wasm_runtime.validate(data)
    except wasm_runtime.WasmError as exc:
        raise HTTPException(status_code=422, detail={"error": "invalid_plugin", "detail": str(exc)}) from None
    count = await db.scalar(select(func.count()).select_from(PolicyPlugin).where(PolicyPlugin.org_id == current_user.org_id))
    if (count or 0) >= policy_plugins.MAX_PLUGINS_PER_ORG:
        raise HTTPException(
            status_code=409, detail={"error": "too_many_plugins", "detail": f"An organization can have at most {policy_plugins.MAX_PLUGINS_PER_ORG} plugins."}
        )
    row = PolicyPlugin(
        org_id=current_user.org_id, name=payload.name, module=data, sha256=digest, size_bytes=len(data), enabled=payload.enabled, created_by=current_user.id
    )
    db.add(row)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail={"error": "plugin_exists", "detail": "A plugin with this name already exists."}) from None
    await _audit(db, current_user, request, "policy_plugin.uploaded", row)
    await _sync_policy(db, redis, current_user.org_id)
    await db.commit()
    await db.refresh(row)
    return _response(row)


async def _load(db: AsyncSession, user, plugin_id: uuid.UUID) -> PolicyPlugin:
    row = await db.scalar(select(PolicyPlugin).where(PolicyPlugin.id == plugin_id, PolicyPlugin.org_id == user.org_id))
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plugin not found")
    return row


@router.patch("/{plugin_id}", response_model=PluginResponse)
async def set_enabled(
    plugin_id: uuid.UUID, payload: PluginUpdate, request: Request, current_user: CurrentUser, db: AsyncSession = Depends(get_db), redis=Depends(get_redis)
) -> PluginResponse:
    _require_admin(current_user)
    row = await _load(db, current_user, plugin_id)
    row.enabled = payload.enabled
    await _audit(db, current_user, request, "policy_plugin.enabled" if payload.enabled else "policy_plugin.disabled", row)
    await db.flush()
    await _sync_policy(db, redis, current_user.org_id)
    await db.commit()
    await db.refresh(row)
    return _response(row)


@router.delete("/{plugin_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_plugin(
    plugin_id: uuid.UUID, request: Request, current_user: CurrentUser, db: AsyncSession = Depends(get_db), redis=Depends(get_redis)
) -> Response:
    _require_admin(current_user)
    row = await _load(db, current_user, plugin_id)
    await _audit(db, current_user, request, "policy_plugin.deleted", row)
    await db.delete(row)
    await db.flush()
    await _sync_policy(db, redis, current_user.org_id)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
