"""
Exact-match semantic cache using Redis SHA-256 key.
Off by default — enable via CACHE_ENABLED=true.
"""
from __future__ import annotations
import hashlib
import json
import logging
from typing import Optional, Any

from app.config import settings

logger = logging.getLogger(__name__)


def _make_key(model: str, messages: list, temperature: Optional[float]) -> str:
    payload = json.dumps(
        {"model": model, "messages": messages, "temp": temperature},
        sort_keys=True,
        separators=(",", ":"),
    )
    return "cache:" + hashlib.sha256(payload.encode()).hexdigest()


def is_enabled() -> bool:
    return getattr(settings, "CACHE_ENABLED", False)


async def get(
    redis,
    model: str,
    messages: list,
    temperature: Optional[float] = None,
) -> Optional[Any]:
    """Return cached response dict or None."""
    if not is_enabled():
        return None
    try:
        key = _make_key(model, messages, temperature)
        raw = await redis.get(key)
        if raw is None:
            return None
        return json.loads(raw)
    except Exception as exc:
        logger.warning("Cache get failed: %s", exc)
        return None


async def set(
    redis,
    model: str,
    messages: list,
    temperature: Optional[float],
    response: Any,
    ttl: Optional[int] = None,
) -> None:
    """Store response in cache. Fire-and-forget (swallows exceptions)."""
    if not is_enabled():
        return
    try:
        key = _make_key(model, messages, temperature)
        ttl = ttl or getattr(settings, "CACHE_TTL_SECONDS", 3600)
        await redis.setex(key, ttl, json.dumps(response))
    except Exception as exc:
        logger.warning("Cache set failed: %s", exc)
