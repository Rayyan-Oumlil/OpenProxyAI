"""Batches (Phase 5, slice 5.6): validate an uploaded JSONL file, then run each line through the governed model runner.

Why the gateway runs the lines itself instead of forwarding a provider batch: a provider batch is a black box that the gateway cannot
police. Running each line through ``model_runner`` means every line gets the org's policy, data classification, routing, metering and
audit row exactly like a live request, on any provider. The price is that the gateway does the waiting.

Rules:
- A file is validated whole before anything runs: every line must be a complete, supported request, and the first bad line is named.
- **A spending cap per job** (``max_cost_usd``): once reached no new line starts and the job ends ``budget_exceeded``; lines already
  in flight finish, so the overshoot is bounded by the concurrency. This is the reservation: a job can never spend more than it declared.
- Bounded size, bounded lines, bounded concurrency, a limit on active jobs per org, cancellation, and a janitor for stalled jobs.
- Content (input and output files) is held only as long as ``BATCH_FILE_RETENTION_DAYS``; a janitor deletes it.
- A line that fails or is refused is a *result* with its status code, never a failure of the job.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, Final

from sqlalchemy import delete, select, update

from app.config import settings
from app.database import AsyncSessionLocal, org_scoped_session, set_session_org_id
from app.models.batch import BatchFile, BatchJob, BatchResult
from app.models.organization import Organization
from app.services.model_runner import run_prompt
from app.services.policy_service import policy_store

logger = logging.getLogger(__name__)

CONCURRENCY: Final = 4
MAX_FILE_BYTES: Final = 16 * 1024 * 1024
MAX_LINES: Final = 5_000
MAX_LINE_BYTES: Final = 256 * 1024
MAX_ACTIVE_JOBS: Final = 2
STALE_AFTER: Final = timedelta(hours=6)
ENDPOINT: Final = "/v1/chat/completions"
ALLOWED_BODY_KEYS: Final = frozenset({"model", "messages", "temperature", "max_tokens"})
ACTIVE: Final = ("validating", "in_progress")

_TASKS: set[asyncio.Task] = set()


class BatchFileError(ValueError):
	"""The upload is not a valid batch input. The message names the line and is safe to show."""


@dataclass(frozen=True)
class Line:
	idx: int
	custom_id: str
	model: str
	messages: list[dict[str, Any]]
	temperature: float | None
	max_tokens: int | None


def _now() -> datetime:
	return datetime.now(UTC).replace(tzinfo=None)


def parse_input(data: bytes) -> list[Line]:
	"""Every line of a batch input file, or ``BatchFileError`` naming the first thing wrong. Nothing is accepted in part."""
	if not data.strip():
		raise BatchFileError("the file is empty")
	if len(data) > MAX_FILE_BYTES:
		raise BatchFileError(f"the file is larger than {MAX_FILE_BYTES} bytes")
	try:
		text = data.decode("utf-8")
	except UnicodeDecodeError:
		raise BatchFileError("the file is not valid UTF-8") from None
	lines: list[Line] = []
	seen: set[str] = set()
	for number, raw in enumerate(text.splitlines(), start=1):
		if not raw.strip():
			continue
		if len(lines) >= MAX_LINES:
			raise BatchFileError(f"a batch can have at most {MAX_LINES} requests")
		if len(raw.encode("utf-8")) > MAX_LINE_BYTES:
			raise BatchFileError(f"line {number} is longer than {MAX_LINE_BYTES} bytes")
		try:
			item = json.loads(raw)
		except ValueError:
			raise BatchFileError(f"line {number} is not valid JSON") from None
		if not isinstance(item, dict) or set(item) - {"custom_id", "method", "url", "body"}:
			raise BatchFileError(f"line {number} must be an object with custom_id, method, url and body only")
		custom_id = item.get("custom_id")
		if not isinstance(custom_id, str) or not 1 <= len(custom_id) <= 64:
			raise BatchFileError(f"line {number}: custom_id must be a string of 1 to 64 characters")
		if custom_id in seen:
			raise BatchFileError(f"line {number}: custom_id '{custom_id}' is used twice")
		seen.add(custom_id)
		if item.get("method") != "POST" or item.get("url") != ENDPOINT:
			raise BatchFileError(f'line {number}: only "method": "POST" with "url": "{ENDPOINT}" is supported')
		body = item.get("body")
		if not isinstance(body, dict) or set(body) - ALLOWED_BODY_KEYS:
			extra = sorted(set(body) - ALLOWED_BODY_KEYS) if isinstance(body, dict) else []
			raise BatchFileError(f"line {number}: body may only hold {', '.join(sorted(ALLOWED_BODY_KEYS))}" + (f" (not {', '.join(extra)})" if extra else ""))
		model, messages = body.get("model"), body.get("messages")
		if not isinstance(model, str) or "/" not in model or len(model) > 100:
			raise BatchFileError(f"line {number}: model must be provider/name")
		if not isinstance(messages, list) or not 1 <= len(messages) <= 200 or not all(
			isinstance(m, dict) and m.get("role") in ("system", "user", "assistant") and isinstance(m.get("content"), str) for m in messages
		):
			raise BatchFileError(f"line {number}: messages must be 1 to 200 items with a role and text content")
		temperature, max_tokens = body.get("temperature"), body.get("max_tokens")
		if temperature is not None and (isinstance(temperature, bool) or not isinstance(temperature, (int, float)) or not 0 <= temperature <= 2):
			raise BatchFileError(f"line {number}: temperature must be a number from 0 to 2")
		if max_tokens is not None and (isinstance(max_tokens, bool) or not isinstance(max_tokens, int) or not 1 <= max_tokens <= 32_000):
			raise BatchFileError(f"line {number}: max_tokens must be an integer from 1 to 32000")
		lines.append(Line(len(lines), custom_id, model, [{"role": m["role"], "content": m["content"]} for m in messages], temperature, max_tokens))
	if not lines:
		raise BatchFileError("the file has no requests")
	return lines


def output_line(job_id: uuid.UUID, row: BatchResult) -> str:
	ok = row.error is None
	return json.dumps({
		"id": f"batch_req_{job_id.hex[:12]}_{row.idx}", "custom_id": row.custom_id,
		"response": {"status_code": row.status_code, "body": row.body} if ok else None,
		"error": None if ok else {"status_code": row.status_code, "message": row.error},
	}, ensure_ascii=False)


def start(job_id: uuid.UUID, org_id: uuid.UUID, user_id: uuid.UUID, redis: Any) -> None:
	task = asyncio.create_task(execute_job(job_id, org_id, user_id, redis))
	_TASKS.add(task)
	task.add_done_callback(_TASKS.discard)


async def _finish(org_id: uuid.UUID, job_id: uuid.UUID, status: str, error: str | None = None) -> None:
	"""End a job unless it already ended, and assemble its output file from the lines that finished."""
	async with org_scoped_session(org_id) as db:
		job = await db.scalar(select(BatchJob).where(BatchJob.id == job_id))
		# A cancel that arrived first stays a cancel, but the lines that did finish still become the output file.
		if job is None or job.output_file_id is not None or job.status not in (*ACTIVE, "cancelled"):
			return
		status = job.status if job.status == "cancelled" else status
		rows = list(await db.scalars(select(BatchResult).where(BatchResult.job_id == job_id).order_by(BatchResult.idx)))
		content = ("\n".join(output_line(job_id, r) for r in rows) + ("\n" if rows else "")).encode("utf-8")
		output = BatchFile(
			org_id=org_id, user_id=job.user_id, filename=f"batch_{job_id.hex[:8]}_output.jsonl", purpose="output", size_bytes=len(content),
			line_count=len(rows), content=content, expires_at=_now() + timedelta(days=settings.BATCH_FILE_RETENTION_DAYS),
		)
		db.add(output)
		await db.flush()
		job.status, job.error, job.output_file_id = status, error, output.id
		job.finished_at = job.finished_at or _now()
		await db.execute(delete(BatchResult).where(BatchResult.job_id == job_id))
		await db.commit()


async def _run_line(line: Line, job_id: uuid.UUID, org_id: uuid.UUID, user_id: uuid.UUID, redis: Any, policy_config: Any, state: dict[str, Any]) -> None:
	"""One line through the model runner and its recorded result. Never raises."""
	async with org_scoped_session(org_id) as db:
		status = await db.scalar(select(BatchJob.status).where(BatchJob.id == job_id))
		if state["stop"] or status != "in_progress":
			return
		outcome = await run_prompt(
			db=db, redis=redis, org_id=org_id, user_id=user_id, model=line.model, messages=line.messages, policy_config=policy_config,
			source="batch", extra_metadata={"batch_id": str(job_id), "batch_custom_id": line.custom_id},
			temperature=line.temperature, max_tokens=line.max_tokens,
		)
		cost = Decimal(outcome.cost_usd)
		if outcome.error is None:
			code, body, error = 200, {
				"model": line.model, "choices": [{"index": 0, "message": {"role": "assistant", "content": outcome.content}, "finish_reason": "stop"}],
				"usage": {"prompt_tokens": outcome.prompt_tokens, "completion_tokens": outcome.completion_tokens, "total_tokens": outcome.prompt_tokens + outcome.completion_tokens},
			}, None
		else:
			code, body, error = (446 if outcome.refused else 502), None, outcome.error
		db.add(BatchResult(org_id=org_id, job_id=job_id, idx=line.idx, custom_id=line.custom_id, status_code=code, body=body, error=error))
		totals = (await db.execute(
			update(BatchJob).where(BatchJob.id == job_id).values(
				completed=BatchJob.completed + (1 if error is None else 0), failed=BatchJob.failed + (1 if error else 0), cost_usd=BatchJob.cost_usd + cost,
			).returning(BatchJob.cost_usd, BatchJob.max_cost_usd)
		)).one()
		await db.commit()
		if totals.cost_usd >= totals.max_cost_usd:
			state["stop"] = "budget_exceeded"


async def execute_job(job_id: uuid.UUID, org_id: uuid.UUID, user_id: uuid.UUID, redis: Any) -> None:
	"""Run one job to its end state. Never raises: an unexpected error ends the job as failed with the reason."""
	try:
		async with org_scoped_session(org_id) as db:
			job = await db.get(BatchJob, job_id)
			if job is None or job.status != "validating":
				return
			source = await db.get(BatchFile, job.input_file_id) if job.input_file_id else None
			if source is None:
				await db.rollback()
				await _finish(org_id, job_id, "failed", "the input file is gone")
				return
			lines = parse_input(source.content)  # validated at upload; checked again because the content is what is about to be sent
			job.status, job.started_at = "in_progress", _now()
			await db.commit()
			policy_config = await policy_store.load(org_id, db, redis)
		state: dict[str, Any] = {"stop": None}
		gate = asyncio.Semaphore(CONCURRENCY)

		async def one(line: Line) -> None:
			async with gate:
				await _run_line(line, job_id, org_id, user_id, redis, policy_config, state)

		await asyncio.gather(*(one(line) for line in lines))
		await _finish(org_id, job_id, state["stop"] or "completed")
	except Exception as exc:
		logger.exception("batch %s failed", job_id)
		try:
			await _finish(org_id, job_id, "failed", str(exc)[:500])
		except Exception:
			logger.exception("could not mark batch %s failed", job_id)


async def maintain() -> tuple[int, int]:
	"""The janitor: end jobs stuck in progress (the process that held them died) and delete files past their retention.

	One organization at a time, because row-level security is forced. Returns (jobs ended, files deleted).
	"""
	ended = deleted = 0
	try:
		async with AsyncSessionLocal() as session:
			for org_id in list(await session.scalars(select(Organization.id))):
				await set_session_org_id(session, org_id)
				result = await session.execute(
					update(BatchJob).where(BatchJob.org_id == org_id, BatchJob.status.in_(ACTIVE), BatchJob.created_at < _now() - STALE_AFTER)
					.values(status="failed", error="interrupted: the service stopped before this batch finished", finished_at=_now())
				)
				ended += result.rowcount or 0
				gone = await session.execute(delete(BatchFile).where(BatchFile.org_id == org_id, BatchFile.expires_at < _now()))
				deleted += gone.rowcount or 0
			await session.commit()
	except Exception:
		logger.exception("batch maintenance failed")
	return ended, deleted
