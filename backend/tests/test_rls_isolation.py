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


# CI sets RLS_TESTS_REQUIRED so a missing database fails the build instead of skipping silently.
_REQUIRED = bool(os.environ.get("RLS_TESTS_REQUIRED"))

if _REQUIRED and not _db_available():
    raise RuntimeError("RLS_TESTS_REQUIRED is set but DATABASE_URL is not a PostgreSQL URL")

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
async def test_request_engine_runs_as_app_role(two_orgs):  # noqa: ARG001
    """Request-path sessions are switched to the RLS-subject role, whatever the login role is."""
    from app.config import settings
    from app.database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        assert await session.scalar(text("SELECT current_user")) == settings.DB_APP_ROLE


@pytest.mark.asyncio
async def test_rls_blocks_cross_org_access(two_orgs):
    """With org A set on a request session, no RLS table exposes org B's rows."""
    from app.database import AsyncSessionLocal

    org_a_id, org_b_id = two_orgs
    async with AsyncSessionLocal() as session:
        await set_session_org_id(session, org_a_id)
        for table in RLS_TABLES:
            count = await session.scalar(
                text(f"SELECT COUNT(*) FROM {table} WHERE org_id = :org_b"), {"org_b": org_b_id}
            )
            assert count == 0, f"RLS leak: {table} exposed {count} rows from org B"


@pytest.mark.asyncio
async def test_request_session_without_org_sees_nothing(two_orgs):
    """Forgetting set_session_org_id hides rows instead of leaking them."""
    from app.database import AsyncSessionLocal

    _, org_b_id = two_orgs
    async with AsyncSessionLocal() as session:
        count = await session.scalar(
            text("SELECT COUNT(*) FROM api_keys WHERE org_id = :org_b"), {"org_b": org_b_id}
        )
        assert count == 0


@pytest.mark.asyncio
async def test_set_session_org_id_scopes_orm_queries(two_orgs):
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
async def test_system_session_reads_across_orgs(two_orgs):
    """Cross-org jobs use the system session, which keeps the login role."""
    from app.database import SystemSessionLocal

    _, org_b_id = two_orgs
    async with SystemSessionLocal() as session:
        count = await session.scalar(
            text("SELECT COUNT(*) FROM api_keys WHERE org_id = :org_b"), {"org_b": org_b_id}
        )
        assert count >= 1


@pytest.mark.asyncio
async def test_request_logs_are_append_only(two_orgs):
    """The app role can insert logs and set archived_at, but never rewrite or delete them."""
    from sqlalchemy.exc import DBAPIError

    from app.database import org_scoped_session
    from app.models.request_log import RequestLog

    org_a_id, _ = two_orgs
    async with org_scoped_session(org_a_id) as session:
        user_id = await session.scalar(select(User.id).where(User.org_id == org_a_id))
        session.add(RequestLog(
            request_id=uuid.uuid4(), org_id=org_a_id, user_id=user_id,
            model="m", provider="p", status_code=200, request_metadata={},
        ))
        await session.commit()

    async with org_scoped_session(org_a_id) as session:
        await session.execute(text("UPDATE request_logs SET archived_at = now() WHERE org_id = :o"), {"o": org_a_id})
        await session.commit()

    for statement in (
        "UPDATE request_logs SET model = 'tampered' WHERE org_id = :o",
        "DELETE FROM request_logs WHERE org_id = :o",
    ):
        async with org_scoped_session(org_a_id) as session:
            with pytest.raises(DBAPIError, match="permission denied"):
                await session.execute(text(statement), {"o": org_a_id})


@pytest.mark.asyncio
async def test_rls_rejects_insert_for_another_org(two_orgs):
    """WITH CHECK stops a session scoped to org A from writing org B's rows."""
    from sqlalchemy.exc import DBAPIError

    from app.database import org_scoped_session

    org_a_id, org_b_id = two_orgs
    async with org_scoped_session(org_a_id) as session:
        with pytest.raises(DBAPIError, match="row-level security"):
            await session.execute(
                text(
                    "INSERT INTO api_keys (id, user_id, org_id, key_hash, key_prefix, is_active) "
                    "SELECT gen_random_uuid(), u.id, :b, 'forged_' || gen_random_uuid(), 'opai_x', true "
                    "FROM users u WHERE u.org_id = :a LIMIT 1"
                ),
                {"a": org_a_id, "b": org_b_id},
            )


@pytest.mark.asyncio
async def test_org_scope_survives_commit(two_orgs):
    """Routes set the org once in a dependency, then commit and keep querying."""
    from app.database import AsyncSessionLocal

    _, org_b_id = two_orgs
    async with AsyncSessionLocal() as session:
        await set_session_org_id(session, org_b_id)
        before = await session.scalar(text("SELECT COUNT(*) FROM api_keys WHERE org_id = :b"), {"b": org_b_id})
        await session.commit()
        after = await session.scalar(text("SELECT COUNT(*) FROM api_keys WHERE org_id = :b"), {"b": org_b_id})
    assert before >= 1 and after == before
