"""The admin view of batch jobs against the real schema: who may see them, isolation between orgs, and cancelling."""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import select

from app.database import org_scoped_session
from app.models.admin_audit_log import AdminAuditLog
from app.models.batch import BatchJob
from tests.db_helpers import Api, remove_seeded_logs  # noqa: F401  (an autouse fixture)
from tests.test_mcp_pinning_db import _dispose_app_engines, pytestmark  # noqa: F401  (shared DB test setup)

PATH = "/api/v1/batch-jobs"


async def make_job(org_id, user, status="in_progress", **fields):
    async with org_scoped_session(org_id) as db:
        job = BatchJob(
            org_id=org_id, user_id=user.id, endpoint="/v1/chat/completions", status=status, total=fields.pop("total", 10),
            max_cost_usd=Decimal("5"), **fields,
        )
        db.add(job)
        await db.commit()
        return str(job.id)


async def test_an_admin_sees_every_job_of_the_org_newest_first_and_never_another_orgs(tenants):
    first = await make_job(tenants.a, tenants.user_a, status="completed", completed=10, cost_usd=Decimal("0.42"))
    second = await make_job(tenants.a, tenants.user_a, status="failed", failed=3, error="boom")
    await make_job(tenants.b, tenants.user_a)
    async with Api(tenants.a, tenants.user_a) as api:
        response = await api.http.get(PATH)
    assert response.status_code == 200
    jobs = response.json()
    assert [j["id"] for j in jobs] == [second, first]
    done = jobs[1]
    assert done["created_by"] == tenants.user_a.email and done["cost_usd"] == 0.42 and done["max_cost_usd"] == 5.0 and done["completed"] == 10
    assert "content" not in done and "input_file_id" not in done  # counts and cost only, never file contents


async def test_only_an_admin_may_list_or_cancel(tenants):
    job = await make_job(tenants.a, tenants.user_a)
    async with Api(tenants.a, tenants.user_a, role="developer") as api:
        assert (await api.http.get(PATH)).status_code == 403
        assert (await api.http.post(f"{PATH}/{job}/cancel")).status_code == 403
    async with org_scoped_session(tenants.a) as db:
        assert (await db.get(BatchJob, job)).status == "in_progress"


async def test_cancelling_an_active_job_stops_it_and_is_audited(tenants):
    job = await make_job(tenants.a, tenants.user_a, status="validating")
    async with Api(tenants.a, tenants.user_a) as api:
        response = await api.http.post(f"{PATH}/{job}/cancel")
        assert response.status_code == 200 and response.json()["status"] == "cancelled" and response.json()["finished_at"]
        assert (await api.http.post(f"{PATH}/{job}/cancel")).status_code == 409  # already stopped
    async with org_scoped_session(tenants.a) as db:
        actions = (await db.scalars(select(AdminAuditLog.action).where(AdminAuditLog.resource_id == job))).all()
    assert actions == ["batch_job.cancelled"]


async def test_a_finished_job_cannot_be_cancelled(tenants):
    job = await make_job(tenants.a, tenants.user_a, status="completed", completed=10)
    async with Api(tenants.a, tenants.user_a) as api:
        response = await api.http.post(f"{PATH}/{job}/cancel")
    assert response.status_code == 409 and "completed" in response.json()["detail"]


async def test_an_admin_cannot_cancel_another_orgs_job(tenants):
    job = await make_job(tenants.b, tenants.user_a)
    async with Api(tenants.a, tenants.user_a) as api:
        assert (await api.http.post(f"{PATH}/{job}/cancel")).status_code == 404
    async with org_scoped_session(tenants.b) as db:
        assert (await db.get(BatchJob, job)).status == "in_progress"


async def test_the_limit_is_bounded(tenants):
    async with Api(tenants.a, tenants.user_a) as api:
        assert (await api.http.get(PATH, params={"limit": 0})).status_code == 422
        assert (await api.http.get(PATH, params={"limit": 101})).status_code == 422
