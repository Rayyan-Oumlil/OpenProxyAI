"""Conversation retention (Phase 4 follow-up): conversations follow the org plan's audit retention, like captured payloads.

A conversation that has not been touched for longer than the plan's ``audit_retention_days`` is deleted whole. Its turns and its
context records go with it through the foreign-key cascade (the application role may not delete context records directly, they are
append-only, but the cascade is allowed). "Touched" is the last message or edit, so an active conversation is never cut short.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select

from app.config import PLAN_FEATURES
from app.database import AsyncSessionLocal, set_session_org_id
from app.models.conversation import Conversation
from app.models.organization import Organization

logger = logging.getLogger(__name__)


def retention_days(plan: str | None) -> int:
	return PLAN_FEATURES.get((plan or "free").lower(), PLAN_FEATURES["free"])["audit_retention_days"]


async def purge_expired_conversations(now: datetime | None = None) -> int:
	"""Delete conversations idle past their org's retention, one organization at a time (row-level security is forced). Returns how many."""
	moment = (now or datetime.now(UTC)).replace(tzinfo=None)
	deleted = 0
	try:
		async with AsyncSessionLocal() as session:
			for org_id, plan in list((await session.execute(select(Organization.id, Organization.plan))).all()):
				await set_session_org_id(session, org_id)
				result = await session.execute(
					delete(Conversation).where(Conversation.org_id == org_id, Conversation.updated_at < moment - timedelta(days=retention_days(plan)))
				)
				deleted += result.rowcount or 0
			await session.commit()
		logger.info("purge_expired_conversations removed %d conversations", deleted)
	except Exception:
		logger.exception("Failed to purge expired conversations")
	return deleted
