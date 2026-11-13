"""Batch jobs for admins: /api/v1/batch-jobs.

The gateway's /v1/batches belongs to the API key that created a job and shows an application only its own. An admin answers a different
question: what is running in my organization, what has it cost, and can I stop it. This router lists every job of the org (counts, cost and
the cap, never the file contents) and lets an admin cancel an active one. Every cancel is written to the admin audit log.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import CurrentUser, get_db
from app.models.batch import BatchJob
from app.models.user import User
from app.services import batch_service as bs
from app.services.admin_audit_service import get_ip, log_admin_action

router = APIRouter(prefix="/api/v1/batch-jobs", tags=["Batches"])

_ADMIN_ONLY = "Only organization admins can manage batch jobs"
MAX_LIST = 100


class BatchJobResponse(BaseModel):
    id: uuid.UUID
    status: Literal["validating", "in_progress", "completed", "failed", "cancelled", "budget_exceeded"]
    created_by: str | None
    total: int
    completed: int
    failed: int
    cost_usd: float
    max_cost_usd: float
    error: str | None
    created_at: datetime
    finished_at: datetime | None


def _require_admin(user) -> None:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=_ADMIN_ONLY)


def _response(job: BatchJob, email: str | None) -> BatchJobResponse:
    return BatchJobResponse(
        id=job.id, status=job.status, created_by=email, total=job.total, completed=job.completed, failed=job.failed,
        cost_usd=float(job.cost_usd), max_cost_usd=float(job.max_cost_usd), error=job.error, created_at=job.created_at, finished_at=job.finished_at,
    )


@router.get("", response_model=list[BatchJobResponse])
async def list_batch_jobs(
    current_user: CurrentUser, limit: int = Query(default=50, ge=1, le=MAX_LIST), db: AsyncSession = Depends(get_db)
) -> list[BatchJobResponse]:
    _require_admin(current_user)
    rows = await db.execute(
        select(BatchJob, User.email)
        .join(User, User.id == BatchJob.user_id)
        .where(BatchJob.org_id == current_user.org_id)
        .order_by(BatchJob.created_at.desc(), BatchJob.id)
        .limit(limit)
    )
    return [_response(job, email) for job, email in rows]


@router.post("/{job_id}/cancel", response_model=BatchJobResponse)
async def cancel_batch_job(job_id: uuid.UUID, request: Request, current_user: CurrentUser, db: AsyncSession = Depends(get_db)) -> BatchJobResponse:
    _require_admin(current_user)
    row = (
        await db.execute(
            select(BatchJob, User.email)
            .join(User, User.id == BatchJob.user_id)
            .where(BatchJob.id == job_id, BatchJob.org_id == current_user.org_id)
            .with_for_update(of=BatchJob)
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch job not found")
    job, email = row
    if job.status not in bs.ACTIVE:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"A batch that is {job.status} cannot be cancelled.")
    job.status, job.finished_at = "cancelled", datetime.now(UTC).replace(tzinfo=None)
    await log_admin_action(
        db, org_id=current_user.org_id, actor_id=current_user.id, actor_email=current_user.email, action="batch_job.cancelled",
        resource_type="batch_job", resource_id=str(job.id), after={"status": "cancelled", "completed": job.completed, "total": job.total},
        ip_address=get_ip(request),
    )
    await db.commit()
    await db.refresh(job)
    return _response(job, email)
