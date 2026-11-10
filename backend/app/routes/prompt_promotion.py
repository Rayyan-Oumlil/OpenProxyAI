"""Promoting a draft prompt template to live (Phase 3, slice 6).

With the org's ``prompt_promotion_gate`` on, editing a template makes a draft. ``POST .../promote`` makes it the live version,
but only if an eval run vouches for it (see ``services/prompt_gate.py``). An admin may override with a written reason, which is
audited with the reason. Everything here is admin-only except reading the status.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import CurrentUser, get_db, get_redis
from app.models.prompt_template import PromptTemplate
from app.services.admin_audit_service import get_ip, log_admin_action
from app.services.policy_service import PolicyConfig, policy_store
from app.services.prompt_gate import GateResult, check_gate

router = APIRouter(prefix="/api/v1/prompt-templates", tags=["Prompt promotion"])

_READ_ROLES = frozenset({"admin", "developer"})
MIN_OVERRIDE_REASON_CHARS = 10


class PromoteRequest(BaseModel):
	model_config = ConfigDict(extra="forbid")

	override: bool = False  # promote even though the gate is not satisfied; needs a reason and is audited
	reason: str | None = Field(default=None, max_length=500)


class PromotionStatus(BaseModel):
	template_id: UUID
	name: str
	version: int
	status: str  # draft, active or retired
	gate_enabled: bool
	requirements: dict
	passes_gate: bool
	qualifying_run: dict | None
	best_run: dict | None  # the closest run, when none qualifies
	reasons: list[str]  # what is missing


class PromoteResponse(BaseModel):
	template_id: UUID
	name: str
	version: int
	status: str
	previous_version: int | None
	run_id: UUID | None  # the run that vouched for it
	overridden: bool


def _requirements(policy: PolicyConfig) -> dict:
	return {"min_pass_rate": policy.prompt_gate_min_pass_rate, "min_items": policy.prompt_gate_min_items}


async def _load(db: AsyncSession, org_id: UUID, template_id: UUID) -> PromptTemplate:
	template = await db.scalar(select(PromptTemplate).where(PromptTemplate.id == template_id, PromptTemplate.org_id == org_id))
	if template is None:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
	return template


@router.get("/{template_id}/promotion", response_model=PromotionStatus)
async def promotion_status(
	template_id: UUID, current_user: CurrentUser, db: AsyncSession = Depends(get_db), redis: Redis = Depends(get_redis),
) -> PromotionStatus:
	"""Whether this template could be promoted now, and if not, exactly what is missing."""
	if current_user.role not in _READ_ROLES:
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin or developer role required")
	template = await _load(db, current_user.org_id, template_id)
	policy = await policy_store.load(current_user.org_id, db, redis)
	gate = await check_gate(db, current_user.org_id, template, policy) if policy.prompt_promotion_gate else GateResult(True, None, None, [])
	return PromotionStatus(
		template_id=template.id, name=template.name, version=template.version, status=template.status,
		gate_enabled=policy.prompt_promotion_gate, requirements=_requirements(policy), passes_gate=gate.passed,
		qualifying_run=gate.qualifying.as_dict() if gate.qualifying else None, best_run=gate.best.as_dict() if gate.best else None,
		reasons=gate.reasons,
	)


@router.post("/{template_id}/promote", response_model=PromoteResponse)
async def promote(
	template_id: UUID, payload: PromoteRequest, request: Request, current_user: CurrentUser,
	db: AsyncSession = Depends(get_db), redis: Redis = Depends(get_redis),
) -> PromoteResponse:
	"""Make a draft the live version of its prompt. The version it replaces is retired."""
	if current_user.role != "admin":
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only organization admins can promote a prompt")
	target = await _load(db, current_user.org_id, template_id)

	# Lock every version of this prompt for the rest of the transaction, so two promotions cannot both leave a live version.
	family = list(await db.scalars(
		select(PromptTemplate).where(PromptTemplate.org_id == current_user.org_id, PromptTemplate.name == target.name).with_for_update()
	))
	target = next(t for t in family if t.id == target.id)  # re-read under the lock
	if target.status != "draft":
		raise HTTPException(
			status_code=status.HTTP_409_CONFLICT,
			detail={"error": "not_a_draft", "detail": f"Only a draft can be promoted; this version is {target.status}."},
		)

	policy = await policy_store.load(current_user.org_id, db, redis)
	gate = GateResult(True, None, None, [])
	if policy.prompt_promotion_gate:
		gate = await check_gate(db, current_user.org_id, target, policy)
	overridden = not gate.passed
	reason = (payload.reason or "").strip()
	if overridden:
		if not payload.override:
			raise HTTPException(
				status_code=status.HTTP_409_CONFLICT,
				detail={
					"error": "promotion_gate_failed",
					"detail": "No eval run vouches for this prompt yet. " + "; ".join(gate.reasons) + ".",
					"reasons": gate.reasons, "requirements": _requirements(policy), "best_run": gate.best.as_dict() if gate.best else None,
				},
			)
		if len(reason) < MIN_OVERRIDE_REASON_CHARS:
			raise HTTPException(
				status_code=422,
				detail={"error": "override_needs_reason", "detail": f"An override needs a written reason of at least {MIN_OVERRIDE_REASON_CHARS} characters."},
			)

	previous = [t for t in family if t.status == "active"]
	for old in previous:
		old.status, old.is_active = "retired", False
	target.status, target.is_active = "active", True

	await log_admin_action(
		db, org_id=current_user.org_id, actor_id=current_user.id, actor_email=current_user.email,
		action="prompt_template.promoted_with_override" if overridden else "prompt_template.promoted",
		resource_type="prompt_template", resource_id=str(target.id),
		before={"live_versions": [t.version for t in previous]},
		after={
			"name": target.name, "version": target.version, "gate_enabled": policy.prompt_promotion_gate,
			"run_id": str(gate.qualifying.run_id) if gate.qualifying else None,
			"pass_rate": gate.qualifying.pass_rate if gate.qualifying else None,
			**({"override_reason": reason, "unmet": gate.reasons} if overridden else {}),
		},
		ip_address=get_ip(request),
	)
	await db.commit()
	return PromoteResponse(
		template_id=target.id, name=target.name, version=target.version, status=target.status,
		previous_version=previous[0].version if previous else None, run_id=gate.qualifying.run_id if gate.qualifying else None,
		overridden=overridden,
	)
