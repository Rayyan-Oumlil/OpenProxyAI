"""Experiment management — CRUD and results for A/B testing."""

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from redis.asyncio import Redis
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import set_session_org_id
from app.dependencies import CurrentUser, get_db, get_redis
from app.models.experiment import Experiment, ExperimentVariant
from app.models.request_score import RequestScore
from app.schemas.experiment import (
	ExperimentCreate,
	ExperimentResponse,
	ExperimentResultsResponse,
	ExperimentUpdate,
	ExperimentVariantResponse,
	ScoreAggregate,
	VariantMetrics,
)
from app.services.admin_audit_service import get_ip, log_admin_action
from app.services.policy_service import policy_service, policy_store

router = APIRouter(prefix="/api/v1/experiments", tags=["Experiments"])

_ADMIN_ONLY = "Only admins can manage experiments"


async def _ensure_experiment_models_on_allowlist(
	org_id: UUID,
	db: AsyncSession,
	redis: Redis,
	target_model: str,
	variant_models: list[str],
) -> None:
	"""Reject create/update when org has a non-empty model allowlist and a model is missing.

	Mirrors runtime policy: empty allowlist means all models are allowed.
	"""
	policy = await policy_store.load(org_id, db, redis)
	bad: list[str] = []
	if not policy_service.is_model_on_allowlist(target_model, policy):
		bad.append(target_model)
	for m in variant_models:
		if not policy_service.is_model_on_allowlist(m, policy) and m not in bad:
			bad.append(m)
	if bad:
		raise HTTPException(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail="These models are not on the organization policy allowlist: " + ", ".join(bad),
		)


def _to_response(experiment: Experiment) -> ExperimentResponse:
	return ExperimentResponse(
		id=experiment.id,
		org_id=experiment.org_id,
		name=experiment.name,
		target_model=experiment.target_model,
		is_active=experiment.is_active,
		variants=[
			ExperimentVariantResponse(
				id=v.id,
				experiment_id=v.experiment_id,
				model=v.model,
				traffic_weight=v.traffic_weight,
			)
			for v in experiment.variants
		],
		created_at=experiment.created_at,
	)


@router.get("", response_model=list[ExperimentResponse])
async def list_experiments(
	current_user: CurrentUser,
	db: AsyncSession = Depends(get_db),
) -> list[ExperimentResponse]:
	await set_session_org_id(db, current_user.org_id)
	rows = await db.scalars(
		select(Experiment)
		.where(Experiment.org_id == current_user.org_id)
		.options(selectinload(Experiment.variants))
		.order_by(Experiment.created_at.desc())
	)
	experiments = list(rows.all())
	return [_to_response(e) for e in experiments]


@router.post("", response_model=ExperimentResponse, status_code=status.HTTP_201_CREATED)
async def create_experiment(
	payload: ExperimentCreate,
	request: Request,
	current_user: CurrentUser,
	db: AsyncSession = Depends(get_db),
	redis: Redis = Depends(get_redis),
) -> ExperimentResponse:
	if current_user.role != "admin":
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=_ADMIN_ONLY)

	# RLS on experiments/experiment_variants requires app.current_org_id before INSERT.
	await set_session_org_id(db, current_user.org_id)
	# Validate against policy allowlist (uses policy_store; must not 500 on bad org.settings.policy).
	await _ensure_experiment_models_on_allowlist(
		current_user.org_id,
		db,
		redis,
		payload.target_model,
		[v.model for v in payload.variants],
	)
	experiment = Experiment(
		org_id=current_user.org_id,
		name=payload.name,
		target_model=payload.target_model,
		is_active=True,
	)
	db.add(experiment)
	await db.flush()

	for v in payload.variants:
		db.add(
			ExperimentVariant(
				experiment_id=experiment.id,
				model=v.model,
				traffic_weight=v.traffic_weight,
			)
		)
	await db.refresh(experiment, ["variants"])

	await log_admin_action(
		db,
		org_id=current_user.org_id,
		actor_id=current_user.id,
		actor_email=current_user.email,
		action="experiment.created",
		resource_type="experiment",
		resource_id=str(experiment.id),
		before=None,
		after={"name": experiment.name, "target_model": experiment.target_model},
		ip_address=get_ip(request),
	)

	await db.commit()
	await db.refresh(experiment)
	await db.refresh(experiment, ["variants"])
	return _to_response(experiment)


