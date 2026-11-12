"""Conversations follow the plan's retention (against the real schema)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update

from app.database import SystemSessionLocal, org_scoped_session
from app.models.conversation import Conversation, ConversationContextPackage, ConversationTurn
from app.models.organization import Organization
from app.services.conversation_retention import purge_expired_conversations, retention_days
from tests.db_helpers import remove_seeded_logs  # noqa: F401  (an autouse fixture)
from tests.test_conversations_db import member
from tests.test_mcp_pinning_db import _dispose_app_engines, pytestmark  # noqa: F401  (shared DB test setup)


async def make(org_id, owner, title, idle_days):
	async with org_scoped_session(org_id) as db:
		row = Conversation(org_id=org_id, owner_id=owner.id, title=title)
		db.add(row)
		await db.flush()
		db.add(ConversationTurn(org_id=org_id, conversation_id=row.id, seq=1, role="user", content="hi", data_class="internal"))
		db.add(ConversationContextPackage(
			org_id=org_id, conversation_id=row.id, model="openai/x", data_class="internal", routing_mode="off", included_turn_ids=[],
			withheld=[], estimated_tokens=1, payload_sha256="0" * 64, outcome="ok",
		))
		await db.commit()
		row_id = row.id
	async with SystemSessionLocal() as session:
		await session.execute(update(Conversation).where(Conversation.id == row_id).values(updated_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(days=idle_days)))
		await session.commit()
	return row_id


async def set_plan(org_id, plan):
	async with SystemSessionLocal() as session:
		await session.execute(update(Organization).where(Organization.id == org_id).values(plan=plan))
		await session.commit()


def test_each_plan_has_its_own_retention_and_an_unknown_plan_gets_the_shortest():
	assert retention_days("community") == 7 and retention_days("ENTERPRISE") == 365 and retention_days("nonsense") == 7 and retention_days(None) == 7


async def test_an_idle_conversation_is_deleted_with_its_turns_and_context_records_and_an_active_one_is_kept(tenants):
	owner = await member(tenants.a)
	await set_plan(tenants.a, "community")
	old, fresh = await make(tenants.a, owner, "old", 10), await make(tenants.a, owner, "fresh", 1)
	assert await purge_expired_conversations() >= 1
	async with org_scoped_session(tenants.a) as db:
		assert await db.get(Conversation, old) is None and await db.get(Conversation, fresh) is not None
		assert (await db.scalar(select(func.count()).select_from(ConversationTurn).where(ConversationTurn.conversation_id == old))) == 0
		assert (await db.scalar(select(func.count()).select_from(ConversationContextPackage).where(ConversationContextPackage.conversation_id == old))) == 0
		assert (await db.scalar(select(func.count()).select_from(ConversationTurn).where(ConversationTurn.conversation_id == fresh))) == 1


async def test_the_orgs_plan_sets_how_long_a_conversation_may_idle_and_other_orgs_are_untouched(tenants):
	owner_a, owner_b = await member(tenants.a), await member(tenants.b)
	await set_plan(tenants.a, "enterprise")
	await set_plan(tenants.b, "community")
	a_old, b_old = await make(tenants.a, owner_a, "a", 100), await make(tenants.b, owner_b, "b", 100)
	await purge_expired_conversations()
	async with org_scoped_session(tenants.a) as db:
		assert await db.get(Conversation, a_old) is not None  # 100 days is inside an enterprise plan's 365
	async with org_scoped_session(tenants.b) as db:
		assert await db.get(Conversation, b_old) is None  # and well past a free plan's 7
	assert uuid.UUID(int=0) != a_old
