"""Running adaptive A/B experiments (Phase 3, slice 5): the periodic job that moves traffic and stops a test.

Every few minutes, for each active adaptive experiment: read the feedback scores per variant, ask ``ab_testing.decide``,
and apply the answer. Three guarantees:

- **Nothing moves before there is enough data.** Weights stay as an admin set them until every variant has
  ``min_samples_per_variant`` scores, and a winner is never named before that either.
- **A winner is recorded, not deployed.** Stopping ends the split (requests go back to the target model) and names the
  winner; an admin decides whether to switch. A test never changes which model serves production traffic on its own.
- **A metric that is not a rate is an error, not a guess.** The statistics assume values in 0 to 1. If the metric has any
  outside that, the experiment is left as it is and ``adaptive_error`` says why.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import AsyncSessionLocal, set_session_org_id
from app.models.experiment import Experiment
from app.models.organization import Organization
from app.models.request_score import RequestScore
from app.services.ab_testing import Decision, VariantStats, decide
from app.services.admin_audit_service import log_admin_action

logger = logging.getLogger(__name__)

SYSTEM_ACTOR = "system:adaptive-ab"


class MetricNotARate(Exception):
	"""The experiment's metric has values outside 0 to 1."""


def seed_for(experiment_id: uuid.UUID, observations: int) -> int:
	"""A seed that is stable for the same data, so a decision can be reproduced, and changes as data arrives."""
	return (experiment_id.int % (2**31)) + observations


async def fetch_stats(db: AsyncSession, org_id: uuid.UUID, experiment: Experiment) -> list[VariantStats]:
	"""Per-variant observations of the experiment's metric, one entry for every variant (zeros when it has none yet)."""
	rows = (await db.execute(
		select(
			RequestScore.variant_id,
			func.count().label("n"),
			func.coalesce(func.sum(RequestScore.value), 0).label("total"),
			func.count().filter((RequestScore.value < 0) | (RequestScore.value > 1)).label("bad"),
		)
		.where(RequestScore.org_id == org_id, RequestScore.experiment_id == experiment.id,
		       RequestScore.score_name == experiment.metric, RequestScore.variant_id.is_not(None))
		.group_by(RequestScore.variant_id)
	)).all()
	if any(row.bad for row in rows):
		raise MetricNotARate(f"metric {experiment.metric!r} has values outside 0 to 1; an adaptive test needs a rate, for example thumbs")
	seen = {row.variant_id: (int(row.n), float(row.total)) for row in rows}
	return [VariantStats(str(v.id), *seen.get(v.id, (0, 0.0))) for v in experiment.variants]


def decide_for(experiment: Experiment, stats: list[VariantStats]) -> Decision:
	return decide(
		stats, min_samples=experiment.min_samples_per_variant, delta=float(experiment.delta), floor=experiment.weight_floor,
		seed=seed_for(experiment.id, sum(s.n for s in stats)),
	)


async def _update_one(db: AsyncSession, org_id: uuid.UUID, experiment: Experiment) -> bool:
	"""Apply one round to one experiment. Returns whether anything about it changed."""
	now = datetime.now(UTC).replace(tzinfo=None)
	experiment.adaptive_updated_at = now
	if len(experiment.variants) < 2:
		experiment.adaptive_error = "an adaptive test needs at least two variants"
		return True
	try:
		stats = await fetch_stats(db, org_id, experiment)
	except MetricNotARate as exc:
		experiment.adaptive_error = str(exc)
		return True
	experiment.adaptive_error = None
	decision = decide_for(experiment, stats)

	before = {str(v.id): v.traffic_weight for v in experiment.variants}
	if decision.weights is not None:
		for variant in experiment.variants:
			variant.traffic_weight = decision.weights[str(variant.id)]
	after = {str(v.id): v.traffic_weight for v in experiment.variants}

	if decision.winner is not None:
		experiment.is_active = False
		experiment.winner_variant_id = uuid.UUID(decision.winner)
		experiment.stopped_reason = "winner"
	if decision.winner is not None or before != after:
		await log_admin_action(
			db, org_id=org_id, actor_id=None, actor_email=SYSTEM_ACTOR,
			action="experiment.winner_found" if decision.winner else "experiment.weights_adapted",
			resource_type="experiment", resource_id=str(experiment.id), before={"weights": before},
			after={"weights": after, "winner_variant_id": decision.winner,
			       "probability_best": {k: round(v, 4) for k, v in decision.probability_best.items()}},
		)
	return True


async def update_adaptive_experiments() -> int:
	"""One round over every active adaptive experiment, one organization at a time (row-level security is forced).

	Returns how many experiments were looked at. A failure on one experiment is logged and does not stop the rest.
	"""
	looked_at = 0
	try:
		async with AsyncSessionLocal() as session:
			for org_id in list(await session.scalars(select(Organization.id))):
				await set_session_org_id(session, org_id)
				experiments = list(await session.scalars(
					select(Experiment).where(Experiment.org_id == org_id, Experiment.is_active.is_(True), Experiment.mode == "adaptive")
					.options(selectinload(Experiment.variants))
				))
				for experiment in experiments:
					try:
						await _update_one(session, org_id, experiment)
						await session.commit()
						looked_at += 1
					except Exception:
						await session.rollback()
						logger.exception("adaptive update failed for experiment %s", experiment.id)
	except Exception:
		logger.exception("Failed to update adaptive experiments")
	return looked_at


def describe(experiment: Experiment, stats: list[VariantStats]) -> dict[str, Any]:
	"""The current state of an adaptive test for the results endpoint (decided with the same rules the job uses)."""
	decision = decide_for(experiment, stats)
	return {
		"ready": decision.ready,
		"probability_best": decision.probability_best,
		"samples": {s.variant_id: s.n for s in stats},
	}
