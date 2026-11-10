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
from app.schemas.experiment import (
	AdaptiveStatus,
	ExperimentCreate,
	ExperimentResponse,
	ExperimentResultsResponse,
	ExperimentUpdate,
	ExperimentVariantResponse,
	ScoreAggregate,
	VariantMetrics,
)
from app.services.adaptive_experiments import MetricNotARate, describe, fetch_stats
from app.services.admin_audit_service import get_ip, log_admin_action
from app.services.policy_service import policy_service, policy_store

router = APIRouter(prefix="/api/v1/experiments", tags=["Experiments"])

_ADMIN_ONLY = "Only admins can manage experiments"


def _check_adaptive(mode: str, metric: str | None, variant_count: int, floor: int) -> None:
	"""An adaptive test must be able to run: a metric to read, two variants to compare, and room for the floor."""
	if mode != "adaptive":
		return
	problem = None
	if not metric:
		problem = "an adaptive experiment needs a metric: the name of a feedback score whose values are 0 to 1, for example thumbs"
	elif variant_count < 2:
		problem = "an adaptive experiment needs at least two variants to compare"
	elif floor * variant_count > 100:
		problem = f"a weight_floor of {floor}% for {variant_count} variants adds up to more than 100%"
	if problem:
		raise HTTPException(status_code=422, detail={"error": "invalid_adaptive_experiment", "detail": problem})


def _reset_result(experiment: Experiment) -> None:
	"""Forget a previous outcome: a winner means nothing once the test, its metric or its variants change."""
	experiment.winner_variant_id = None
	experiment.stopped_reason = None
	experiment.adaptive_error = None


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
		mode=experiment.mode,
		metric=experiment.metric,
		min_samples_per_variant=experiment.min_samples_per_variant,
		delta=float(experiment.delta),
		weight_floor=experiment.weight_floor,
		winner_variant_id=experiment.winner_variant_id,
		stopped_reason=experiment.stopped_reason,
		adaptive_error=experiment.adaptive_error,
		adaptive_updated_at=experiment.adaptive_updated_at,
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
	mode = payload.mode or "static"
	floor = payload.weight_floor if payload.weight_floor is not None else 5
	_check_adaptive(mode, payload.metric, len(payload.variants), floor)
	experiment = Experiment(
		org_id=current_user.org_id,
		name=payload.name,
		target_model=payload.target_model,
		is_active=True,
		mode=mode,
		metric=payload.metric,
		min_samples_per_variant=payload.min_samples_per_variant if payload.min_samples_per_variant is not None else 30,
		delta=Decimal(str(payload.delta)) if payload.delta is not None else Decimal("0.0100"),
		weight_floor=floor,
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
		after={"name": experiment.name, "target_model": experiment.target_model, "mode": mode, "metric": payload.metric},
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

	new_mode = updates.get("mode") or experiment.mode
	new_metric = updates["metric"] if "metric" in updates else experiment.metric
	new_floor = updates.get("weight_floor") or experiment.weight_floor
	_check_adaptive(new_mode, new_metric, len(variant_models), new_floor)
	if updates.get("mode") or "metric" in updates or "variants" in updates:
		_reset_result(experiment)
	experiment.mode, experiment.metric, experiment.weight_floor = new_mode, new_metric, new_floor
	if updates.get("min_samples_per_variant") is not None:
		experiment.min_samples_per_variant = updates["min_samples_per_variant"]
	if updates.get("delta") is not None:
		experiment.delta = Decimal(str(updates["delta"]))

	if "name" in updates and updates["name"] is not None:
		experiment.name = updates["name"]
	if "is_active" in updates:
		experiment.is_active = updates["is_active"]
		if updates["is_active"]:
			_reset_result(experiment)
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
	_reset_result(experiment)

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
	experiment.stopped_reason = "manual"

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

	# Aggregate from request_logs where request_metadata.experiment.experiment_id matches, per VARIANT: two variants may use
	# the same model (different prompts or settings), so the model name cannot be the key.
	stmt = text("""
		SELECT
			request_metadata->'experiment'->>'variant_id' AS variant_id,
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
		GROUP BY 1, 2
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
		WHERE org_id = :org_id AND experiment_id = :experiment_id AND variant_id IS NOT NULL
		GROUP BY variant_id, score_name
	""")
	score_result = await db.execute(
		score_stmt, {"org_id": str(current_user.org_id), "experiment_id": str(experiment_id)}
	)
	score_rows = score_result.mappings().all()
	variant_scores: dict[str, list[dict]] = {}
	for sr in score_rows:
		vid = str(sr["variant_id"])
		variant_scores.setdefault(vid, []).append(
			{"name": sr["score_name"], "avg": float(sr["avg_val"]), "count": sr["cnt"]}
		)

	adaptive = None
	chances: dict[str, float] = {}
	if experiment.mode == "adaptive":
		error = experiment.adaptive_error
		try:
			info = describe(experiment, await fetch_stats(db, current_user.org_id, experiment)) if len(experiment.variants) >= 2 else None
		except MetricNotARate as exc:
			info, error = None, str(exc)
		chances = info["probability_best"] if info else {}
		adaptive = AdaptiveStatus(
			metric=experiment.metric or "", ready=bool(info and info["ready"]), min_samples_per_variant=experiment.min_samples_per_variant,
			delta=float(experiment.delta), samples=info["samples"] if info else {}, winner_variant_id=experiment.winner_variant_id,
			stopped_reason=experiment.stopped_reason, error=error,
		)

	by_id = {str(v.id): v for v in experiment.variants}
	only_variant_for_model = {
		model: str(next(v.id for v in experiment.variants if v.model == model))
		for model in {v.model for v in experiment.variants}
		if sum(1 for v in experiment.variants if v.model == model) == 1
	}
	variants = []
	for row in rows:
		vid = row["variant_id"] or only_variant_for_model.get(row["model"])  # rows from before variants were tracked by id
		current = by_id.get(vid) if vid else None
		scores = [
			ScoreAggregate(name=s["name"], avg=s["avg"], count=s["count"])
			for s in variant_scores.get(vid, [])
		]
		variants.append(
			VariantMetrics(
				variant_id=UUID(vid) if vid else None,
				model=row["model"],
				traffic_weight=current.traffic_weight if current else None,
				request_count=row["request_count"],
				avg_latency_ms=row["avg_latency_ms"],
				total_cost_usd=Decimal(str(row["total_cost_usd"])),
				total_prompt_tokens=row["total_prompt_tokens"],
				total_completion_tokens=row["total_completion_tokens"],
				policy_violations=row["policy_violations"],
				scores=scores,
				probability_best=chances.get(vid) if vid else None,
			)
		)
	return ExperimentResultsResponse(variants=variants, adaptive=adaptive)
