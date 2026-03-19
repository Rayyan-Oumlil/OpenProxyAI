"""
3-tier cache: L1 in-memory TTLCache, L2 Redis exact-match, L3 pgvector semantic.
Off by default — enable via CACHE_ENABLED (L2) and SEMANTIC_CACHE_ENABLED (L1+L3).
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from datetime import UTC, datetime
from typing import Any, Literal, Optional
from uuid import UUID

from cachetools import TTLCache
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings

logger = logging.getLogger(__name__)

# L1 in-memory cache — keyed by SHA-256 hash
_L1_CACHE: TTLCache[str, dict[str, Any]] | None = None
_L1_LOCK = asyncio.Lock()


def _get_l1_cache() -> TTLCache[str, dict[str, Any]] | None:
    """Lazy-init L1 cache when semantic cache is enabled."""
    global _L1_CACHE
    if not getattr(settings, "SEMANTIC_CACHE_ENABLED", False):
        return None
    if _L1_CACHE is None:
        maxsize = getattr(settings, "SEMANTIC_CACHE_L1_MAX_SIZE", 1000)
        ttl = getattr(settings, "SEMANTIC_CACHE_L1_TTL_SECONDS", 300)
        _L1_CACHE = TTLCache(maxsize=maxsize, ttl=ttl)
    return _L1_CACHE


def _make_key(model: str, messages: list, temperature: Optional[float]) -> str:
    """SHA-256 hash for exact-match key (L2 Redis)."""
    payload = json.dumps(
        {"model": model, "messages": messages, "temp": temperature},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def _messages_hash(messages: list) -> str:
    """SHA-256 of messages only (for semantic dedup)."""
    payload = json.dumps(messages, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def _cache_key_text(messages: list) -> str:
    """Concatenate message contents for embedding input."""
    parts = []
    for m in messages:
        if isinstance(m, dict):
            content = m.get("content") or m.get("text") or ""
        else:
            content = getattr(m, "content", None) or getattr(m, "text", "") or ""
        if isinstance(content, str):
            parts.append(content)
        elif isinstance(content, list):
            for c in content:
                if isinstance(c, dict) and "text" in c:
                    parts.append(c["text"])
    return "\n".join(parts)


def _redis_key(sha: str) -> str:
    return "cache:" + sha


def _today_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


def is_enabled() -> bool:
    """True if any cache layer is enabled."""
    return getattr(settings, "CACHE_ENABLED", False) or getattr(
        settings, "SEMANTIC_CACHE_ENABLED", False
    )


CacheTier = Literal["hit:exact", "hit:semantic"]
CacheOverride = Literal["skip", "no-store", "no-cache"]


async def _record_metrics(
    redis: Redis,
    org_id: UUID | str,
    tier: CacheTier,
    token_count: int,
) -> None:
    """Fire-and-forget: increment hit metrics and tokens saved."""
    try:
        today = _today_iso()
        org = str(org_id)
        if tier == "hit:exact":
            await redis.incr(f"cache:hits:exact:{org}:{today}")
        else:
            await redis.incr(f"cache:hits:semantic:{org}:{today}")
        if token_count > 0:
            await redis.incrby(f"cache:tokens_saved:{org}:{today}", token_count)
    except Exception as exc:
        logger.warning("Cache metrics record failed: %s", exc)


async def _record_miss(redis: Redis, org_id: UUID | str) -> None:
    """Fire-and-forget: increment miss metric."""
    try:
        today = _today_iso()
        await redis.incr(f"cache:misses:{str(org_id)}:{today}")
    except Exception as exc:
        logger.warning("Cache miss metrics record failed: %s", exc)


async def get(
    redis: Redis,
    model: str,
    messages: list,
    temperature: Optional[float] = None,
    *,
    org_id: Optional[UUID | str] = None,
    db: Optional[AsyncSession] = None,
    cache_override: Optional[CacheOverride] = None,
) -> tuple[Optional[dict[str, Any]], Optional[str]]:
    """
    Return (cached_response, cache_tier) or (None, None) on miss.
    cache_tier: "hit:exact" | "hit:semantic" | None
    """
    if cache_override == "skip":
        return None, None

    if not is_enabled():
        return None, None

    sha = _make_key(model, messages, temperature)
    cache_key_text = _cache_key_text(messages)

    # L1
    l1 = _get_l1_cache()
    if l1 is not None:
        async with _L1_LOCK:
            hit = l1.get(sha)
        if hit is not None:
            if org_id:
                usage = hit.get("usage", {}) or {}
                token_count = int(usage.get("total_tokens", 0)) or (
                    int(usage.get("prompt_tokens", 0)) + int(usage.get("completion_tokens", 0))
                )
                asyncio.create_task(_record_metrics(redis, org_id, "hit:exact", token_count))
            return hit, "hit:exact"

    # L2 Redis
    if getattr(settings, "CACHE_ENABLED", False):
        try:
            key = _redis_key(sha)
            raw = await redis.get(key)
            if raw is not None:
                body = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
                if isinstance(body, bytes):
                    body = json.loads(body.decode())
                # Populate L1
                if l1 is not None:
                    async with _L1_LOCK:
                        l1[sha] = body
                if org_id:
                    usage = body.get("usage", {}) or {}
                    token_count = int(usage.get("total_tokens", 0)) or (
                        int(usage.get("prompt_tokens", 0)) + int(usage.get("completion_tokens", 0))
                    )
                    asyncio.create_task(_record_metrics(redis, org_id, "hit:exact", token_count))
                return body, "hit:exact"
        except Exception as exc:
            logger.warning("Cache L2 get failed: %s", exc)

    # L3 pgvector semantic
    if (
        getattr(settings, "SEMANTIC_CACHE_ENABLED", False)
        and db is not None
        and org_id is not None
        and cache_key_text.strip()
    ):
        try:
            from app.models.semantic_cache import SemanticCacheEntry
            from litellm import aembedding

            emb_model = getattr(settings, "SEMANTIC_CACHE_EMBEDDING_MODEL", "text-embedding-3-small")
            emb_result = await aembedding(model=emb_model, input=cache_key_text)
            if emb_result and emb_result.data:
                query_embedding = emb_result.data[0].embedding
            else:
                query_embedding = None

            if query_embedding:
                from sqlalchemy import and_, func

                threshold = getattr(settings, "SEMANTIC_CACHE_SIMILARITY_THRESHOLD", 0.95)
                dist_col = SemanticCacheEntry.embedding.cosine_distance(query_embedding)
                stmt = (
                    select(SemanticCacheEntry, dist_col)
                    .where(
                        and_(
                            SemanticCacheEntry.org_id == org_id,
                            SemanticCacheEntry.model == model,
                            SemanticCacheEntry.expires_at > func.now(),
                        )
                    )
                    .order_by(dist_col)
                    .limit(1)
                )
                result = await db.execute(stmt)
                row_tuple = result.one_or_none()
                if row_tuple is not None:
                    row, distance = row_tuple
                    similarity = 1.0 - float(distance) if distance is not None else 0.0
                    if similarity >= threshold:
                        body = row.response_json
                        if l1 is not None:
                            async with _L1_LOCK:
                                l1[sha] = body
                        asyncio.create_task(
                            _record_metrics(redis, org_id, "hit:semantic", row.token_count)
                        )
                        return body, "hit:semantic"
        except Exception as exc:
            logger.warning("Cache L3 semantic get failed: %s", exc)

    if org_id:
        asyncio.create_task(_record_miss(redis, org_id))
    return None, None


async def set(
    redis: Redis,
    model: str,
    messages: list,
    temperature: Optional[float],
    response: Any,
    *,
    org_id: Optional[UUID | str] = None,
    db: Optional[AsyncSession] = None,
    ttl: Optional[int] = None,
    cache_override: Optional[CacheOverride] = None,
) -> None:
    """Store response in cache. Fire-and-forget (swallows exceptions)."""
    if cache_override == "skip" or cache_override == "no-store":
        return
    if not is_enabled():
        return

    sha = _make_key(model, messages, temperature)
    body = response if isinstance(response, dict) else {}
    if not isinstance(body, dict):
        try:
            body = json.loads(json.dumps(response, default=str))
        except Exception:
            return

    ttl = ttl or getattr(settings, "CACHE_TTL_SECONDS", 3600)
    usage = body.get("usage", {}) or {}
    token_count = int(usage.get("total_tokens", 0)) or (
        int(usage.get("prompt_tokens", 0)) + int(usage.get("completion_tokens", 0))
    )

    # L1
    l1 = _get_l1_cache()
    if l1 is not None:
        try:
            async with _L1_LOCK:
                l1[sha] = body
        except Exception as exc:
            logger.warning("Cache L1 set failed: %s", exc)

    # L2 Redis
    if getattr(settings, "CACHE_ENABLED", False):
        try:
            key = _redis_key(sha)
            await redis.setex(key, ttl, json.dumps(body))
        except Exception as exc:
            logger.warning("Cache L2 set failed: %s", exc)

    # L3 pgvector — fire-and-forget
    if (
        getattr(settings, "SEMANTIC_CACHE_ENABLED", False)
        and db is not None
        and org_id is not None
    ):
        asyncio.create_task(
            _set_l3_semantic(org_id, model, messages, body, token_count, ttl)
        )


async def _set_l3_semantic(
    org_id: UUID | str,
    model: str,
    messages: list,
    response_json: dict,
    token_count: int,
    ttl: int,
) -> None:
    """Fire-and-forget: embed + insert into semantic_cache_entries.

    Creates its own DB session — the request-scoped session may be closed
    by the time this task runs. Swallows all exceptions (sidecar pattern).
    """
    try:
        from datetime import timedelta, timezone

        from app.database import AsyncSessionLocal
        from app.models.semantic_cache import SemanticCacheEntry
        from litellm import aembedding

        cache_text = _cache_key_text(messages)
        if not cache_text.strip():
            return

        emb_model = getattr(settings, "SEMANTIC_CACHE_EMBEDDING_MODEL", "text-embedding-3-small")
        emb_result = await aembedding(model=emb_model, input=cache_text)
        if not emb_result or not emb_result.data:
            return

        embedding = emb_result.data[0].embedding
        messages_hash = _messages_hash(messages)
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl)

        async with AsyncSessionLocal() as session:
            entry = SemanticCacheEntry(
                org_id=org_id,
                model=model,
                messages_hash=messages_hash,
                embedding=embedding,
                response_json=response_json,
                token_count=token_count,
                expires_at=expires_at,
            )
            session.add(entry)
            await session.commit()
    except Exception as exc:
        logger.warning("Cache L3 semantic set failed: %s", exc)
