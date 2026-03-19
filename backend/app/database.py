"""Async SQLAlchemy engine and session factory for PostgreSQL."""

from collections.abc import AsyncGenerator
from uuid import UUID

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.sql import text

from app.config import settings

engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
)


async def set_session_org_id(session: AsyncSession, org_id: UUID | None) -> None:
    """Set app.current_org_id for RLS. Transaction-scoped via set_config(..., true)."""
    if org_id is None:
        # Use set_config(..., true) so the reset is transaction-scoped, matching the set path.
        # RESET is session-scoped and would leak state to the next request on a pooled connection.
        await session.execute(text("SELECT set_config('app.current_org_id', '', true)"))
    else:
        if not isinstance(org_id, UUID):
            raise TypeError("org_id must be UUID or None")
        await session.execute(
            text("SELECT set_config('app.current_org_id', :org_id, true)"),
            {"org_id": str(org_id)},
        )


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that yields an async DB session and closes it after use."""
    async with AsyncSessionLocal() as session:
        yield session


async def ping_db() -> bool:
    """Run ``SELECT 1`` to verify the database is reachable."""
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    return True
