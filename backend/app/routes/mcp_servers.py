"""Admin API for the upstream MCP servers behind the gateway: /api/v1/mcp-servers."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import CurrentUser, get_db
from app.models.mcp_server import McpServer
from app.models.mcp_tool import McpTool
from app.schemas.mcp_server import (
	McpServerCreateRequest,
	McpServerResponse,
	McpServerUpdateRequest,
	McpToolResponse,
)
from app.services.admin_audit_service import get_ip, log_admin_action
from app.services.crypto_service import decrypt, encrypt
from app.services.mcp_client import McpUpstreamError, call_upstream
from app.services.mcp_gateway import UpstreamServer, list_server_tools
from app.services.mcp_pinning import PIN_OFF, DbPinStore, approve_tool, block_tool
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
		pin_mode=payload.pin_mode,
		scan_mode=payload.scan_mode,
	)
	db.add(server)
	try:
		await db.flush()
	except IntegrityError as exc:
		raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"An MCP server named {payload.name} already exists") from exc
	await log_admin_action(
		db, org_id=current_user.org_id, actor_id=current_user.id, actor_email=current_user.email,
		action="mcp_server.created", resource_type="mcp_server", resource_id=str(server.id),
		after={"name": server.name, "url": server.url, "has_auth": bool(server.auth_header_encrypted), "pin_mode": server.pin_mode,
		       "scan_mode": server.scan_mode},
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
	before = {"is_active": server.is_active, "pin_mode": server.pin_mode, "scan_mode": server.scan_mode}
	if payload.is_active is not None:
		server.is_active = payload.is_active
	if payload.pin_mode is not None:
		server.pin_mode = payload.pin_mode
	if payload.scan_mode is not None:
		server.scan_mode = payload.scan_mode
	await log_admin_action(
		db, org_id=current_user.org_id, actor_id=current_user.id, actor_email=current_user.email,
		action="mcp_server.updated", resource_type="mcp_server", resource_id=str(server.id),
		before=before, after={"is_active": server.is_active, "pin_mode": server.pin_mode, "scan_mode": server.scan_mode},
		ip_address=get_ip(request),
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


async def _get_owned_tool(db: AsyncSession, server_id: UUID, tool_id: UUID, org_id: UUID) -> McpTool:
	tool = await db.get(McpTool, tool_id)
	if tool is None or tool.org_id != org_id or tool.server_id != server_id:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="MCP tool not found")
	return tool


async def _tools_of(db: AsyncSession, server_id: UUID, org_id: UUID) -> list[McpToolResponse]:
	rows = await db.scalars(
		select(McpTool).where(McpTool.org_id == org_id, McpTool.server_id == server_id).order_by(McpTool.name)
	)
	return [McpToolResponse.model_validate(t) for t in rows.all()]


@router.get("/{server_id}/tools", response_model=list[McpToolResponse])
async def list_pinned_tools(
	server_id: UUID, current_user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> list[McpToolResponse]:
	await _get_owned(db, server_id, current_user.org_id)
	return await _tools_of(db, server_id, current_user.org_id)


@router.post("/{server_id}/sync", response_model=list[McpToolResponse])
async def sync_pinned_tools(
	server_id: UUID, current_user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> list[McpToolResponse]:
	"""Fetch the live tool list now and record it (new tools, drift)."""
	_require_admin(current_user)
	server = await _get_owned(db, server_id, current_user.org_id)
	if server.pin_mode == PIN_OFF:
		raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Tool pinning is off for this server")
	upstream = UpstreamServer(
		id=server.id, name=server.name, url=server.url, pin_mode=server.pin_mode,
		auth_header=decrypt(server.auth_header_encrypted) if server.auth_header_encrypted else None,
	)
	try:
		live = await list_server_tools(upstream, call_upstream)
	except McpUpstreamError as exc:
		raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Upstream MCP server unavailable") from exc
	await DbPinStore(db, current_user.org_id).reconcile(upstream, live)
	await db.commit()
	return await _tools_of(db, server_id, current_user.org_id)


async def _review_tool(
	action: str, server_id: UUID, tool_id: UUID, request: Request, current_user, db: AsyncSession
) -> McpToolResponse:
	_require_admin(current_user)
	tool = await _get_owned_tool(db, server_id, tool_id, current_user.org_id)
	before = {"status": tool.status, "approved_hash": tool.approved_hash, "current_hash": tool.current_hash}
	if action == "approve":
		approve_tool(tool, current_user.id)
	else:
		block_tool(tool)
	await log_admin_action(
		db, org_id=current_user.org_id, actor_id=current_user.id, actor_email=current_user.email,
		action=f"mcp_tool.{action}", resource_type="mcp_tool", resource_id=str(tool.id),
		before=before, after={"status": tool.status, "approved_hash": tool.approved_hash, "name": tool.name},
		ip_address=get_ip(request),
	)
	await db.commit()
	return McpToolResponse.model_validate(tool)


@router.post("/{server_id}/tools/{tool_id}/approve", response_model=McpToolResponse)
async def approve_pinned_tool(
	server_id: UUID, tool_id: UUID, request: Request, current_user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> McpToolResponse:
	"""Approve the definition the server advertises right now (also unblocks a blocked tool)."""
	return await _review_tool("approve", server_id, tool_id, request, current_user, db)


@router.post("/{server_id}/tools/{tool_id}/block", response_model=McpToolResponse)
async def block_pinned_tool(
	server_id: UUID, tool_id: UUID, request: Request, current_user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> McpToolResponse:
	return await _review_tool("block", server_id, tool_id, request, current_user, db)
