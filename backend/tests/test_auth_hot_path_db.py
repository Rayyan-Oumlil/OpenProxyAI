"""The API-key hot path against the real schema: "last used" is written at most once a minute, and nothing else is cached (a revoked key stops at once)."""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import select, update

from app.database import SystemSessionLocal, org_scoped_session
from app.models.api_key import ApiKey
from app.models.user import User
from app.services import auth_service as auth
from tests.conftest import FakeRedis
from tests.db_helpers import remove_seeded_logs  # noqa: F401  (an autouse fixture)
from tests.test_mcp_pinning_db import _dispose_app_engines, pytestmark  # noqa: F401  (shared DB test setup)


async def make_key(tenants):
	async with org_scoped_session(tenants.a) as db:
		return await auth.create_api_key(db=db, user_id=tenants.user_a.id, org_id=tenants.a, name="hot", permissions=["proxy:llm"], expires_at=None)


async def validate(tenants, full):
	async with org_scoped_session(tenants.a) as db:
		return await auth.validate_api_key(db, FakeRedis(), full)


async def last_used(tenants, key_id):
	async with org_scoped_session(tenants.a) as db:
		return await db.scalar(select(ApiKey.last_used_at).where(ApiKey.id == key_id))


async def test_last_used_is_written_by_the_first_request_and_not_again_inside_the_window(tenants):
	model, full = await make_key(tenants)
	assert await last_used(tenants, model.id) is None
	await validate(tenants, full)
	first = await last_used(tenants, model.id)
	assert first is not None
	await validate(tenants, full)
	await validate(tenants, full)
	assert await last_used(tenants, model.id) == first  # inside the window: no write


async def test_after_the_window_the_next_request_writes_it_again(tenants):
	model, full = await make_key(tenants)
	await validate(tenants, full)
	async with SystemSessionLocal() as session:
		old = auth._utc_now().replace(tzinfo=None) - timedelta(seconds=61)
		await session.execute(update(ApiKey).where(ApiKey.id == model.id).values(last_used_at=old))
		await session.commit()
	await validate(tenants, full)
	assert await last_used(tenants, model.id) > old + timedelta(seconds=30)


async def test_a_revoked_key_stops_working_at_once_even_inside_the_window(tenants):
	"""Nothing about who may call is cached: the throttle only skips a bookkeeping write."""
	model, full = await make_key(tenants)
	await validate(tenants, full)
	async with SystemSessionLocal() as session:
		await session.execute(update(ApiKey).where(ApiKey.id == model.id).values(is_active=False))
		await session.commit()
	with pytest.raises(HTTPException) as caught:
		await validate(tenants, full)
	assert caught.value.status_code == 401


async def test_a_deactivated_user_stops_working_at_once_inside_the_window(tenants):
	model, full = await make_key(tenants)
	await validate(tenants, full)
	async with SystemSessionLocal() as session:
		await session.execute(update(User).where(User.id == tenants.user_a.id).values(is_active=False))
		await session.commit()
	with pytest.raises(HTTPException):
		await validate(tenants, full)


async def test_an_expired_key_stops_working_at_once_inside_the_window(tenants):
	model, full = await make_key(tenants)
	await validate(tenants, full)
	async with SystemSessionLocal() as session:
		await session.execute(update(ApiKey).where(ApiKey.id == model.id).values(expires_at=auth._utc_now().replace(tzinfo=None) - timedelta(seconds=1)))
		await session.commit()
	with pytest.raises(HTTPException):
		await validate(tenants, full)


async def test_a_wrong_key_is_still_refused(tenants):
	await make_key(tenants)
	with pytest.raises(HTTPException):
		await validate(tenants, "opai_" + uuid.uuid4().hex)
