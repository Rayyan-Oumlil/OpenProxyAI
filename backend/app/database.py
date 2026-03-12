"""Async SQLAlchemy engine and session factory for PostgreSQL."""

from collections.abc import AsyncGenerator

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


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that yields an async DB session and closes it after use."""
    async with AsyncSessionLocal() as session:
        yield session


async def ping_db() -> bool:
    """Run ``SELECT 1`` to verify the database is reachable."""
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    return True
