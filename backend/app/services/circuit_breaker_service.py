"""Circuit breaker for provider keys — skip keys after N consecutive failures."""

from __future__ import annotations

import logging
import time
from uuid import UUID

from redis.asyncio import Redis

from app.config import settings

logger = logging.getLogger(__name__)

_CIRCUIT_PREFIX = "circuit"
_FAILURES_SUFFIX = "failures"
_OPEN_UNTIL_SUFFIX = "open_until"


def _key_failures(key_id: UUID) -> str:
    return f"{_CIRCUIT_PREFIX}:{key_id}:{_FAILURES_SUFFIX}"


def _key_open_until(key_id: UUID) -> str:
    return f"{_CIRCUIT_PREFIX}:{key_id}:{_OPEN_UNTIL_SUFFIX}"


def is_enabled() -> bool:
    return getattr(settings, "CIRCUIT_BREAKER_ENABLED", False)


def _threshold() -> int:
    return getattr(settings, "CIRCUIT_BREAKER_FAILURE_THRESHOLD", 5)


def _cooldown_seconds() -> int:
    return getattr(settings, "CIRCUIT_BREAKER_COOLDOWN_SECONDS", 60)


async def is_circuit_open(redis: Redis | None, key_id: UUID | None) -> bool:
    """Return True if circuit for key_id is open (should skip this key)."""
    if not redis or key_id is None or not is_enabled():
        return False
    open_until_raw = await redis.get(_key_open_until(key_id))
    if not open_until_raw:
        return False
    try:
        open_until = float(open_until_raw)
        return time.time() < open_until
    except (ValueError, TypeError):
        return False


async def record_failure(redis: Redis | None, key_id: UUID | None) -> None:
    """Increment failure count; if >= threshold, open circuit."""
    if not redis or key_id is None or not is_enabled():
        return
    failures_key = _key_failures(key_id)
    open_until_key = _key_open_until(key_id)
    count = await redis.incr(failures_key)
    await redis.expire(failures_key, 3600)
    if count >= _threshold():
        open_until = int(time.time()) + _cooldown_seconds()
        await redis.setex(open_until_key, _cooldown_seconds() + 10, str(open_until))
        await redis.delete(failures_key)
        logger.warning("Circuit opened for provider key %s until %s", key_id, open_until)


async def record_success(redis: Redis | None, key_id: UUID | None) -> None:
    """Reset failure count for key."""
    if not redis or key_id is None or not is_enabled():
        return
    await redis.delete(_key_failures(key_id))


async def get_open_until(redis: Redis | None, key_id: UUID | None) -> float | None:
    """Return Unix timestamp when circuit closes, or None if closed."""
    if not redis or key_id is None:
        return None
    raw = await redis.get(_key_open_until(key_id))
    if not raw:
        return None
    try:
        return float(raw)
    except (ValueError, TypeError):
        return None
