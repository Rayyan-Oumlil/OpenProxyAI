"""Async SQLAlchemy engine and session factory for PostgreSQL."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

from sqlalchemy import event
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.sql import text

from app.config import settings

# Request-path engine: every pooled connection switches to DB_APP_ROLE, which is
# subject to row-level security (superusers and FORCE-exempt roles are not).
engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

# System engine: keeps the login role. Only for jobs that must read across orgs
# (provider health checks, key rotation, adaptive sampling). Never for request handling.
system_engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=2,
    max_overflow=2,
)


def set_app_role(dbapi_connection: Any, _connection_record: Any) -> None:
    """Switch a new connection to the RLS-subject app role (DB_APP_ROLE is validated as an identifier)."""
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute(f'SET ROLE "{settings.DB_APP_ROLE}"')
    finally:
        cursor.close()


event.listen(engine.sync_engine, "connect", set_app_role)

# Session.info key holding the org a session is scoped to (set by set_session_org_id).
RLS_ORG_KEY = "rls_org_id"
_SET_ORG_SQL = text("SELECT set_config('app.current_org_id', :org_id, true)")


class RequestSession(Session):
    """Sync session class behind AsyncSessionLocal; carries the org-reapply listener."""


def reapply_org_on_begin(session: Any, _transaction: Any, connection: Any) -> None:
    """Re-apply the session's org at the start of every transaction.

    set_config(..., true) is transaction-scoped, so without this a route that sets the
    org once (in its auth dependency), commits, and keeps querying would lose it.
    """
    org_id = session.info.get(RLS_ORG_KEY)
    if org_id is not None:
        connection.execute(_SET_ORG_SQL, {"org_id": org_id})


event.listen(RequestSession, "after_begin", reapply_org_on_begin)

AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    sync_session_class=RequestSession,
)

SystemSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=system_engine,
    expire_on_commit=False,
)


async def set_session_org_id(session: AsyncSession, org_id: UUID | None) -> None:
    """Scope ``session`` to ``org_id`` for RLS, for this and every later transaction on it."""
    if org_id is None:
        session.info.pop(RLS_ORG_KEY, None)
        # Transaction-scoped reset: RESET is session-scoped and would leak to pooled connections.
        await session.execute(text("SELECT set_config('app.current_org_id', '', true)"))
        return
    if not isinstance(org_id, UUID):
        raise TypeError("org_id must be UUID or None")
    session.info[RLS_ORG_KEY] = str(org_id)
    await session.execute(_SET_ORG_SQL, {"org_id": str(org_id)})


@asynccontextmanager
async def org_scoped_session(org_id: UUID) -> AsyncIterator[AsyncSession]:
    """Open a request-role session already scoped to ``org_id`` for RLS.

    Use this for every background write to an org-owned table: the insert then
    passes the policy's WITH CHECK, and a wrong org fails loudly instead of leaking.
    """
    async with AsyncSessionLocal() as session:
        await set_session_org_id(session, org_id)
        yield session


async def ping_db() -> bool:
    """Run ``SELECT 1`` to verify the database is reachable."""
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    return True
