"""Admin API for evaluators and eval runs: /api/v1/evaluators and /api/v1/eval-runs (admins only). Phase 3, slice 4.

A run spends real money (candidate and judge calls), so it is admin-only, capped by ``max_cost_usd``, limited to
``MAX_ACTIVE_RUNS`` at a time per organization, and every create and cancel is in the admin audit log.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import CurrentUser, get_db, get_redis
from app.models.dataset import Dataset, DatasetItem
from app.models.evaluation import EvalRun, EvalRunItem, Evaluator
from app.models.prompt_template import PromptTemplate
from app.schemas.evaluation import (
	MAX_ACTIVE_RUNS,
	EvalRunCreate,
	EvalRunItemResponse,
	EvalRunResponse,
	EvaluatorCreate,
	EvaluatorResponse,
)
from app.services import eval_runner
from app.services.admin_audit_service import get_ip, log_admin_action
from app.services.evaluators import validate_config
from app.services.policy_service import policy_service, policy_store

evaluators_router = APIRouter(prefix="/api/v1/evaluators", tags=["Evaluators"])
runs_router = APIRouter(prefix="/api/v1/eval-runs", tags=["Eval runs"])

_ADMIN_ONLY = "Only organization admins can manage evaluators and eval runs"


def _require_admin(user) -> None:
	if user.role != "admin":
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=_ADMIN_ONLY)


def _refuse(code: int, error: str, detail: str) -> HTTPException:
	return HTTPException(status_code=code, detail={"error": error, "detail": detail})


# ── evaluators ───────────────────────────────────────────────────────────────


def _evaluator_response(e: Evaluator) -> EvaluatorResponse:
	return EvaluatorResponse(id=e.id, name=e.name, type=e.type, config=e.config, created_at=e.created_at)


async def _load_evaluator(db: AsyncSession, org_id: UUID, evaluator_id: UUID) -> Evaluator:
	evaluator = await db.get(Evaluator, evaluator_id)
	if evaluator is None or evaluator.org_id != org_id:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluator not found")
	return evaluator


@evaluators_router.post("", response_model=EvaluatorResponse, status_code=status.HTTP_201_CREATED)
async def create_evaluator(payload: EvaluatorCreate, request: Request, current_user: CurrentUser, db: AsyncSession = Depends(get_db)) -> EvaluatorResponse:
	_require_admin(current_user)
	try:
		config = validate_config(payload.type, payload.config)
	except ValueError as exc:
		raise _refuse(422, "invalid_evaluator", str(exc)) from None
	evaluator = Evaluator(org_id=current_user.org_id, name=payload.name, type=payload.type, config=config, created_by=current_user.id)
	db.add(evaluator)
	try:
		await db.flush()
	except IntegrityError:
		await db.rollback()
		raise _refuse(409, "evaluator_exists", "An evaluator with this name already exists.") from None
	await log_admin_action(
		db, org_id=current_user.org_id, actor_id=current_user.id, actor_email=current_user.email, action="evaluator.created",
		resource_type="evaluator", resource_id=str(evaluator.id), after={"name": evaluator.name, "type": evaluator.type}, ip_address=get_ip(request),
	)
	await db.commit()
	await db.refresh(evaluator)
	return _evaluator_response(evaluator)


@evaluators_router.get("", response_model=list[EvaluatorResponse])
async def list_evaluators(current_user: CurrentUser, db: AsyncSession = Depends(get_db)) -> list[EvaluatorResponse]:
	_require_admin(current_user)
	rows = await db.scalars(select(Evaluator).where(Evaluator.org_id == current_user.org_id).order_by(Evaluator.name))
	return [_evaluator_response(e) for e in rows.all()]


@evaluators_router.get("/{evaluator_id}", response_model=EvaluatorResponse)
async def get_evaluator(evaluator_id: UUID, current_user: CurrentUser, db: AsyncSession = Depends(get_db)) -> EvaluatorResponse:
	_require_admin(current_user)
	return _evaluator_response(await _load_evaluator(db, current_user.org_id, evaluator_id))


@evaluators_router.delete("/{evaluator_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_evaluator(evaluator_id: UUID, request: Request, current_user: CurrentUser, db: AsyncSession = Depends(get_db)) -> Response:
	"""Past runs keep working: each stores a copy of the evaluator it used."""
	_require_admin(current_user)
	evaluator = await _load_evaluator(db, current_user.org_id, evaluator_id)
	await log_admin_action(
		db, org_id=current_user.org_id, actor_id=current_user.id, actor_email=current_user.email, action="evaluator.deleted",
		resource_type="evaluator", resource_id=str(evaluator.id), after={"name": evaluator.name}, ip_address=get_ip(request),
	)
	await db.delete(evaluator)
	await db.commit()
	return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── eval runs ────────────────────────────────────────────────────────────────


def _run_response(run: EvalRun) -> EvalRunResponse:
	scored = run.completed_items - run.failed_items
	return EvalRunResponse(
		id=run.id, dataset_id=run.dataset_id, evaluator_id=run.evaluator_id, evaluator=run.evaluator_snapshot,
		prompt_template_id=run.prompt_template_id, candidate_model=run.candidate_model, status=run.status,
		total_items=run.total_items, completed_items=run.completed_items, scored_items=scored, failed_items=run.failed_items,
		passed_items=run.passed_items, mean_score=float(run.score_sum) / scored if scored else None,
		pass_rate=run.passed_items / scored if scored else None, cost_usd=float(run.cost_usd), max_cost_usd=float(run.max_cost_usd),
		error=run.error, created_at=run.created_at, started_at=run.started_at, finished_at=run.finished_at,
	)


async def _load_run(db: AsyncSession, org_id: UUID, run_id: UUID) -> EvalRun:
	run = await db.get(EvalRun, run_id)
	if run is None or run.org_id != org_id:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Eval run not found")
	return run


@runs_router.post("", response_model=EvalRunResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_run(
	payload: EvalRunCreate, request: Request, current_user: CurrentUser, db: AsyncSession = Depends(get_db), redis: Redis = Depends(get_redis),
) -> EvalRunResponse:
	"""Start a run. It executes in the background; poll ``GET /api/v1/eval-runs/{id}`` for progress."""
	_require_admin(current_user)
	org_id = current_user.org_id
	dataset = await db.get(Dataset, payload.dataset_id)
	if dataset is None or dataset.org_id != org_id:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")
	evaluator = await _load_evaluator(db, org_id, payload.evaluator_id)

	system_prompt = payload.system_prompt
	if payload.prompt_template_id is not None:
		template = await db.get(PromptTemplate, payload.prompt_template_id)
		if template is None or template.org_id != org_id:
			raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prompt template not found")
		system_prompt = system_prompt if system_prompt is not None else template.system_message

	policy_config = await policy_store.load(org_id, db, redis)
	models = [payload.candidate_model] + ([evaluator.config["model"]] if evaluator.type == "llm_judge" else [])
	for model in models:
		if not policy_service.is_model_on_allowlist(model, policy_config):
			raise _refuse(422, "model_not_allowed", f"{model} is not on this organization's model allowlist, so a run could not use it.")

	available = int(await db.scalar(select(func.count()).select_from(DatasetItem).where(DatasetItem.dataset_id == dataset.id)) or 0)
	if available == 0:
		raise _refuse(422, "empty_dataset", "This dataset has no items to run.")
	active = int(await db.scalar(select(func.count()).select_from(EvalRun).where(EvalRun.org_id == org_id, EvalRun.status.in_(("queued", "running")))) or 0)
	if active >= MAX_ACTIVE_RUNS:
		raise _refuse(409, "too_many_runs", f"At most {MAX_ACTIVE_RUNS} runs can be active at once. Wait for one to finish or cancel it.")

	run = EvalRun(
		org_id=org_id, dataset_id=dataset.id, evaluator_id=evaluator.id,
		evaluator_snapshot={"name": evaluator.name, "type": evaluator.type, "config": evaluator.config},
		prompt_template_id=payload.prompt_template_id, candidate_model=payload.candidate_model, system_prompt=system_prompt,
		status="queued", total_items=min(payload.max_items, available), max_cost_usd=Decimal(str(payload.max_cost_usd)), created_by=current_user.id,
	)
	db.add(run)
	await db.flush()
	await log_admin_action(
		db, org_id=org_id, actor_id=current_user.id, actor_email=current_user.email, action="eval_run.created", resource_type="eval_run",
		resource_id=str(run.id), after={"dataset": dataset.name, "evaluator": evaluator.name, "candidate_model": run.candidate_model,
		"items": run.total_items, "max_cost_usd": float(run.max_cost_usd)}, ip_address=get_ip(request),
	)
	await db.commit()
	await db.refresh(run)
	eval_runner.start(run.id, org_id, current_user.id, redis)
	return _run_response(run)


@runs_router.get("", response_model=list[EvalRunResponse])
async def list_runs(
	current_user: CurrentUser, db: AsyncSession = Depends(get_db), limit: int = Query(default=20, ge=1, le=100), offset: int = Query(default=0, ge=0),
) -> list[EvalRunResponse]:
	_require_admin(current_user)
	rows = await db.scalars(select(EvalRun).where(EvalRun.org_id == current_user.org_id).order_by(EvalRun.created_at.desc(), EvalRun.id).limit(limit).offset(offset))
	return [_run_response(r) for r in rows.all()]


@runs_router.get("/{run_id}", response_model=EvalRunResponse)
async def get_run(run_id: UUID, current_user: CurrentUser, db: AsyncSession = Depends(get_db)) -> EvalRunResponse:
	_require_admin(current_user)
	return _run_response(await _load_run(db, current_user.org_id, run_id))


@runs_router.get("/{run_id}/items", response_model=list[EvalRunItemResponse])
async def list_run_items(
	run_id: UUID,
	current_user: CurrentUser,
	db: AsyncSession = Depends(get_db),
	outcome: str | None = Query(default=None, pattern="^(passed|failed|error)$"),
	limit: int = Query(default=50, ge=1, le=200),
	offset: int = Query(default=0, ge=0),
) -> list[EvalRunItemResponse]:
	"""Per-item results. ``outcome`` filters: passed, failed (scored below the bar) or error (could not be scored)."""
	_require_admin(current_user)
	run = await _load_run(db, current_user.org_id, run_id)
	query = select(EvalRunItem).where(EvalRunItem.run_id == run.id)
	if outcome == "passed":
		query = query.where(EvalRunItem.passed.is_(True))
	elif outcome == "failed":
		query = query.where(EvalRunItem.passed.is_(False))
	elif outcome == "error":
		query = query.where(EvalRunItem.error.is_not(None))
	rows = await db.scalars(query.order_by(EvalRunItem.created_at, EvalRunItem.id).limit(limit).offset(offset))
	return [
		EvalRunItemResponse(
			id=i.id, dataset_item_id=i.dataset_item_id, output=i.output, score=float(i.score) if i.score is not None else None,
			passed=i.passed, reason=i.reason, error=i.error, cost_usd=float(i.cost_usd), latency_ms=i.latency_ms,
		)
		for i in rows.all()
	]


@runs_router.post("/{run_id}/cancel", response_model=EvalRunResponse)
async def cancel_run(run_id: UUID, request: Request, current_user: CurrentUser, db: AsyncSession = Depends(get_db)) -> EvalRunResponse:
	"""Stop a run. Items already in flight finish; no new item starts."""
	_require_admin(current_user)
	run = await _load_run(db, current_user.org_id, run_id)
	if run.status not in ("queued", "running"):
		raise _refuse(409, "run_finished", f"This run already ended ({run.status}).")
	run.status = "cancelled"
	await log_admin_action(
		db, org_id=current_user.org_id, actor_id=current_user.id, actor_email=current_user.email, action="eval_run.cancelled",
		resource_type="eval_run", resource_id=str(run.id), after={"completed_items": run.completed_items}, ip_address=get_ip(request),
	)
	await db.commit()
	await db.refresh(run)
	return _run_response(run)
