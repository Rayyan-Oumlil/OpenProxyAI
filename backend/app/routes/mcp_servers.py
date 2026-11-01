"""Admin API for the upstream MCP servers behind the gateway: /api/v1/mcp-servers."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import CurrentUser, get_db
from app.models.mcp_server import McpServer
from app.schemas.mcp_server import (
	McpServerCreateRequest,
	McpServerResponse,
	McpServerUpdateRequest,
)
from app.services.admin_audit_service import get_ip, log_admin_action
from app.services.crypto_service import encrypt
from app.utils.ssrf import is_safe_https_url

router = APIRouter(prefix="/api/v1/mcp-servers", tags=["MCP Gateway"])

_ADMIN_ONLY = "Only organization admins can manage MCP servers"


def _require_admin(user) -> None:
	if user.role != "admin":
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=_ADMIN_ONLY)


async def _get_owned(db: AsyncSession, server_id: UUID, org_id: UUID) -> McpServer:
	server = await db.get(McpServer, server_id)
	if server is None or server.org_id != org_id:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="MCP server not found")
	return server


@router.get("", response_model=list[McpServerResponse])
async def list_mcp_servers(current_user: CurrentUser, db: AsyncSession = Depends(get_db)) -> list[McpServerResponse]:
	rows = await db.scalars(
		select(McpServer).where(McpServer.org_id == current_user.org_id).order_by(McpServer.name)
	)
	return [McpServerResponse.from_model(s) for s in rows.all()]


@router.post("", response_model=McpServerResponse, status_code=status.HTTP_201_CREATED)
async def create_mcp_server(
	payload: McpServerCreateRequest,
	request: Request,
	current_user: CurrentUser,
	db: AsyncSession = Depends(get_db),
) -> McpServerResponse:
	_require_admin(current_user)
	if not is_safe_https_url(payload.url):
		raise HTTPException(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail="URL must be HTTPS and resolve to a public address",
		)
	server = McpServer(
		org_id=current_user.org_id,
		name=payload.name,
		url=payload.url,
		auth_header_encrypted=encrypt(payload.auth_header) if payload.auth_header else None,
	)
	db.add(server)
	try:
		await db.flush()
	except IntegrityError as exc:
		raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"An MCP server named {payload.name} already exists") from exc
	await log_admin_action(
		db, org_id=current_user.org_id, actor_id=current_user.id, actor_email=current_user.email,
		action="mcp_server.created", resource_type="mcp_server", resource_id=str(server.id),
		after={"name": server.name, "url": server.url, "has_auth": bool(server.auth_header_encrypted)},
		ip_address=get_ip(request),
	)
	await db.commit()
	return McpServerResponse.from_model(server)


@router.patch("/{server_id}", response_model=McpServerResponse)
async def update_mcp_server(
	server_id: UUID,
	payload: McpServerUpdateRequest,
	request: Request,
	current_user: CurrentUser,
	db: AsyncSession = Depends(get_db),
) -> McpServerResponse:
	_require_admin(current_user)
	server = await _get_owned(db, server_id, current_user.org_id)
	before = {"is_active": server.is_active}
	server.is_active = payload.is_active
	await log_admin_action(
		db, org_id=current_user.org_id, actor_id=current_user.id, actor_email=current_user.email,
		action="mcp_server.updated", resource_type="mcp_server", resource_id=str(server.id),
		before=before, after={"is_active": server.is_active}, ip_address=get_ip(request),
	)
	await db.commit()
	return McpServerResponse.from_model(server)


@router.delete("/{server_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_mcp_server(
	server_id: UUID,
	request: Request,
	current_user: CurrentUser,
	db: AsyncSession = Depends(get_db),
) -> None:
	_require_admin(current_user)
	server = await _get_owned(db, server_id, current_user.org_id)
	await log_admin_action(
		db, org_id=current_user.org_id, actor_id=current_user.id, actor_email=current_user.email,
		action="mcp_server.deleted", resource_type="mcp_server", resource_id=str(server.id),
		before={"name": server.name, "url": server.url}, ip_address=get_ip(request),
	)
	await db.delete(server)
	await db.commit()
