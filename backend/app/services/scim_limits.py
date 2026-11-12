"""Fixed-window limits for /scim/v2: requests per org, and failed token attempts per client address.

Redis is a core service here, so a Redis error propagates (the request fails) instead of letting traffic through unmetered.
"""

from __future__ import annotations

import time
import uuid

from redis.asyncio import Redis

WINDOW_SECONDS = 60
ORG_REQUESTS_PER_WINDOW = 600
FAILED_ATTEMPTS_PER_WINDOW = 20


def _bucket() -> tuple[int, int]:
    now = int(time.time())
    bucket = now // WINDOW_SECONDS
    return bucket, max((bucket + 1) * WINDOW_SECONDS - now, 1)


async def _count(redis: Redis, key: str) -> int:
    pipe = redis.pipeline(transaction=True)
    pipe.incr(key)
    pipe.expire(key, WINDOW_SECONDS * 2)
    count, _ = await pipe.execute()
    return int(count)


async def too_many_failures(redis: Redis, client_ip: str) -> int | None:
    """Seconds to wait if this address has already failed too often this window; None otherwise. Does not count."""
    bucket, retry = _bucket()
    seen = await redis.get(f"rl:scim-fail:{client_ip}:{bucket}")
    return retry if seen is not None and int(seen) >= FAILED_ATTEMPTS_PER_WINDOW else None


async def record_failure(redis: Redis, client_ip: str) -> None:
    bucket, _ = _bucket()
    await _count(redis, f"rl:scim-fail:{client_ip}:{bucket}")


async def org_over_limit(redis: Redis, org_id: uuid.UUID) -> int | None:
    """Count one request for the org; seconds to wait if it is over the window's limit, else None."""
    bucket, retry = _bucket()
    count = await _count(redis, f"rl:scim:{org_id}:{bucket}")
    return retry if count > ORG_REQUESTS_PER_WINDOW else None
