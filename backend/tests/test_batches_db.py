"""Files and batches against the real schema with the provider faked: ownership, limits, governance per line, cap, cancel, expiry."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, update

from app.database import SystemSessionLocal, org_scoped_session
from app.dependencies import get_current_user_from_api_key, get_db, get_redis
from app.main import app
from app.models.batch import BatchFile, BatchJob, BatchResult
from app.services import batch_service as bs
from app.services.model_runner import RunOutcome
from tests.conftest import FakeRedis
from tests.db_helpers import make_user, remove_seeded_logs  # noqa: F401  (an autouse fixture)
from tests.test_batch_parse import line
from tests.test_mcp_pinning_db import _dispose_app_engines, pytestmark  # noqa: F401  (shared DB test setup)


class Client:
	"""The app with an API key pinned to an org and user, talking to the real database."""

	def __init__(self, org_id, user, permissions=("proxy:llm",)):
		self.user = SimpleNamespace(id=user.id, org_id=org_id, email=user.email, role="developer", is_active=True)
		self.key = SimpleNamespace(id=uuid.uuid4(), permissions=list(permissions))
		self.org = org_id
		self.redis = FakeRedis()

	async def __aenter__(self):
		from app.database import org_scoped_session as scoped

		async def auth():
			return self.user, self.key

		async def db():
			async with scoped(self.org) as session:
				yield session

		async def redis():
			return self.redis

		app.dependency_overrides[get_current_user_from_api_key] = auth
		app.dependency_overrides[get_db] = db
		app.dependency_overrides[get_redis] = redis
		self.http = AsyncClient(transport=ASGITransport(app=app), base_url="http://gateway.test")
		return self

	async def __aexit__(self, *exc):
		await self.http.aclose()
		app.dependency_overrides.clear()

	async def upload(self, *lines, name="in.jsonl", purpose="batch"):
		data = ("\n".join(lines) + "\n").encode()
		return await self.http.post("/v1/files", data={"purpose": purpose}, files={"file": (name, data, "application/jsonl")})

	async def start(self, file_id, **extra):
		return await self.http.post("/v1/batches", json={"input_file_id": file_id, **extra})


@pytest.fixture
def provider(monkeypatch):
	"""The model runner replaced: records every call and answers from a script by custom id."""
	seen = SimpleNamespace(calls=[], refuse=set(), fail=set(), cost="0.01", delay=0.0, in_flight=0, peak=0)

	async def run_prompt(*, db, redis, org_id, user_id, model, messages, policy_config, source, extra_metadata=None, temperature=None, max_tokens=None):
		seen.in_flight += 1
		seen.peak = max(seen.peak, seen.in_flight)
		try:
			seen.calls.append({"model": model, "messages": messages, "source": source, "meta": extra_metadata, "temperature": temperature, "max_tokens": max_tokens})
			await asyncio.sleep(seen.delay)
			cid = (extra_metadata or {}).get("batch_custom_id")
			if cid in seen.refuse:
				return RunOutcome(error="Blocked by policy.", refused=True)
			if cid in seen.fail:
				return RunOutcome(error="upstream exploded")
			return RunOutcome(content=f"answer to {messages[-1]['content']}", prompt_tokens=5, completion_tokens=3, cost_usd=Decimal(seen.cost))
		finally:
			seen.in_flight -= 1

	monkeypatch.setattr(bs, "run_prompt", run_prompt)
	return seen


async def wait_done(client, batch_id, timeout=15):
	for _ in range(int(timeout / 0.1)):
		job = (await client.http.get(f"/v1/batches/{batch_id}")).json()
		if job["status"] not in ("validating", "in_progress"):
			return job
		await asyncio.sleep(0.1)
	raise AssertionError(f"batch still {job['status']}")


async def output(client, job):
	return [json.loads(l) for l in (await client.http.get(f"/v1/files/{job['output_file_id']}/content")).text.splitlines()]


async def run(client, *lines, **extra):
	file_id = (await client.upload(*lines)).json()["id"]
	started = await client.start(file_id, **extra)
	assert started.status_code == 200, started.text
	return await wait_done(client, started.json()["id"])


async def test_a_batch_runs_every_line_governed_and_returns_an_output_file(tenants, provider):
	async with Client(tenants.a, tenants.user_a) as c:
		job = await run(c, line("a", content="first"), line("b", content="second", temperature=0.2, max_tokens=9))
		assert job["status"] == "completed" and job["request_counts"] == {"total": 2, "completed": 2, "failed": 0} and Decimal(job["cost_usd"]) == Decimal("0.02")
		rows = await output(c, job)
		assert [r["custom_id"] for r in rows] == ["a", "b"] and rows[0]["response"]["status_code"] == 200 and rows[0]["error"] is None
		assert rows[0]["response"]["body"]["choices"][0]["message"]["content"] == "answer to first" and rows[0]["response"]["body"]["usage"]["total_tokens"] == 8
	by_cid = {c["meta"]["batch_custom_id"]: c for c in provider.calls}
	assert all(c["source"] == "batch" and c["meta"]["batch_id"] == job["id"] for c in provider.calls)  # the audit row carries the batch id
	assert (by_cid["b"]["temperature"], by_cid["b"]["max_tokens"]) == (0.2, 9)


async def test_a_refused_or_failed_line_is_its_own_result_and_never_fails_the_job(tenants, provider):
	provider.refuse, provider.fail = {"bad"}, {"boom"}
	async with Client(tenants.a, tenants.user_a) as c:
		job = await run(c, line("ok"), line("bad"), line("boom"))
		assert job["status"] == "completed" and job["request_counts"] == {"total": 3, "completed": 1, "failed": 2}
		rows = {r["custom_id"]: r for r in await output(c, job)}
		assert rows["bad"]["response"] is None and rows["bad"]["error"] == {"status_code": 446, "message": "Blocked by policy."}
		assert rows["boom"]["error"]["status_code"] == 502 and rows["ok"]["error"] is None


async def test_the_spending_cap_stops_new_lines_and_ends_the_job_budget_exceeded(tenants, provider):
	provider.cost = "1.00"
	async with Client(tenants.a, tenants.user_a) as c:
		job = await run(c, *[line(f"l{i}") for i in range(20)], max_cost_usd=2.5)
		assert job["status"] == "budget_exceeded" and 3 <= job["request_counts"]["completed"] < 20
		assert Decimal(job["cost_usd"]) <= Decimal("2.5") + Decimal(bs.CONCURRENCY)  # the overshoot is bounded by the concurrency
		assert len(await output(c, job)) == job["request_counts"]["completed"]  # what finished is still delivered


async def test_concurrency_is_bounded(tenants, provider):
	provider.delay = 0.05
	async with Client(tenants.a, tenants.user_a) as c:
		await run(c, *[line(f"l{i}") for i in range(12)])
	assert 1 < provider.peak <= bs.CONCURRENCY


async def test_cancelling_stops_the_job_and_keeps_what_finished(tenants, provider):
	provider.delay = 0.1
	async with Client(tenants.a, tenants.user_a) as c:
		file_id = (await c.upload(*[line(f"l{i}") for i in range(30)])).json()["id"]
		batch_id = (await c.start(file_id)).json()["id"]
		await asyncio.sleep(0.4)
		cancelled = await c.http.post(f"/v1/batches/{batch_id}/cancel")
		assert cancelled.status_code == 200 and cancelled.json()["status"] == "cancelled"
		await asyncio.sleep(1.0)
		job = (await c.http.get(f"/v1/batches/{batch_id}")).json()
		assert job["status"] == "cancelled" and job["output_file_id"] and 0 < job["request_counts"]["completed"] < 30
		assert len(await output(c, job)) == job["request_counts"]["completed"]
		assert (await c.http.post(f"/v1/batches/{batch_id}/cancel")).status_code == 409


async def test_a_finished_job_cannot_be_cancelled(tenants, provider):
	async with Client(tenants.a, tenants.user_a) as c:
		job = await run(c, line("a"))
		assert (await c.http.post(f"/v1/batches/{job['id']}/cancel")).json()["error"] == "not_cancellable"


# -- upload rules ---------------------------------------------------------------------------------------


async def test_an_invalid_file_is_refused_whole_with_the_line_named_and_nothing_is_stored(tenants, provider):
	async with Client(tenants.a, tenants.user_a) as c:
		response = await c.upload(line("a"), "{broken")
		assert response.status_code == 422 and response.json()["error"] == "invalid_batch_file" and "line 2" in response.json()["detail"]
	async with org_scoped_session(tenants.a) as db:
		assert (await db.scalar(select(func.count()).select_from(BatchFile))) == 0


async def test_upload_needs_a_length_the_right_purpose_and_the_permission(tenants, provider):
	async with Client(tenants.a, tenants.user_a) as c:
		assert (await c.upload(line("a"), purpose="fine-tune")).status_code == 422
		async def body():
		    yield b"--x--"

		chunked = await c.http.post("/v1/files", headers={"Content-Type": "multipart/form-data; boundary=x"}, content=body())
		assert chunked.status_code == 411
	async with Client(tenants.a, tenants.user_a, permissions=("proxy:mcp",)) as c:
		assert (await c.upload(line("a"))).status_code == 403
		assert (await c.http.get("/v1/batches")).status_code == 403


async def test_an_oversized_upload_is_refused_on_its_declared_length(tenants, provider, monkeypatch):
	monkeypatch.setattr(bs, "MAX_FILE_BYTES", 100)
	import app.routes.batches as routes

	monkeypatch.setattr(routes, "_OVERHEAD", 10)
	async with Client(tenants.a, tenants.user_a) as c:
		assert (await c.upload(line("a", content="x" * 500))).status_code == 413


async def test_a_user_keeps_a_limited_number_of_files(tenants, provider, monkeypatch):
	from app.config import settings

	monkeypatch.setattr(settings, "BATCH_MAX_FILES_PER_USER", 2)
	async with Client(tenants.a, tenants.user_a) as c:
		await c.upload(line("a"))
		await c.upload(line("a"))
		assert (await c.upload(line("a"))).json()["error"] == "too_many_files"


# -- ownership and isolation ---------------------------------------------------------------------------


async def test_another_user_in_the_same_org_and_another_org_cannot_see_files_or_batches(tenants, provider):
	teammate, outsider = await make_user(tenants.a), await make_user(tenants.b)
	async with Client(tenants.a, tenants.user_a) as owner:
		file_id = (await owner.upload(line("a"))).json()["id"]
		batch_id = (await owner.start(file_id)).json()["id"]
		await wait_done(owner, batch_id)
	for org, user in ((tenants.a, teammate), (tenants.b, outsider)):
		async with Client(org, user) as other:
			assert (await other.http.get(f"/v1/files/{file_id}")).status_code == 404
			assert (await other.http.get(f"/v1/files/{file_id}/content")).status_code == 404
			assert (await other.http.delete(f"/v1/files/{file_id}")).status_code == 404
			assert (await other.http.get(f"/v1/batches/{batch_id}")).status_code == 404
			assert (await other.http.post(f"/v1/batches/{batch_id}/cancel")).status_code == 404
			assert (await other.start(file_id)).status_code == 404
			assert (await other.http.get("/v1/batches")).json()["data"] == []


async def test_a_batch_needs_a_batch_input_file_not_an_output_file(tenants, provider):
	async with Client(tenants.a, tenants.user_a) as c:
		job = await run(c, line("a"))
		assert (await c.start(job["output_file_id"])).status_code == 404


async def test_the_cap_has_a_ceiling_and_the_endpoint_must_be_chat(tenants, provider):
	async with Client(tenants.a, tenants.user_a) as c:
		file_id = (await c.upload(line("a"))).json()["id"]
		assert (await c.start(file_id, max_cost_usd=10_000)).json()["error"] == "cost_cap_too_high"
		assert (await c.start(file_id, endpoint="/v1/embeddings")).json()["error"] == "unsupported_endpoint"
		assert (await c.start(file_id, max_cost_usd=-1)).status_code == 422
		assert (await c.start("not-a-uuid")).status_code == 404


async def test_only_a_limited_number_of_batches_run_at_once(tenants, provider):
	provider.delay = 0.3
	async with Client(tenants.a, tenants.user_a) as c:
		file_id = (await c.upload(*[line(f"l{i}") for i in range(10)])).json()["id"]
		first, second = await c.start(file_id), await c.start(file_id)
		third = await c.start(file_id)
		assert first.status_code == second.status_code == 200 and third.status_code == 409 and third.json()["error"] == "too_many_batches"
		for response in (first, second):
			await wait_done(c, response.json()["id"], timeout=30)


# -- the janitor ----------------------------------------------------------------------------------------


async def test_expired_files_are_deleted_and_stalled_jobs_are_ended(tenants, provider):
	async with Client(tenants.a, tenants.user_a) as c:
		job = await run(c, line("a"))
		old_input = (await c.upload(line("z"))).json()["id"]
	async with SystemSessionLocal() as session:
		await session.execute(update(BatchFile).where(BatchFile.id == uuid.UUID(old_input)).values(expires_at=bs._now() - timedelta(days=1)))
		stuck = BatchJob(org_id=tenants.a, user_id=tenants.user_a.id, endpoint=bs.ENDPOINT, status="in_progress", total=1, max_cost_usd=1, created_at=bs._now() - timedelta(days=2))
		session.add(stuck)
		await session.commit()
		stuck_id = stuck.id
	ended, deleted = await bs.maintain()
	assert ended >= 1 and deleted >= 1
	async with org_scoped_session(tenants.a) as db:
		assert await db.get(BatchFile, uuid.UUID(old_input)) is None
		assert (await db.get(BatchJob, stuck_id)).status == "failed"
		assert await db.get(BatchJob, uuid.UUID(job["id"])) is not None  # a finished job and its unexpired output are kept


async def test_line_results_are_cleared_once_the_output_file_is_assembled(tenants, provider):
	async with Client(tenants.a, tenants.user_a) as c:
		await run(c, line("a"), line("b"))
	async with org_scoped_session(tenants.a) as db:
		assert (await db.scalar(select(func.count()).select_from(BatchResult))) == 0


async def test_deleting_a_file_removes_its_content(tenants, provider):
	async with Client(tenants.a, tenants.user_a) as c:
		file_id = (await c.upload(line("a"))).json()["id"]
		assert (await c.http.delete(f"/v1/files/{file_id}")).json()["deleted"] is True
		assert (await c.http.get(f"/v1/files/{file_id}")).status_code == 404
