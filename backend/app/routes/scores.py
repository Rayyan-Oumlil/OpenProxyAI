"""Reading scores back: /api/v1/scores (Phase 5, slice 5.12).

Writing is ``POST /v1/feedback`` (an application, with an API key) and ``POST /api/v1/requests/{id}/scores`` (a signed-in user).
This is the missing read side, so an org can ask "how is this model doing on thumbs this month" without exporting the database.

- ``GET /api/v1/scores`` lists individual scores, comments and user ids included, so it is admin only.
- ``GET /api/v1/scores/summary`` aggregates (count, mean, min, max) by score name, model or day: no comments, no user ids, so admins
  and developers can read it.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import CurrentUser, get_db
from app.models.request_log import RequestLog
from app.models.request_score import RequestScore

router = APIRouter(prefix="/api/v1/scores", tags=["Scores"])

DEFAULT_WINDOW_DAYS = 30
MAX_WINDOW_DAYS = 365
SUMMARY_ROLES = frozenset({"admin", "developer"})


class ScoreItem(BaseModel):
	id: uuid.UUID
	request_id: uuid.UUID
	score_name: str
	value: float
	source: str
	comment: str | None
	user_id: uuid.UUID | None
	experiment_id: uuid.UUID | None
	variant_id: uuid.UUID | None
	model: str | None
	created_at: datetime


class ScoreGroup(BaseModel):
	group: str
	count: int
	mean: float
	min: float
	max: float


class ScoreSummary(BaseModel):
	group_by: str
	since: datetime
	until: datetime
	groups: list[ScoreGroup]


def _naive_utc(moment: datetime) -> datetime:
	return moment.astimezone(UTC).replace(tzinfo=None) if moment.tzinfo else moment


def _window(since: datetime | None, until: datetime | None) -> tuple[datetime, datetime]:
	end = _naive_utc(until) if until else datetime.now(UTC).replace(tzinfo=None)
	start = _naive_utc(since) if since else end - timedelta(days=DEFAULT_WINDOW_DAYS)
	if start >= end:
		raise HTTPException(status_code=422, detail="since must be before until")
	if end - start > timedelta(days=MAX_WINDOW_DAYS):
		raise HTTPException(status_code=422, detail=f"the window can be at most {MAX_WINDOW_DAYS} days")
	return start, end


def _conditions(user, start, end, score_name, source, experiment_id, model):
	conditions = [RequestScore.org_id == user.org_id, RequestScore.created_at >= start, RequestScore.created_at < end]
	if score_name:
		conditions.append(RequestScore.score_name == score_name)
	if source:
		conditions.append(RequestScore.source == source)
	if experiment_id:
		conditions.append(RequestScore.experiment_id == experiment_id)
	if model:
		conditions.append(RequestLog.model == model)
	return conditions


def _joined_to_logs():
	# Scores carry the gateway's request id; the log row it belongs to gives the model. Both must be the same org's.
	return and_(RequestLog.request_id == RequestScore.request_id, RequestLog.org_id == RequestScore.org_id)


@router.get("", response_model=list[ScoreItem])
async def list_scores(
	current_user: CurrentUser,
	score_name: str | None = Query(None, max_length=100),
	source: Literal["console", "api", "evaluator"] | None = None,
	model: str | None = Query(None, max_length=100),
	request_id: uuid.UUID | None = None,
	experiment_id: uuid.UUID | None = None,
	since: datetime | None = None,
	until: datetime | None = None,
	limit: int = Query(100, ge=1, le=500),
	offset: int = Query(0, ge=0),
	db: AsyncSession = Depends(get_db),
) -> list[ScoreItem]:
	if current_user.role != "admin":
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only organization admins can list individual scores")
	start, end = _window(since, until)
	query = (
		select(RequestScore, RequestLog.model)
		.outerjoin(RequestLog, _joined_to_logs())
		.where(*_conditions(current_user, start, end, score_name, source, experiment_id, model))
		.order_by(RequestScore.created_at.desc(), RequestScore.id)
		.limit(limit)
		.offset(offset)
	)
	if request_id:
		query = query.where(RequestScore.request_id == request_id)
	rows = (await db.execute(query)).all()
	return [
		ScoreItem(
			id=s.id, request_id=s.request_id, score_name=s.score_name, value=float(s.value), source=s.source, comment=s.comment,
			user_id=s.user_id, experiment_id=s.experiment_id, variant_id=s.variant_id, model=model_name, created_at=s.created_at,
		)
		for s, model_name in rows
	]


@router.get("/summary", response_model=ScoreSummary)
async def summarize_scores(
	current_user: CurrentUser,
	group_by: Literal["score_name", "model", "day"] = "score_name",
	score_name: str | None = Query(None, max_length=100),
	source: Literal["console", "api", "evaluator"] | None = None,
	model: str | None = Query(None, max_length=100),
	experiment_id: uuid.UUID | None = None,
	since: datetime | None = None,
	until: datetime | None = None,
	db: AsyncSession = Depends(get_db),
) -> ScoreSummary:
	if current_user.role not in SUMMARY_ROLES:
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Your role cannot read score summaries")
	start, end = _window(since, until)
	key = {"score_name": RequestScore.score_name, "model": func.coalesce(RequestLog.model, "unknown"), "day": func.to_char(RequestScore.created_at, "YYYY-MM-DD")}[group_by]
	query = (
		select(key.label("g"), func.count(), func.avg(RequestScore.value), func.min(RequestScore.value), func.max(RequestScore.value))
		.select_from(RequestScore)
		.outerjoin(RequestLog, _joined_to_logs())
		.where(*_conditions(current_user, start, end, score_name, source, experiment_id, model))
		.group_by(key)
		.order_by(key)
		.limit(1_000)
	)
	rows = (await db.execute(query)).all()
	return ScoreSummary(
		group_by=group_by, since=start, until=end,
		groups=[ScoreGroup(group=str(g), count=int(n), mean=round(float(avg), 4), min=float(lo), max=float(hi)) for g, n, avg, lo, hi in rows],
	)
