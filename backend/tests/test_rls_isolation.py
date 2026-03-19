"""Row-Level Security (RLS) isolation integration tests.

Test against the REAL database schema. Requires:
- DATABASE_URL pointing to a PostgreSQL instance
- RLS migration (f8a9b0c1d2e3) applied
- Run with: pytest tests/test_rls_isolation.py -v
"""

from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.database import set_session_org_id
from app.models.api_key import ApiKey
from app.models.organization import Organization
from app.models.user import User
from app.utils.crypto import hash_password


def _db_available() -> bool:
    url = os.environ.get("DATABASE_URL", "")
    return bool(url and "postgresql" in url)


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not _db_available(), reason="DATABASE_URL not set or not PostgreSQL"),
]


RLS_TABLES = [
    "request_logs",
    "api_keys",
    "llm_provider_keys",
    "webhook_deliveries",
    "semantic_cache_entries",
    "prompt_templates",
]


@pytest.fixture
async def db_engine():
    url = os.environ.get("DATABASE_URL") or ""
    if not url.strip():
        pytest.skip("DATABASE_URL not set (required for RLS integration tests)")
    engine = create_async_engine(url, poolclass=NullPool)
    yield engine
    await engine.dispose()


@pytest.fixture
async def two_orgs(db_engine):
    """Create two orgs with users and return (org_a_id, org_b_id)."""
    from app.database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        org_a = Organization(name="RLS Test Org A", slug=f"rls-a-{uuid.uuid4().hex[:8]}")
        org_b = Organization(name="RLS Test Org B", slug=f"rls-b-{uuid.uuid4().hex[:8]}")
        session.add(org_a)
        session.add(org_b)
        await session.flush()

        user_a = User(
            org_id=org_a.id,
            email=f"rls-a-{uuid.uuid4().hex[:8]}@test.local",
            password_hash=hash_password("TestPass1!"),
            role="admin",
            is_active=True,
        )
        user_b = User(
            org_id=org_b.id,
            email=f"rls-b-{uuid.uuid4().hex[:8]}@test.local",
            password_hash=hash_password("TestPass1!"),
            role="admin",
            is_active=True,
        )
        session.add(user_a)
        session.add(user_b)
        await session.flush()

        await set_session_org_id(session, org_b.id)
        key_b = ApiKey(
            user_id=user_b.id,
            org_id=org_b.id,
            key_hash="rls_test_hash_" + uuid.uuid4().hex,
            key_prefix="opai_rls",
            is_active=True,
        )
        session.add(key_b)
        await session.commit()
        await session.refresh(org_a)
        await session.refresh(org_b)

    yield org_a.id, org_b.id


@pytest.mark.asyncio
async def test_rls_blocks_cross_org_access(db_engine, two_orgs):
    """With org_id set to org A, queries must not return org B's data."""
    org_a_id, org_b_id = two_orgs

    async with db_engine.connect() as conn:
        async with conn.begin():
            await conn.execute(
                text("SELECT set_config('app.current_org_id', :org_id, true)"),
                {"org_id": str(org_a_id)},
            )

            for table in RLS_TABLES:
                result = await conn.execute(
                    text(f"SELECT COUNT(*) FROM {table} WHERE org_id = :org_b"),
                    {"org_b": org_b_id},
                )
                count = result.scalar() or 0
                assert count == 0, f"RLS leak: {table} exposed {count} rows from org B"


@pytest.mark.asyncio
async def test_set_session_org_id_scopes_orm_queries(db_engine, two_orgs):
    """set_session_org_id restricts ORM queries to the given org."""
    from app.database import AsyncSessionLocal

    org_a_id, org_b_id = two_orgs

    async with AsyncSessionLocal() as session:
        await set_session_org_id(session, org_a_id)
        keys = await session.scalars(select(ApiKey).where(ApiKey.org_id == org_b_id))
        assert len(keys.all()) == 0

        await set_session_org_id(session, org_b_id)
        keys = await session.scalars(select(ApiKey).where(ApiKey.org_id == org_b_id))
        assert len(keys.all()) >= 1


@pytest.mark.asyncio
async def test_rls_allows_own_org_data(db_engine, two_orgs):
    """With org_id set to org B, queries return org B's data."""
    org_a_id, org_b_id = two_orgs

    async with db_engine.connect() as conn:
        async with conn.begin():
            await conn.execute(
                text("SELECT set_config('app.current_org_id', :org_id, true)"),
                {"org_id": str(org_b_id)},
            )

            result = await conn.execute(
                text("SELECT COUNT(*) FROM api_keys WHERE org_id = :org_b"),
                {"org_b": org_b_id},
            )
            count = result.scalar() or 0
            assert count >= 1, "RLS should allow reading own org's api_keys"
