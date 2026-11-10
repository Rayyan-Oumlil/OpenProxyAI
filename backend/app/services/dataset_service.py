"""Building datasets from captured traffic (Phase 3, slice 3).

An import copies redacted prompts and answers out of ``request_payloads`` (slice 2). Three rules keep it safe:

- A row the PII detector touched when it was captured is never imported, and every row is scanned again on the way in,
  so a detector that has improved since catches what the old one missed.
- Importing the same requests twice adds nothing (unique on dataset and request id).
- A dataset holds at most ``MAX_ITEMS_PER_DATASET`` items.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

from sqlalchemy import Select, and_, exists, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dataset import DatasetItem
from app.models.request_log import RequestLog
from app.models.request_payload import RequestPayload
from app.models.request_score import RequestScore
from app.schemas.dataset import MAX_ITEMS_PER_DATASET, ImportRequest, ImportResponse
from app.services import pii_detection


def pii_kinds(*texts: str | None) -> list[str]:
	"""Each kind of PII found across the given texts, once."""
	return pii_detection.entities("\n".join(t for t in texts if t))


def _naive_utc(moment: datetime) -> datetime:
	"""The ``created_at`` columns are timestamps without a zone, holding UTC."""
	return moment.astimezone(UTC).replace(tzinfo=None) if moment.tzinfo else moment


def _matches(org_id: uuid.UUID, request: ImportRequest) -> Select:
	query = select(
		RequestPayload.request_id, RequestPayload.messages, RequestPayload.output, RequestPayload.redacted
	).where(RequestPayload.org_id == org_id)
	if request.model is not None:
		query = query.join(
			RequestLog, and_(RequestLog.request_id == RequestPayload.request_id, RequestLog.org_id == RequestPayload.org_id)
		).where(RequestLog.model == request.model)
	if request.since is not None:
		query = query.where(RequestPayload.created_at >= _naive_utc(request.since))
	if request.until is not None:
		query = query.where(RequestPayload.created_at <= _naive_utc(request.until))
	if request.score_name is not None:
		score = and_(
			RequestScore.org_id == org_id,
			RequestScore.request_id == RequestPayload.request_id,
			RequestScore.score_name == request.score_name,
		)
		if request.min_score is not None:
			score = and_(score, RequestScore.value >= request.min_score)
		if request.max_score is not None:
			score = and_(score, RequestScore.value <= request.max_score)
		query = query.where(exists().where(score))
	return query


async def _count(db: AsyncSession, query: Select) -> int:
	return int(await db.scalar(select(func.count()).select_from(query.subquery())) or 0)


async def item_count(db: AsyncSession, dataset_id: uuid.UUID) -> int:
	return int(await db.scalar(select(func.count()).select_from(DatasetItem).where(DatasetItem.dataset_id == dataset_id)) or 0)


async def import_from_payloads(db: AsyncSession, org_id: uuid.UUID, dataset_id: uuid.UUID, request: ImportRequest) -> ImportResponse:
	"""Copy matching captured requests into the dataset. Commits nothing; the caller commits with its audit entry."""
	matches = _matches(org_id, request)
	already_there = exists().where(DatasetItem.dataset_id == dataset_id, DatasetItem.request_id == RequestPayload.request_id)

	skipped_redacted = await _count(db, matches.where(RequestPayload.redacted.is_(True)))
	skipped_duplicate = await _count(db, matches.where(RequestPayload.redacted.is_(False), already_there))
	fresh = matches.where(RequestPayload.redacted.is_(False), ~already_there)

	capacity = MAX_ITEMS_PER_DATASET - await item_count(db, dataset_id)
	wanted = max(0, min(request.limit, capacity))
	stopped_at_capacity = wanted < min(request.limit, await _count(db, fresh))
	if wanted == 0:
		return ImportResponse(imported=0, skipped_redacted=skipped_redacted, skipped_duplicate=skipped_duplicate, stopped_at_capacity=stopped_at_capacity)

	ordering = func.random() if request.order == "random" else RequestPayload.created_at.desc()
	rows = (await db.execute(fresh.order_by(ordering).limit(wanted))).all()

	items = []
	for row in rows:
		if pii_kinds(json.dumps(row.messages), row.output):
			skipped_redacted += 1  # found now, though the detector at capture time did not
			continue
		items.append({"org_id": org_id, "dataset_id": dataset_id, "request_id": row.request_id, "messages": row.messages, "output": row.output})

	imported = 0
	if items:
		result = await db.execute(
			insert(DatasetItem).values(items).on_conflict_do_nothing(index_elements=["dataset_id", "request_id"]).returning(DatasetItem.id)
		)
		imported = len(result.all())
	return ImportResponse(imported=imported, skipped_redacted=skipped_redacted, skipped_duplicate=skipped_duplicate, stopped_at_capacity=stopped_at_capacity)
