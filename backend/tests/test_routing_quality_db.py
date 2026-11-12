"""Loading model feedback for the routing quality signal from the real schema: join, window, filters, RLS, cache."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text, update

from app.database import SystemSessionLocal, org_scoped_session
from app.models.request_log import RequestLog
from app.models.request_score import RequestScore
from app.models.user import User
from app.services.routing_service import QUALITY_WINDOW_DAYS, clear_quality_cache, load_candidates, load_quality
from app.utils.crypto import hash_password
from tests.test_mcp_pinning_db import _dispose_app_engines, pytestmark  # noqa: F401  (shared DB test setup)
from tests.test_routing_loader_db import add_entry, add_key


@pytest.fixture
async def tenants(tenants):
	"""The shared two-org fixture, plus removal of the request logs these tests write (they have no cascade from the org)."""
	yield tenants
	async with SystemSessionLocal() as session:
		await session.execute(text("DELETE FROM request_logs WHERE org_id IN (:a, :b)"), {"a": tenants.a, "b": tenants.b})
		await session.commit()


async def rate(org_id, user_id, model, value, *, score_name="thumbs", age_days=0.0, count=1) -> None:
	"""Log ``count`` requests to ``model`` and give each a score."""
	async with org_scoped_session(org_id) as db:
		for _ in range(count):
			request_id = uuid.uuid4()
			db.add(RequestLog(request_id=request_id, org_id=org_id, user_id=user_id, model=model, provider=model.split("/")[0], status_code=200))
			await db.flush()
			db.add(RequestScore(request_id=request_id, org_id=org_id, score_name=score_name, value=value, source="api"))
		await db.commit()
		if age_days:
			await db.execute(
				update(RequestScore).where(RequestScore.org_id == org_id, RequestScore.score_name == score_name)
				.values(created_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(days=age_days))
			)
			await db.commit()


async def test_feedback_is_summed_per_model(tenants):
	clear_quality_cache()
	user = tenants.user_a.id
	await rate(tenants.a, user, "openai/good", 1.0, count=3)
	await rate(tenants.a, user, "openai/good", 0.0, count=1)
	await rate(tenants.a, user, "openai/other", 0.5, count=2)
	async with org_scoped_session(tenants.a) as db:
		loaded = await load_quality(db, tenants.a)
	assert loaded == {"openai/good": (4, 3.0), "openai/other": (2, 1.0)}


async def test_only_recent_thumbs_in_range_count(tenants):
	clear_quality_cache()
	user = tenants.user_a.id
	await rate(tenants.a, user, "openai/m", 1.0, score_name="thumbs", count=2)
	await rate(tenants.a, user, "openai/m", 1.0, score_name="quality_1_to_5", count=5)  # a different score is not a thumbs rate
	await rate(tenants.a, user, "openai/m", 7.0, score_name="thumbs")  # out of range: left out, not clipped
	async with org_scoped_session(tenants.a) as db:
		assert await load_quality(db, tenants.a) == {"openai/m": (2, 2.0)}

	clear_quality_cache()
	async with org_scoped_session(tenants.a) as db:
		await db.execute(update(RequestScore).where(RequestScore.org_id == tenants.a).values(created_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(days=QUALITY_WINDOW_DAYS + 1)))
		await db.commit()
	async with org_scoped_session(tenants.a) as db:
		assert await load_quality(db, tenants.a) == {}  # everything is now older than the window


async def test_another_orgs_feedback_is_invisible(tenants):
	clear_quality_cache()
	async with org_scoped_session(tenants.b) as db:
		other = User(org_id=tenants.b, email=f"q-{uuid.uuid4().hex[:8]}@test.local", password_hash=hash_password("TestPass1!"), role="admin", is_active=True)
		db.add(other)
		await db.commit()
		other_id = other.id
	await rate(tenants.b, other_id, "openai/theirs", 1.0, count=4)
	await rate(tenants.a, tenants.user_a.id, "openai/ours", 1.0, count=1)
	async with org_scoped_session(tenants.a) as db:
		assert await load_quality(db, tenants.a) == {"openai/ours": (1, 1.0)}


async def test_candidates_carry_feedback_only_when_asked(tenants):
	clear_quality_cache()
	key = await add_key(tenants.a)
	await add_entry(tenants.a, "openai/rated", key, capabilities=["CODE_GENERATION"])
	await add_entry(tenants.a, "openai/unrated", key, capabilities=["CODE_GENERATION"])
	await rate(tenants.a, tenants.user_a.id, "openai/rated", 1.0, count=2)

	async with org_scoped_session(tenants.a) as db:
		plain = {c.model_id: c.quality for c in await load_candidates(db, tenants.a)}
		rated = {c.model_id: c.quality for c in await load_candidates(db, tenants.a, with_quality=True)}
	assert plain == {"openai/rated": None, "openai/unrated": None}  # off: nothing is read, nothing attached
	assert rated == {"openai/rated": (2, 2.0), "openai/unrated": None}


async def test_feedback_is_cached_briefly(tenants):
	clear_quality_cache()
	await rate(tenants.a, tenants.user_a.id, "openai/m", 1.0, count=1)
	async with org_scoped_session(tenants.a) as db:
		first = await load_quality(db, tenants.a)
	await rate(tenants.a, tenants.user_a.id, "openai/m", 1.0, count=1)
	async with org_scoped_session(tenants.a) as db:
		assert await load_quality(db, tenants.a) == first  # served from the cache within the minute
	clear_quality_cache()
	async with org_scoped_session(tenants.a) as db:
		assert (await load_quality(db, tenants.a))["openai/m"] == (2, 2.0)
