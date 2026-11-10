"""Shared helpers for the real-database API tests (datasets, evaluators, eval runs)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.database import AsyncSessionLocal, SystemSessionLocal, org_scoped_session
from app.dependencies import get_current_user_from_jwt, get_db, get_redis
from app.main import app
from app.models.request_log import RequestLog
from app.models.request_payload import RequestPayload
from app.models.request_score import RequestScore
from app.models.user import User
from app.utils.crypto import hash_password
from tests.conftest import FakeRedis


class Api:
	"""The app with the caller pinned to an org, user and role, talking to the real database and a fake Redis."""

	def __init__(self, org_id, user, role="admin"):
		self.org = org_id
		self.user = SimpleNamespace(id=user.id, org_id=org_id, email=user.email, role=role, is_active=True)
		self.redis = FakeRedis()

	async def __aenter__(self):
		async def fake_user():
			return self.user

		async def scoped_db():
			async with org_scoped_session(self.org) as session:
				yield session

		async def fake_redis():
			return self.redis

		app.dependency_overrides[get_current_user_from_jwt] = fake_user
		app.dependency_overrides[get_db] = scoped_db
		app.dependency_overrides[get_redis] = fake_redis
		self.http = AsyncClient(transport=ASGITransport(app=app), base_url="http://gateway.test")
		return self

	async def __aexit__(self, *exc):
		await self.http.aclose()
		app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
async def remove_seeded_logs(tenants):
	"""request_logs.org_id does not cascade, so the shared tenants fixture cannot delete an org that has log rows.

	Depending on ``tenants`` makes this tear down first. It is autouse, so a test module that imports it (a bare import
	is enough) gets the cleanup for every test.
	"""
	yield
	async with SystemSessionLocal() as session:
		await session.execute(text("DELETE FROM request_logs WHERE org_id IN (:a, :b)"), {"a": tenants.a, "b": tenants.b})
		await session.commit()


async def make_user(org_id) -> SimpleNamespace:
	async with AsyncSessionLocal() as session:
		user = User(org_id=org_id, email=f"t-{uuid.uuid4().hex[:8]}@test.local", password_hash=hash_password("TestPass1!"), role="admin", is_active=True)
		session.add(user)
		await session.commit()
		return SimpleNamespace(id=user.id, email=user.email)


async def seed(org_id, user_id, *, model="openai/gpt-4o-mini", redacted=False, content="Summarise Q3.", output="Revenue grew.",
               age_days=0, score=None, request_id=None) -> uuid.UUID:
	"""One captured request: its log row, its payload and optionally a score."""
	request_id = request_id or uuid.uuid4()
	created = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=age_days)
	async with org_scoped_session(org_id) as db:
		db.add(RequestLog(request_id=request_id, org_id=org_id, user_id=user_id, model=model, provider="openai", status_code=200))
		db.add(RequestPayload(
			request_id=request_id, org_id=org_id, messages=[{"role": "user", "content": content}], output=output,
			redacted=redacted, expires_at=datetime.now(UTC) + timedelta(days=7), created_at=created,
		))
		if score:
			db.add(RequestScore(request_id=request_id, org_id=org_id, score_name=score[0], value=score[1]))
		await db.commit()
	return request_id
