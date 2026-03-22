"""Scheduled key rotation — re-encrypt all provider keys on interval."""

from __future__ import annotations

import logging
from sqlalchemy import select

from app.config import settings
from app.database import AsyncSessionLocal, set_session_org_id
from app.models.llm_provider_key import LLMProviderKey
from app.services.provider_key_service import rotate_key

logger = logging.getLogger(__name__)


async def run_key_rotation() -> None:
    """Scheduler job: rotate (re-encrypt) all active provider keys."""
    if not getattr(settings, "KEY_ROTATION_SCHEDULER_ENABLED", False):
        return

    try:
        async with AsyncSessionLocal() as db:
            result = await db.scalars(
                select(LLMProviderKey).where(
                    LLMProviderKey.is_active.is_(True),
                    LLMProviderKey.weight > 0,
                )
            )
            keys = list(result.all())

        rotated = 0
        for key in keys:
            async with AsyncSessionLocal() as db:
                await set_session_org_id(db, key.org_id)
                if await rotate_key(
                    db,
                    key.id,
                    key.org_id,
                    actor_email="system@scheduler",
                ):
                    await db.commit()
                    rotated += 1

        if rotated:
            logger.info("Key rotation complete — rotated %d provider keys", rotated)
    except Exception:
        logger.exception("Key rotation job failed")
