"""Adaptive load balancing — sample latency/error per provider key from request_logs."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

import redis.asyncio as aioredis
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import SystemSessionLocal

logger = logging.getLogger(__name__)

_PREFIX = "adaptive"
_TTL = 600  # 10 min — slightly longer than sample window


def _key_latency_p99(key_id: UUID) -> str:
    return f"{_PREFIX}:{key_id}:latency_p99"


def _key_error_rate(key_id: UUID) -> str:
    return f"{_PREFIX}:{key_id}:error_rate"


async def run_adaptive_sampling(redis: Redis, db: AsyncSession) -> int:
    """Query request_logs for last N minutes, aggregate per provider_key_id, store in Redis.

    Returns count of keys updated.
    """
    minutes = getattr(settings, "ADAPTIVE_LB_SAMPLE_MINUTES", 10)
    cutoff = datetime.now(UTC) - timedelta(minutes=minutes)

    stmt = text("""
        SELECT
            provider_key_id,
            percentile_cont(0.99) WITHIN GROUP (ORDER BY latency_ms) FILTER (WHERE latency_ms IS NOT NULL) AS p99,
            COUNT(*)::int AS total,
            COUNT(*) FILTER (WHERE status_code IN (429, 500, 502, 503, 504))::int AS errors
        FROM request_logs
        WHERE created_at >= :cutoff
          AND provider_key_id IS NOT NULL
        GROUP BY provider_key_id
    """)
    result = await db.execute(stmt, {"cutoff": cutoff})
    rows = result.mappings().all()

    updated = 0
    pipe = redis.pipeline()
    for row in rows:
        key_id = row["provider_key_id"]
        if key_id is None:
            continue
        kid = key_id if isinstance(key_id, UUID) else UUID(str(key_id))
        p99 = row["p99"]
        total = row["total"] or 0
        errors = row["errors"] or 0
        error_rate = errors / total if total > 0 else 0.0
        p99_val = float(p99) if p99 is not None else 0.0
        pipe.setex(_key_latency_p99(kid), _TTL, str(p99_val))
        pipe.setex(_key_error_rate(kid), _TTL, str(error_rate))
        updated += 1
    if updated > 0:
        await pipe.execute()
    return updated


async def get_latency_p99(redis: Redis, key_id: UUID) -> float | None:
    """Return cached p99 latency (ms) for a provider key, or None if not available."""
    val = await redis.get(_key_latency_p99(key_id))
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


async def get_error_rate(redis: Redis, key_id: UUID) -> float | None:
    """Return cached error rate (0.0–1.0) for a provider key, or None if not available."""
    val = await redis.get(_key_error_rate(key_id))
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


async def run_adaptive_sampling_job() -> None:
    """APScheduler entrypoint: sample request_logs, write adaptive metrics to Redis."""
    if not getattr(settings, "ADAPTIVE_LB_ENABLED", False):
        return
    try:
        redis = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
        )
        try:
            # Aggregates request_logs across every org, so it needs the system session.
            async with SystemSessionLocal() as db:
                count = await run_adaptive_sampling(redis, db)
                logger.debug("Adaptive sampling complete — %d keys updated", count)
        finally:
            await redis.aclose()
    except Exception:
        logger.exception("Adaptive sampling job failed")
