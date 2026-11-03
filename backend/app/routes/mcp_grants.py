"""Admin API for per-tool grants behind the MCP gateway: /api/v1/mcp-grants."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import CurrentUser, get_db
from app.models.tool_grant import ToolGrant
from app.schemas.mcp_grant import McpGrantCreateRequest, McpGrantResponse
from app.services.admin_audit_service import get_ip, log_admin_action

router = APIRouter(prefix="/api/v1/mcp-grants", tags=["MCP Gateway"])

_ADMIN_ONLY = "Only organization admins can manage MCP tool grants"


def _require_admin(user) -> None:
	if user.role != "admin":
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=_ADMIN_ONLY)


@router.get("", response_model=list[McpGrantResponse])
async def list_grants(current_user: CurrentUser, db: AsyncSession = Depends(get_db)) -> list[McpGrantResponse]:
	rows = await db.scalars(
		select(ToolGrant).where(ToolGrant.org_id == current_user.org_id)
		.order_by(ToolGrant.subject_type, ToolGrant.subject_id, ToolGrant.tool_pattern)
	)
	return [McpGrantResponse.model_validate(g) for g in rows.all()]


@router.post("", response_model=McpGrantResponse, status_code=status.HTTP_201_CREATED)
async def create_grant(
	payload: McpGrantCreateRequest,
	request: Request,
	current_user: CurrentUser,
	db: AsyncSession = Depends(get_db),
) -> McpGrantResponse:
	_require_admin(current_user)
	grant = ToolGrant(
		org_id=current_user.org_id, subject_type=payload.subject_type, subject_id=payload.subject_id,
		tool_pattern=payload.tool_pattern, effect=payload.effect, created_by=current_user.id,
	)
	db.add(grant)
	try:
		await db.flush()
	except IntegrityError as exc:
		raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="That grant already exists") from exc
	await log_admin_action(
		db, org_id=current_user.org_id, actor_id=current_user.id, actor_email=current_user.email,
		action="mcp_grant.created", resource_type="mcp_grant", resource_id=str(grant.id),
		after=payload.model_dump(), ip_address=get_ip(request),
	)
	await db.commit()
	return McpGrantResponse.model_validate(grant)


@router.delete("/{grant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_grant(
	grant_id: UUID,
	request: Request,
	current_user: CurrentUser,
	db: AsyncSession = Depends(get_db),
) -> None:
	_require_admin(current_user)
	grant = await db.get(ToolGrant, grant_id)
	if grant is None or grant.org_id != current_user.org_id:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grant not found")
	await log_admin_action(
		db, org_id=current_user.org_id, actor_id=current_user.id, actor_email=current_user.email,
		action="mcp_grant.deleted", resource_type="mcp_grant", resource_id=str(grant.id),
		before={"subject_type": grant.subject_type, "subject_id": grant.subject_id,
		        "tool_pattern": grant.tool_pattern, "effect": grant.effect},
		ip_address=get_ip(request),
	)
	await db.delete(grant)
	await db.commit()
