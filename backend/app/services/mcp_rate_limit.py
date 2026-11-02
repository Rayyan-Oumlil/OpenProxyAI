"""Per-API-key fixed-window rate limit for the MCP gateway.

Kept apart from rate_limiter.RateLimiterService: that one counts LLM requests, tokens and dollars per
organisation, and tool calls must not consume the LLM quota. Redis is a core service, so a Redis error
propagates (fails hard) instead of letting traffic through unmetered.
"""

import time
import uuid

from redis.asyncio import Redis

WINDOW_SECONDS = 60


async def check_mcp_rate_limit(redis: Redis, api_key_id: uuid.UUID, limit: int) -> tuple[bool, int]:
	"""Count one request for ``api_key_id``. Returns (allowed, retry_after_seconds)."""
	now = int(time.time())
	bucket = now // WINDOW_SECONDS
	key = f"rl:mcp:{api_key_id}:{bucket}"
	pipe = redis.pipeline(transaction=True)
	pipe.incr(key)
	pipe.expire(key, WINDOW_SECONDS * 2)
	count, _ = await pipe.execute()
	retry_after = max((bucket + 1) * WINDOW_SECONDS - now, 1)
	return int(count) <= limit, retry_after
