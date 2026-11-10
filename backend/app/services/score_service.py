"""Writing request scores: one upsert shared by the console route and the API-key feedback route."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.request_score import RequestScore


@dataclass(frozen=True)
class ScoreWrite:
	name: str
	value: float
	comment: str | None = None


def experiment_link(request_log: Any) -> tuple[uuid.UUID | None, uuid.UUID | None]:
	"""The experiment and variant a logged request ran under, or (None, None). Malformed ids are ignored, not fatal."""
	metadata = getattr(request_log, "request_metadata", None) or {}
	experiment = metadata.get("experiment") or {}
	return _uuid_or_none(experiment.get("experiment_id")), _uuid_or_none(experiment.get("variant_id"))


def _uuid_or_none(value: Any) -> uuid.UUID | None:
	try:
		return uuid.UUID(str(value)) if value else None
	except ValueError:
		return None


async def record_scores(
	db: AsyncSession,
	*,
	org_id: uuid.UUID,
	request_id: uuid.UUID,
	request_log: Any,
	scores: Sequence[ScoreWrite],
	source: str,
	user_id: uuid.UUID | None,
) -> int:
	"""Upsert one row per (org, request, score name): sending the same score again replaces it. Commits."""
	experiment_id, variant_id = experiment_link(request_log)
	for score in scores:
		fields = {
			"experiment_id": experiment_id,
			"variant_id": variant_id,
			"value": score.value,
			"source": source,
			"comment": score.comment,
			"user_id": user_id,
		}
		stmt = insert(RequestScore).values(
			request_id=request_id, org_id=org_id, score_name=score.name, **fields
		).on_conflict_do_update(index_elements=["org_id", "request_id", "score_name"], set_=fields)
		await db.execute(stmt)
	await db.commit()
	return len(scores)