@router.get("/{experiment_id}", response_model=ExperimentResponse)
async def get_experiment(
	experiment_id: UUID,
	current_user: CurrentUser,
	db: AsyncSession = Depends(get_db),
) -> ExperimentResponse:
	await set_session_org_id(db, current_user.org_id)
	experiment = await db.scalar(
		select(Experiment)
		.where(
			Experiment.id == experiment_id,
			Experiment.org_id == current_user.org_id,
		)
		.options(selectinload(Experiment.variants))
	)
	if experiment is None:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Experiment not found")
	return _to_response(experiment)


@router.patch("/{experiment_id}", response_model=ExperimentResponse)
async def update_experiment(
	experiment_id: UUID,
	payload: ExperimentUpdate,
	request: Request,
	current_user: CurrentUser,
	db: AsyncSession = Depends(get_db),
	redis: Redis = Depends(get_redis),
) -> ExperimentResponse:
	if current_user.role != "admin":
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=_ADMIN_ONLY)

	await set_session_org_id(db, current_user.org_id)
	experiment = await db.scalar(
		select(Experiment)
		.where(
			Experiment.id == experiment_id,
			Experiment.org_id == current_user.org_id,
		)
		.options(selectinload(Experiment.variants))
	)
	if experiment is None:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Experiment not found")

	updates = payload.model_dump(exclude_unset=True)
	if "variants" in updates:
		new_variants = updates["variants"]
		if not new_variants:
			raise HTTPException(
				status_code=status.HTTP_400_BAD_REQUEST,
				detail="variants must not be empty",
			)
		variant_models = [v["model"] for v in new_variants]
	else:
		variant_models = [v.model for v in experiment.variants]
	await _ensure_experiment_models_on_allowlist(
		current_user.org_id,
		db,
		redis,
		experiment.target_model,
		variant_models,
	)

	if "name" in updates and updates["name"] is not None:
		experiment.name = updates["name"]
	if "is_active" in updates:
		experiment.is_active = updates["is_active"]
	if "variants" in updates:
		new_variants = updates["variants"]
		for v in experiment.variants:
			await db.delete(v)
		for v in new_variants:
			db.add(
				ExperimentVariant(
					experiment_id=experiment.id,
					model=v["model"],
					traffic_weight=v["traffic_weight"],
				)
			)

	await log_admin_action(
		db,
		org_id=current_user.org_id,
		actor_id=current_user.id,
		actor_email=current_user.email,
		action="experiment.updated",
		resource_type="experiment",
		resource_id=str(experiment_id),
		before=None,
		after=updates,
		ip_address=get_ip(request),
	)

	await db.commit()
	await db.refresh(experiment)
	await db.refresh(experiment, ["variants"])
	return _to_response(experiment)


@router.delete("/{experiment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_experiment(
	experiment_id: UUID,
	request: Request,
	current_user: CurrentUser,
	db: AsyncSession = Depends(get_db),
) -> None:
	if current_user.role != "admin":
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=_ADMIN_ONLY)

	await set_session_org_id(db, current_user.org_id)
	experiment = await db.scalar(
		select(Experiment).where(
			Experiment.id == experiment_id,
			Experiment.org_id == current_user.org_id,
		)
	)
	if experiment is None:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Experiment not found")

	await log_admin_action(
		db,
		org_id=current_user.org_id,
		actor_id=current_user.id,
		actor_email=current_user.email,
		action="experiment.deleted",
		resource_type="experiment",
		resource_id=str(experiment_id),
		before={"name": experiment.name},
		after=None,
		ip_address=get_ip(request),
	)

	await db.delete(experiment)
	await db.commit()


@router.post("/{experiment_id}/start", response_model=ExperimentResponse)
async def start_experiment(
	experiment_id: UUID,
	request: Request,
	current_user: CurrentUser,
	db: AsyncSession = Depends(get_db),
) -> ExperimentResponse:
	if current_user.role != "admin":
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=_ADMIN_ONLY)

	await set_session_org_id(db, current_user.org_id)
	experiment = await db.scalar(
		select(Experiment)
		.where(
			Experiment.id == experiment_id,
			Experiment.org_id == current_user.org_id,
		)
		.options(selectinload(Experiment.variants))
	)
	if experiment is None:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Experiment not found")

	experiment.is_active = True

	await log_admin_action(
		db,
		org_id=current_user.org_id,
		actor_id=current_user.id,
		actor_email=current_user.email,
		action="experiment.started",
		resource_type="experiment",
		resource_id=str(experiment_id),
		before={"is_active": False},
		after={"is_active": True},
		ip_address=get_ip(request),
	)

	await db.commit()
	await db.refresh(experiment)
	await db.refresh(experiment, ["variants"])
	return _to_response(experiment)


