"""OpenAI-style files and batches: /v1/files and /v1/batches (Phase 5, slice 5.6). Authenticated with an API key.

A file or batch belongs to the user who owns the key; another user in the org cannot see it. See ``services/batch_service.py`` for what
runs and the rules it keeps.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import UploadFile

from app.config import settings
from app.database import set_session_org_id
from app.dependencies import ProxyAuth, get_db, get_redis
from app.models.batch import BatchFile, BatchJob
from app.services import batch_service as bs

router = APIRouter(tags=["Batches"])
LLM_PERMISSION = "proxy:llm"
_OVERHEAD = 64 * 1024


def _error(status_code: int, error: str, detail: str) -> JSONResponse:
	return JSONResponse(status_code=status_code, content={"error": error, "detail": detail}, headers={"X-OpenProxyAI-Gateway-Error": "true"})


def _ts(value: datetime | None) -> int | None:
	return int(value.replace(tzinfo=UTC).timestamp()) if value else None


def _file(row: BatchFile) -> dict:
	return {"id": str(row.id), "object": "file", "bytes": row.size_bytes, "created_at": _ts(row.created_at), "expires_at": _ts(row.expires_at), "filename": row.filename, "purpose": row.purpose if row.purpose == "batch" else "batch_output", "lines": row.line_count}


def _job(row: BatchJob) -> dict:
	return {
		"id": str(row.id), "object": "batch", "endpoint": row.endpoint, "input_file_id": str(row.input_file_id) if row.input_file_id else None,
		"output_file_id": str(row.output_file_id) if row.output_file_id else None, "status": row.status, "completion_window": "24h",
		"created_at": _ts(row.created_at), "in_progress_at": _ts(row.started_at), "completed_at": _ts(row.finished_at) if row.status == "completed" else None,
		"request_counts": {"total": row.total, "completed": row.completed, "failed": row.failed},
		"cost_usd": str(row.cost_usd), "max_cost_usd": str(row.max_cost_usd), "error": row.error, "metadata": row.extra,
	}


async def _guard(auth, db: AsyncSession):
	user, api_key = auth
	if LLM_PERMISSION not in (api_key.permissions or []):
		return None, _error(403, "missing_permission", f"This API key lacks the {LLM_PERMISSION} permission.")
	await set_session_org_id(db, user.org_id)
	return user, None


async def _owned_file(db: AsyncSession, user, file_id: str) -> BatchFile | None:
	try:
		fid = uuid.UUID(file_id)
	except ValueError:
		return None
	return await db.scalar(select(BatchFile).where(BatchFile.id == fid, BatchFile.org_id == user.org_id, BatchFile.user_id == user.id))


@router.post("/v1/files")
async def upload_file(http_request: Request, auth: ProxyAuth, db: AsyncSession = Depends(get_db)):
	user, refusal = await _guard(auth, db)
	if refusal:
		return refusal
	declared = http_request.headers.get("content-length")
	if declared is None or not declared.isdigit():
		return _error(411, "length_required", "A Content-Length header is required for uploads.")
	if int(declared) > bs.MAX_FILE_BYTES + _OVERHEAD:
		return _error(413, "file_too_large", f"Files can be at most {bs.MAX_FILE_BYTES} bytes.")
	form = await http_request.form(max_files=1, max_fields=5)
	upload = form.get("file")
	if not isinstance(upload, UploadFile) or form.get("purpose") != "batch":
		return _error(422, "invalid_request", 'Send multipart form data with purpose "batch" and a file.')
	data = await upload.read(bs.MAX_FILE_BYTES + 1)
	if len(data) > bs.MAX_FILE_BYTES:
		return _error(413, "file_too_large", f"Files can be at most {bs.MAX_FILE_BYTES} bytes.")
	try:
		lines = bs.parse_input(data)
	except bs.BatchFileError as exc:
		return _error(422, "invalid_batch_file", str(exc))
	count = await db.scalar(select(func.count()).select_from(BatchFile).where(BatchFile.org_id == user.org_id, BatchFile.user_id == user.id))
	if (count or 0) >= settings.BATCH_MAX_FILES_PER_USER:
		return _error(409, "too_many_files", f"You can keep at most {settings.BATCH_MAX_FILES_PER_USER} files. Delete some first.")
	row = BatchFile(
		org_id=user.org_id, user_id=user.id, filename=(upload.filename or "batch.jsonl")[:255], purpose="batch", size_bytes=len(data), line_count=len(lines),
		content=data, expires_at=datetime.now(UTC).replace(tzinfo=None) + timedelta(days=settings.BATCH_FILE_RETENTION_DAYS),
	)
	db.add(row)
	await db.commit()
	await db.refresh(row)
	return _file(row)


@router.get("/v1/files/{file_id}")
async def get_file(file_id: str, auth: ProxyAuth, db: AsyncSession = Depends(get_db)):
	user, refusal = await _guard(auth, db)
	if refusal:
		return refusal
	row = await _owned_file(db, user, file_id)
	return _file(row) if row else _error(404, "not_found", "File not found")


@router.get("/v1/files/{file_id}/content")
async def file_content(file_id: str, auth: ProxyAuth, db: AsyncSession = Depends(get_db)):
	user, refusal = await _guard(auth, db)
	if refusal:
		return refusal
	row = await _owned_file(db, user, file_id)
	if row is None:
		return _error(404, "not_found", "File not found")
	return Response(content=row.content, media_type="application/jsonl", headers={"X-OpenProxyAI-Gateway-Error": "false"})


@router.delete("/v1/files/{file_id}")
async def delete_file(file_id: str, auth: ProxyAuth, db: AsyncSession = Depends(get_db)):
	user, refusal = await _guard(auth, db)
	if refusal:
		return refusal
	row = await _owned_file(db, user, file_id)
	if row is None:
		return _error(404, "not_found", "File not found")
	await db.delete(row)
	await db.commit()
	return {"id": file_id, "object": "file", "deleted": True}


class BatchCreate(BaseModel):
	model_config = ConfigDict(extra="forbid")

	input_file_id: str = Field(max_length=64)
	endpoint: str = Field(default=bs.ENDPOINT, max_length=40)
	completion_window: str = Field(default="24h", max_length=10)
	max_cost_usd: float | None = Field(default=None, gt=0, le=1_000_000)
	metadata: dict[str, str] | None = Field(default=None, max_length=16)


@router.post("/v1/batches")
async def create_batch(payload: BatchCreate, auth: ProxyAuth, db: AsyncSession = Depends(get_db), redis: Redis = Depends(get_redis)):
	user, refusal = await _guard(auth, db)
	if refusal:
		return refusal
	if payload.endpoint != bs.ENDPOINT:
		return _error(422, "unsupported_endpoint", f"Only {bs.ENDPOINT} is supported in a batch.")
	cap = Decimal(str(payload.max_cost_usd if payload.max_cost_usd is not None else settings.BATCH_DEFAULT_MAX_COST_USD))
	if cap > Decimal(str(settings.BATCH_MAX_COST_USD)):
		return _error(422, "cost_cap_too_high", f"max_cost_usd can be at most {settings.BATCH_MAX_COST_USD}.")
	source = await _owned_file(db, user, payload.input_file_id)
	if source is None or source.purpose != "batch":
		return _error(404, "not_found", "Input file not found")
	active = int(await db.scalar(select(func.count()).select_from(BatchJob).where(BatchJob.org_id == user.org_id, BatchJob.status.in_(bs.ACTIVE))) or 0)
	if active >= bs.MAX_ACTIVE_JOBS:
		return _error(409, "too_many_batches", f"At most {bs.MAX_ACTIVE_JOBS} batches can be active at once. Wait for one to finish or cancel it.")
	row = BatchJob(
		org_id=user.org_id, user_id=user.id, input_file_id=source.id, endpoint=bs.ENDPOINT, status="validating", total=source.line_count,
		max_cost_usd=cap, extra=payload.metadata or {},
	)
	db.add(row)
	await db.commit()
	await db.refresh(row)
	bs.start(row.id, user.org_id, user.id, redis)
	return _job(row)


async def _owned_job(db: AsyncSession, user, batch_id: str) -> BatchJob | None:
	try:
		bid = uuid.UUID(batch_id)
	except ValueError:
		return None
	return await db.scalar(select(BatchJob).where(BatchJob.id == bid, BatchJob.org_id == user.org_id, BatchJob.user_id == user.id))


@router.get("/v1/batches/{batch_id}")
async def get_batch(batch_id: str, auth: ProxyAuth, db: AsyncSession = Depends(get_db)):
	user, refusal = await _guard(auth, db)
	if refusal:
		return refusal
	row = await _owned_job(db, user, batch_id)
	return _job(row) if row else _error(404, "not_found", "Batch not found")


@router.get("/v1/batches")
async def list_batches(auth: ProxyAuth, limit: int = 20, db: AsyncSession = Depends(get_db)):
	user, refusal = await _guard(auth, db)
	if refusal:
		return refusal
	rows = await db.scalars(
		select(BatchJob).where(BatchJob.org_id == user.org_id, BatchJob.user_id == user.id).order_by(BatchJob.created_at.desc()).limit(max(1, min(limit, 100)))
	)
	return {"object": "list", "data": [_job(r) for r in rows]}


@router.post("/v1/batches/{batch_id}/cancel")
async def cancel_batch(batch_id: str, auth: ProxyAuth, db: AsyncSession = Depends(get_db)):
	user, refusal = await _guard(auth, db)
	if refusal:
		return refusal
	row = await _owned_job(db, user, batch_id)
	if row is None:
		return _error(404, "not_found", "Batch not found")
	if row.status not in bs.ACTIVE:
		return _error(409, "not_cancellable", f"A batch that is {row.status} cannot be cancelled.")
	row.status, row.finished_at = "cancelled", datetime.now(UTC).replace(tzinfo=None)
	await db.commit()
	await db.refresh(row)
	return _job(row)
