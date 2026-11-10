"""Executing an eval run (Phase 3, slice 4): every dataset item through a candidate model, then through an evaluator.

A run is started by the API and executed here in the background. Four rules keep it from becoming a way to burn money or
hang the service:

- **A spending cap.** ``max_cost_usd`` covers candidate and judge calls together. Once it is reached no new item starts and
  the run ends ``budget_exceeded``; the few already in flight finish, so the overshoot is bounded by the concurrency.
- **Bounded concurrency** (``CONCURRENCY`` items at a time) and a bounded item count (checked by the API).
- **Cancellation** is a status change; each item checks it before it starts.
- **Item failures are results, not run failures.** A refused, failed or unscorable item is recorded with its error and left
  out of the average, so one bad item never ends a run or counts as a zero.

Each item uses its own database session: a session cannot be shared between concurrent tasks.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, Final

from sqlalchemy import select, update

from app.database import AsyncSessionLocal, org_scoped_session, set_session_org_id
from app.models.dataset import DatasetItem
from app.models.evaluation import EvalRun, EvalRunItem
from app.models.organization import Organization
from app.services import evaluators
from app.services.model_runner import run_prompt
from app.services.policy_service import policy_store

logger = logging.getLogger(__name__)

CONCURRENCY: Final = 4
STALE_AFTER: Final = timedelta(hours=3)  # longer than the largest allowed run can take

_TASKS: set[asyncio.Task] = set()  # a task nobody holds can be garbage-collected mid-run


@dataclass(frozen=True)
class RunSpec:
	"""What the workers need from the run row, copied out so no worker touches a detached ORM object."""

	id: uuid.UUID
	dataset_id: uuid.UUID | None
	candidate_model: str
	system_prompt: str | None
	evaluator_type: str
	evaluator_config: dict
	total_items: int


def start(run_id: uuid.UUID, org_id: uuid.UUID, user_id: uuid.UUID, redis: Any) -> None:
	"""Run in the background of this process. Returns at once."""
	task = asyncio.create_task(execute_run(run_id, org_id, user_id, redis))
	_TASKS.add(task)
	task.add_done_callback(_TASKS.discard)


def _now() -> datetime:
	return datetime.now(UTC).replace(tzinfo=None)  # the timestamp columns hold naive UTC


async def _finish(org_id: uuid.UUID, run_id: uuid.UUID, status: str, error: str | None = None) -> None:
	"""End a run, unless it already ended (a cancel that arrived first stays a cancel)."""
	async with org_scoped_session(org_id) as db:
		await db.execute(
			update(EvalRun).where(EvalRun.id == run_id, EvalRun.status.in_(("queued", "running")))
			.values(status=status, error=error, finished_at=_now())
		)
		await db.commit()


async def _score_item(
	run: RunSpec, item: DatasetItem, org_id: uuid.UUID, user_id: uuid.UUID, redis: Any, policy_config: Any, state: dict[str, Any],
) -> None:
	"""One item: candidate call, evaluation, and the recorded result. Never raises."""
	async with org_scoped_session(org_id) as db:
		current = await db.scalar(select(EvalRun.status).where(EvalRun.id == run.id))
		if state["stop"] or current != "running":
			return
		messages = ([{"role": "system", "content": run.system_prompt}] if run.system_prompt else []) + list(item.messages)
		outcome = await run_prompt(
			db=db, redis=redis, org_id=org_id, user_id=user_id, model=run.candidate_model, messages=messages,
			policy_config=policy_config, source="eval_run", extra_metadata={"eval_run_id": str(run.id)},
		)
		cost = Decimal(outcome.cost_usd)
		score: float | None = None
		passed: bool | None = None
		reason: str | None = None
		error = outcome.error
		if error is None:
			try:
				verdict = await evaluators.evaluate(
					run.evaluator_type, run.evaluator_config, db=db, redis=redis, org_id=org_id, user_id=user_id,
					policy_config=policy_config, question=list(item.messages), output=outcome.content, expected=item.expected, run_id=str(run.id),
				)
			except Exception as exc:  # evaluators do not raise; if one does, the item fails and the run goes on
				logger.exception("evaluator crashed on run %s", run.id)
				verdict = evaluators.Verdict(error=f"evaluator crashed: {exc}")
			cost += Decimal(verdict.cost_usd)
			error = verdict.error
			if error is None:
				score, passed, reason = verdict.score, verdict.passed, verdict.reason

		db.add(EvalRunItem(
			org_id=org_id, run_id=run.id, dataset_item_id=item.id, output=outcome.content or None, score=score, passed=passed,
			reason=reason, error=error, cost_usd=cost, latency_ms=outcome.latency_ms,
		))
		totals = (await db.execute(
			update(EvalRun).where(EvalRun.id == run.id).values(
				completed_items=EvalRun.completed_items + 1,
				failed_items=EvalRun.failed_items + (1 if error else 0),
				passed_items=EvalRun.passed_items + (1 if passed else 0),
				score_sum=EvalRun.score_sum + Decimal(str(score or 0)),
				cost_usd=EvalRun.cost_usd + cost,
			).returning(EvalRun.cost_usd, EvalRun.max_cost_usd)
		)).one()
		await db.commit()
		if totals.cost_usd >= totals.max_cost_usd:
			state["stop"] = "budget_exceeded"


async def execute_run(run_id: uuid.UUID, org_id: uuid.UUID, user_id: uuid.UUID, redis: Any) -> None:
	"""Execute one run to its end state. Never raises: an unexpected error ends the run as failed with the reason."""
	try:
		async with org_scoped_session(org_id) as db:
			row = await db.get(EvalRun, run_id)
			if row is None or row.status != "queued":
				return
			run = RunSpec(
				id=row.id, dataset_id=row.dataset_id, candidate_model=row.candidate_model, system_prompt=row.system_prompt,
				evaluator_type=row.evaluator_snapshot["type"], evaluator_config=row.evaluator_snapshot["config"], total_items=row.total_items,
			)
			row.status, row.started_at = "running", _now()
			await db.commit()
			policy_config = await policy_store.load(org_id, db, redis)
			items = list(await db.scalars(
				select(DatasetItem).where(DatasetItem.dataset_id == run.dataset_id)
				.order_by(DatasetItem.created_at, DatasetItem.id).limit(run.total_items)
			))
			db.expunge_all()  # the rows are read-only copies from here on

		state: dict[str, Any] = {"stop": None}
		gate = asyncio.Semaphore(CONCURRENCY)

		async def one(item: DatasetItem) -> None:
			async with gate:
				await _score_item(run, item, org_id, user_id, redis, policy_config, state)

		await asyncio.gather(*(one(item) for item in items))
		await _finish(org_id, run_id, state["stop"] or "completed")
	except Exception as exc:
		logger.exception("eval run %s failed", run_id)
		try:
			await _finish(org_id, run_id, "failed", str(exc)[:500])
		except Exception:
			logger.exception("could not mark eval run %s failed", run_id)


async def fail_stale_runs(now: datetime | None = None) -> int:
	"""End runs that are still queued or running long after they could have finished (the process that held them died).

	One organization at a time, because row-level security is forced. Returns how many were ended.
	"""
	cutoff = (now or _now()) - STALE_AFTER
	ended = 0
	try:
		async with AsyncSessionLocal() as session:
			for org_id in list(await session.scalars(select(Organization.id))):
				await set_session_org_id(session, org_id)
				result = await session.execute(
					update(EvalRun).where(EvalRun.org_id == org_id, EvalRun.status.in_(("queued", "running")), EvalRun.created_at < cutoff)
					.values(status="failed", error="interrupted: the service stopped before this run finished", finished_at=_now())
				)
				ended += result.rowcount or 0
			await session.commit()
	except Exception:
		logger.exception("Failed to end stale eval runs")
	return ended
