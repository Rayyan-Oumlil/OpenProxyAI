"""Admin API for taint-tracking trust rules: /api/v1/mcp-trust-rules."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import CurrentUser, get_db
from app.models.tool_trust_rule import ToolTrustRule
from app.schemas.mcp_trust_rule import TrustRuleCreateRequest, TrustRuleResponse
from app.services.admin_audit_service import get_ip, log_admin_action

router = APIRouter(prefix="/api/v1/mcp-trust-rules", tags=["MCP Gateway"])

_ADMIN_ONLY = "Only organization admins can manage tool trust rules"


def _require_admin(user) -> None:
	if user.role != "admin":
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=_ADMIN_ONLY)


@router.get("", response_model=list[TrustRuleResponse])
async def list_rules(current_user: CurrentUser, db: AsyncSession = Depends(get_db)) -> list[TrustRuleResponse]:
	rows = await db.scalars(
		select(ToolTrustRule).where(ToolTrustRule.org_id == current_user.org_id)
		.order_by(ToolTrustRule.rule, ToolTrustRule.tool_pattern)
	)
	return [TrustRuleResponse.model_validate(r) for r in rows.all()]


@router.post("", response_model=TrustRuleResponse, status_code=status.HTTP_201_CREATED)
async def create_rule(
	payload: TrustRuleCreateRequest, request: Request, current_user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> TrustRuleResponse:
	_require_admin(current_user)
	rule = ToolTrustRule(
		org_id=current_user.org_id, tool_pattern=payload.tool_pattern, rule=payload.rule, created_by=current_user.id
	)
	db.add(rule)
	try:
		await db.flush()
	except IntegrityError as exc:
		raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="That rule already exists") from exc
	await log_admin_action(
		db, org_id=current_user.org_id, actor_id=current_user.id, actor_email=current_user.email,
		action="mcp_trust_rule.created", resource_type="mcp_trust_rule", resource_id=str(rule.id),
		after=payload.model_dump(), ip_address=get_ip(request),
	)
	await db.commit()
	return TrustRuleResponse.model_validate(rule)


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(
	rule_id: UUID, request: Request, current_user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> None:
	_require_admin(current_user)
	rule = await db.get(ToolTrustRule, rule_id)
	if rule is None or rule.org_id != current_user.org_id:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")
	await log_admin_action(
		db, org_id=current_user.org_id, actor_id=current_user.id, actor_email=current_user.email,
		action="mcp_trust_rule.deleted", resource_type="mcp_trust_rule", resource_id=str(rule.id),
		before={"tool_pattern": rule.tool_pattern, "rule": rule.rule}, ip_address=get_ip(request),
	)
	await db.delete(rule)
	await db.commit()
