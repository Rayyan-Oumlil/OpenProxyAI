"""Tests for PolicyStore.save() — verifies Redis cache is invalidated on save."""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.services.policy_service import PolicyConfig, PolicyStore


class FakeOrg:
    def __init__(self, org_id):
        self.id = org_id
        self.settings = {}


class FakeDB:

    @property
    def info(self) -> dict:
        # Mirrors AsyncSession.info (set_session_org_id stores the org there).
        return self.__dict__.setdefault("_info", {})

    def __init__(self, org):
        self._org = org

    async def scalar(self, query):  # noqa: ARG002
        return self._org

    async def commit(self):
        return None

    async def refresh(self, obj):  # noqa: ARG002
        return None


@pytest.mark.asyncio
async def test_save_invalidates_redis_cache():
    """save() must delete the Redis cache key for the org after committing."""
    org_id = uuid4()
    org = FakeOrg(org_id)
    db = FakeDB(org)

    redis = AsyncMock()

    config = PolicyConfig(
        enforcement_mode="block",
        allowed_models=["openai/gpt-4o"],
        blocked_keywords=["secret"],
        pii_detection_enabled=True,
    )

    store = PolicyStore()
    await store.save(org_id=org_id, config=config, db=db, redis=redis)

    expected_key = f"policy:config:{org_id}"
    redis.delete.assert_awaited_once_with(expected_key)


@pytest.mark.asyncio
async def test_save_does_not_invalidate_when_org_not_found():
    """save() returns early without calling redis.delete when the org is missing."""
    org_id = uuid4()

    class MissingOrgDB:
        async def scalar(self, query):  # noqa: ARG002
            return None

        async def commit(self):
            return None

        async def refresh(self, obj):  # noqa: ARG002
            return None

    redis = AsyncMock()
    config = PolicyConfig()

    store = PolicyStore()
    await store.save(org_id=org_id, config=config, db=MissingOrgDB(), redis=redis)

    redis.delete.assert_not_awaited()