@router.post("/{experiment_id}/stop", response_model=ExperimentResponse)
async def stop_experiment(
	experiment_id: UUID,
	request: Request,
	current_user: CurrentUser,
	db: AsyncSession = Depends(get_db),
) -> ExperimentResponse:
	if current_user.role != "admin":
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=_ADMIN_ONLY)

	await set_session_org_id(db, current_user.org_id)
	experiment = await db.scalar(
		select(Experiment)
		.where(
			Experiment.id == experiment_id,
			Experiment.org_id == current_user.org_id,
		)
		.options(selectinload(Experiment.variants))
	)
	if experiment is None:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Experiment not found")

	experiment.is_active = False

	await log_admin_action(
		db,
		org_id=current_user.org_id,
		actor_id=current_user.id,
		actor_email=current_user.email,
		action="experiment.stopped",
		resource_type="experiment",
		resource_id=str(experiment_id),
		before={"is_active": True},
		after={"is_active": False},
		ip_address=get_ip(request),
	)

	await db.commit()
	await db.refresh(experiment)
	await db.refresh(experiment, ["variants"])
	return _to_response(experiment)


@router.get("/{experiment_id}/results", response_model=ExperimentResultsResponse)
async def get_experiment_results(
	experiment_id: UUID,
	current_user: CurrentUser,
	db: AsyncSession = Depends(get_db),
) -> ExperimentResultsResponse:
	await set_session_org_id(db, current_user.org_id)
	experiment = await db.scalar(
		select(Experiment)
		.where(
			Experiment.id == experiment_id,
			Experiment.org_id == current_user.org_id,
		)
		.options(selectinload(Experiment.variants))
	)
	if experiment is None:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Experiment not found")

	# Aggregate from request_logs where request_metadata.experiment.experiment_id matches
	stmt = text("""
		SELECT
			model,
			COUNT(*)::int AS request_count,
			AVG(latency_ms)::float AS avg_latency_ms,
			COALESCE(SUM(cost_usd), 0) AS total_cost_usd,
			COALESCE(SUM(prompt_tokens), 0)::int AS total_prompt_tokens,
			COALESCE(SUM(completion_tokens), 0)::int AS total_completion_tokens,
			COUNT(*) FILTER (WHERE status_code IN (403, 446))::int AS policy_violations
		FROM request_logs
		WHERE org_id = :org_id
		  AND request_metadata->'experiment'->>'experiment_id' = :experiment_id
		GROUP BY model
	""")
	result = await db.execute(
		stmt,
		{"org_id": str(current_user.org_id), "experiment_id": str(experiment_id)},
	)
	rows = result.mappings().all()

	# Aggregate scores per variant from request_scores
	score_stmt = text("""
		SELECT variant_id, score_name,
			AVG(value)::float AS avg_val, COUNT(*)::int AS cnt
		FROM request_scores
		WHERE experiment_id = :experiment_id AND variant_id IS NOT NULL
		GROUP BY variant_id, score_name
	""")
	score_result = await db.execute(
		score_stmt, {"experiment_id": str(experiment_id)}
	)
	score_rows = score_result.mappings().all()
	variant_scores: dict[str, list[dict]] = {}
	for sr in score_rows:
		vid = str(sr["variant_id"])
		variant_scores.setdefault(vid, []).append(
			{"name": sr["score_name"], "avg": float(sr["avg_val"]), "count": sr["cnt"]}
		)

	model_to_variant_id = {v.model: str(v.id) for v in experiment.variants}
	variants = []
	for row in rows:
		vid = model_to_variant_id.get(row["model"])
		scores = [
			ScoreAggregate(name=s["name"], avg=s["avg"], count=s["count"])
			for s in variant_scores.get(vid, [])
		]
		variants.append(
			VariantMetrics(
				model=row["model"],
				request_count=row["request_count"],
				avg_latency_ms=row["avg_latency_ms"],
				total_cost_usd=Decimal(str(row["total_cost_usd"])),
				total_prompt_tokens=row["total_prompt_tokens"],
				total_completion_tokens=row["total_completion_tokens"],
				policy_violations=row["policy_violations"],
				scores=scores,
			)
		)
	return ExperimentResultsResponse(variants=variants)
