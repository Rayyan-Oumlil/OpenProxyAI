"""Admin API for virtual MCP bundles: /api/v1/mcp-bundles."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import CurrentUser, get_db
from app.models.api_key import ApiKey
from app.models.mcp_bundle import ApiKeyMcpBundle, McpBundle, McpBundleTool
from app.schemas.mcp_bundle import McpBundleCreateRequest, McpBundleResponse, McpBundleUpdateRequest
from app.services.admin_audit_service import get_ip, log_admin_action

router = APIRouter(prefix="/api/v1/mcp-bundles", tags=["MCP Gateway"])

_ADMIN_ONLY = "Only organization admins can manage MCP bundles"


def _require_admin(user) -> None:
	if user.role != "admin":
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=_ADMIN_ONLY)


async def _get_owned(db: AsyncSession, bundle_id: UUID, org_id: UUID) -> McpBundle:
	bundle = await db.get(McpBundle, bundle_id)
	if bundle is None or bundle.org_id != org_id:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bundle not found")
	return bundle


async def _present(db: AsyncSession, bundle: McpBundle) -> McpBundleResponse:
	tools = await db.scalars(select(McpBundleTool.tool_pattern).where(McpBundleTool.bundle_id == bundle.id))
	keys = await db.scalars(select(ApiKeyMcpBundle.api_key_id).where(ApiKeyMcpBundle.bundle_id == bundle.id))
	return McpBundleResponse(
		id=bundle.id, slug=bundle.slug, name=bundle.name, description=bundle.description, is_active=bundle.is_active,
		tools=sorted(tools.all()), api_key_ids=sorted(keys.all(), key=str), created_at=bundle.created_at,
	)


@router.get("", response_model=list[McpBundleResponse])
async def list_bundles(current_user: CurrentUser, db: AsyncSession = Depends(get_db)) -> list[McpBundleResponse]:
	rows = await db.scalars(select(McpBundle).where(McpBundle.org_id == current_user.org_id).order_by(McpBundle.slug))
	return [await _present(db, b) for b in rows.all()]


@router.post("", response_model=McpBundleResponse, status_code=status.HTTP_201_CREATED)
async def create_bundle(
	payload: McpBundleCreateRequest, request: Request, current_user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> McpBundleResponse:
	_require_admin(current_user)
	bundle = McpBundle(org_id=current_user.org_id, slug=payload.slug, name=payload.name, description=payload.description)
	db.add(bundle)
	try:
		await db.flush()
	except IntegrityError as exc:
		raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"A bundle named {payload.slug} already exists") from exc
	for pattern in dict.fromkeys(payload.tools):
		db.add(McpBundleTool(org_id=current_user.org_id, bundle_id=bundle.id, tool_pattern=pattern))
	await db.flush()
	await log_admin_action(
		db, org_id=current_user.org_id, actor_id=current_user.id, actor_email=current_user.email,
		action="mcp_bundle.created", resource_type="mcp_bundle", resource_id=str(bundle.id),
		after={"slug": bundle.slug, "tools": sorted(set(payload.tools))}, ip_address=get_ip(request),
	)
	await db.commit()
	return await _present(db, bundle)


@router.patch("/{bundle_id}", response_model=McpBundleResponse)
async def update_bundle(
	bundle_id: UUID, payload: McpBundleUpdateRequest, request: Request, current_user: CurrentUser,
	db: AsyncSession = Depends(get_db),
) -> McpBundleResponse:
	_require_admin(current_user)
	bundle = await _get_owned(db, bundle_id, current_user.org_id)
	before = await _present(db, bundle)
	if payload.name is not None:
		bundle.name = payload.name
	if "description" in payload.model_fields_set:
		bundle.description = payload.description
	if payload.is_active is not None:
		bundle.is_active = payload.is_active
	if payload.tools is not None:
		await db.execute(delete(McpBundleTool).where(McpBundleTool.bundle_id == bundle.id))
		for pattern in dict.fromkeys(payload.tools):
			db.add(McpBundleTool(org_id=current_user.org_id, bundle_id=bundle.id, tool_pattern=pattern))
	await db.flush()
	after = await _present(db, bundle)
	await log_admin_action(
		db, org_id=current_user.org_id, actor_id=current_user.id, actor_email=current_user.email,
		action="mcp_bundle.updated", resource_type="mcp_bundle", resource_id=str(bundle.id),
		before={"tools": before.tools, "is_active": before.is_active},
		after={"tools": after.tools, "is_active": after.is_active}, ip_address=get_ip(request),
	)
	await db.commit()
	return after


@router.delete("/{bundle_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bundle(
	bundle_id: UUID, request: Request, current_user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> None:
	_require_admin(current_user)
	bundle = await _get_owned(db, bundle_id, current_user.org_id)
	await log_admin_action(
		db, org_id=current_user.org_id, actor_id=current_user.id, actor_email=current_user.email,
		action="mcp_bundle.deleted", resource_type="mcp_bundle", resource_id=str(bundle.id),
		before={"slug": bundle.slug}, ip_address=get_ip(request),
	)
	await db.delete(bundle)
	await db.commit()


@router.put("/{bundle_id}/keys/{api_key_id}", response_model=McpBundleResponse)
async def attach_key(
	bundle_id: UUID, api_key_id: UUID, request: Request, current_user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> McpBundleResponse:
	"""Attach an API key. From then on the key can only use MCP through its bundles."""
	_require_admin(current_user)
	bundle = await _get_owned(db, bundle_id, current_user.org_id)
	key = await db.get(ApiKey, api_key_id)
	if key is None or key.org_id != current_user.org_id:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
	if await db.get(ApiKeyMcpBundle, (api_key_id, bundle_id)) is None:
		db.add(ApiKeyMcpBundle(api_key_id=api_key_id, bundle_id=bundle_id, org_id=current_user.org_id))
		await db.flush()
		await log_admin_action(
			db, org_id=current_user.org_id, actor_id=current_user.id, actor_email=current_user.email,
			action="mcp_bundle.key_attached", resource_type="mcp_bundle", resource_id=str(bundle.id),
			after={"api_key_id": str(api_key_id)}, ip_address=get_ip(request),
		)
	await db.commit()
	return await _present(db, bundle)


@router.delete("/{bundle_id}/keys/{api_key_id}", response_model=McpBundleResponse)
async def detach_key(
	bundle_id: UUID, api_key_id: UUID, request: Request, current_user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> McpBundleResponse:
	_require_admin(current_user)
	bundle = await _get_owned(db, bundle_id, current_user.org_id)
	link = await db.get(ApiKeyMcpBundle, (api_key_id, bundle_id))
	if link is not None and link.org_id == current_user.org_id:
		await db.delete(link)
		await log_admin_action(
			db, org_id=current_user.org_id, actor_id=current_user.id, actor_email=current_user.email,
			action="mcp_bundle.key_detached", resource_type="mcp_bundle", resource_id=str(bundle.id),
			before={"api_key_id": str(api_key_id)}, ip_address=get_ip(request),
		)
		await db.commit()
	return await _present(db, bundle)
