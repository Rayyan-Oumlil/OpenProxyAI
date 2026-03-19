"""Tests for 3-tier semantic cache — L1, L2, L3, overrides, metrics."""
import asyncio
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.services import cache_service


@pytest.fixture
def mock_redis():
    r = AsyncMock()
    r.get = AsyncMock(return_value=None)
    r.setex = AsyncMock(return_value=True)
    r.incr = AsyncMock(return_value=1)
    r.incrby = AsyncMock(return_value=1)
    return r


@pytest.fixture
def org_id():
    return uuid.uuid4()


# ── L1 hit ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_l1_hit_returns_cached_response(mock_redis, org_id):
    """L1 in-memory hit returns cached response with hit:exact."""
    cached = {"choices": [{"message": {"content": "cached"}}], "usage": {"total_tokens": 10}}
    with (
        patch.object(cache_service, "is_enabled", return_value=True),
        patch.object(settings, "CACHE_ENABLED", False),
        patch.object(settings, "SEMANTIC_CACHE_ENABLED", True),
        patch.object(settings, "SEMANTIC_CACHE_L1_MAX_SIZE", 1000),
        patch.object(settings, "SEMANTIC_CACHE_L1_TTL_SECONDS", 300),
    ):
        cache_service._get_l1_cache()
        cache_service._L1_CACHE.clear()
        sha = cache_service._make_key("gpt-4", [{"role": "user", "content": "hi"}], 0.7)
        async with cache_service._L1_LOCK:
            cache_service._L1_CACHE[sha] = cached

        result, tier = await cache_service.get(
            mock_redis,
            "gpt-4",
            [{"role": "user", "content": "hi"}],
            0.7,
            org_id=org_id,
        )
        assert result == cached
        assert tier == "hit:exact"
        mock_redis.get.assert_not_called()


# ── L2 hit ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_l2_hit_returns_cached_response(mock_redis, org_id):
    """L2 Redis exact-match hit returns cached response."""
    cached = {"choices": [{"message": {"content": "redis"}}], "usage": {"total_tokens": 5}}
    mock_redis.get = AsyncMock(return_value=json.dumps(cached))
    with (
        patch.object(cache_service, "is_enabled", return_value=True),
        patch.object(settings, "CACHE_ENABLED", True),
        patch.object(settings, "SEMANTIC_CACHE_ENABLED", False),
    ):
        result, tier = await cache_service.get(
            mock_redis,
            "gpt-4",
            [{"role": "user", "content": "hello"}],
            0.5,
            org_id=org_id,
        )
        assert result == cached
        assert tier == "hit:exact"


# ── L3 semantic hit ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_l3_semantic_hit_when_similarity_above_threshold(mock_redis, org_id):
    """L3 pgvector returns response when similarity >= threshold."""
    embedding = [0.1] * 1536
    cached_body = {"choices": [{"message": {"content": "semantic"}}], "usage": {"total_tokens": 8}}
    mock_db = AsyncMock(spec=AsyncSession)

    async def mock_execute(stmt):
        class Row:
            def one_or_none(self):
                entry = MagicMock()
                entry.response_json = cached_body
                entry.token_count = 8
                entry.embedding = MagicMock()
                entry.embedding.cosine_distance = MagicMock(return_value=0.03)
                return (entry, 0.03)

        result = MagicMock()
        result.one_or_none = Row().one_or_none
        return result

    mock_db.execute = AsyncMock(side_effect=mock_execute)

    with (
        patch.object(cache_service, "is_enabled", return_value=True),
        patch.object(settings, "CACHE_ENABLED", False),
        patch.object(settings, "SEMANTIC_CACHE_ENABLED", True),
        patch.object(settings, "SEMANTIC_CACHE_SIMILARITY_THRESHOLD", 0.95),
        patch.object(settings, "SEMANTIC_CACHE_EMBEDDING_MODEL", "text-embedding-3-small"),
        patch("litellm.aembedding", new_callable=AsyncMock) as mock_emb,
    ):
        mock_emb.return_value = MagicMock(data=[MagicMock(embedding=embedding)])
        result, tier = await cache_service.get(
            mock_redis,
            "openai/gpt-4",
            [{"role": "user", "content": "what is 2+2?"}],
            0.7,
            org_id=org_id,
            db=mock_db,
        )
        assert result == cached_body
        assert tier == "hit:semantic"


@pytest.mark.asyncio
async def test_l3_returns_none_when_no_matching_rows(mock_redis, org_id):
    """L3 returns (None, None) when no rows match (expired or no similar)."""
    embedding = [0.1] * 1536
    mock_db = AsyncMock(spec=AsyncSession)

    async def mock_execute(stmt):
        result = MagicMock()
        result.one_or_none = lambda: None
        return result

    mock_db.execute = AsyncMock(side_effect=mock_execute)
    with (
        patch.object(cache_service, "is_enabled", return_value=True),
        patch.object(settings, "CACHE_ENABLED", False),
        patch.object(settings, "SEMANTIC_CACHE_ENABLED", True),
        patch("litellm.aembedding", new_callable=AsyncMock) as mock_emb,
    ):
        mock_emb.return_value = MagicMock(data=[MagicMock(embedding=embedding)])
        result, tier = await cache_service.get(
            mock_redis,
            "openai/gpt-4",
            [{"role": "user", "content": "no-match-query"}],
            None,
            org_id=org_id,
            db=mock_db,
        )
        assert result is None
        assert tier is None


@pytest.mark.asyncio
async def test_l3_miss_when_similarity_below_threshold(mock_redis, org_id):
    """L3 returns None when best match similarity < threshold."""
    embedding = [0.1] * 1536
    mock_db = AsyncMock(spec=AsyncSession)

    async def mock_execute(stmt):
        class Row:
            def one_or_none(self):
                entry = MagicMock()
                entry.response_json = {}
                entry.token_count = 0
                entry.embedding = MagicMock()
                entry.embedding.cosine_distance = MagicMock(return_value=0.5)
                return (entry, 0.5)

        result = MagicMock()
        result.one_or_none = Row().one_or_none
        return result

    mock_db.execute = AsyncMock(side_effect=mock_execute)

    with (
        patch.object(cache_service, "is_enabled", return_value=True),
        patch.object(settings, "CACHE_ENABLED", False),
        patch.object(settings, "SEMANTIC_CACHE_ENABLED", True),
        patch.object(settings, "SEMANTIC_CACHE_SIMILARITY_THRESHOLD", 0.95),
        patch("litellm.aembedding", new_callable=AsyncMock) as mock_emb,
    ):
        mock_emb.return_value = MagicMock(data=[MagicMock(embedding=embedding)])
        result, tier = await cache_service.get(
            mock_redis,
            "openai/gpt-4",
            [{"role": "user", "content": "hi"}],
            None,
            org_id=org_id,
            db=mock_db,
        )
        assert result is None
        assert tier is None


# ── x-openproxy-cache: skip ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_skip_bypasses_cache(mock_redis, org_id):
    """x-openproxy-cache: skip bypasses cache entirely."""
    mock_redis.get = AsyncMock(return_value=json.dumps({"cached": True}))
    with (
        patch.object(cache_service, "is_enabled", return_value=True),
        patch.object(settings, "CACHE_ENABLED", True),
    ):
        result, tier = await cache_service.get(
            mock_redis,
            "gpt-4",
            [{"role": "user", "content": "hi"}],
            0.7,
            org_id=org_id,
            cache_override="skip",
        )
        assert result is None
        assert tier is None
        mock_redis.get.assert_not_called()


# ── Cache write stores in layers ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_cache_write_stores_in_l2_when_enabled(mock_redis):
    """set() writes to L2 Redis when CACHE_ENABLED."""
    body = {"choices": [{"message": {"content": "ok"}}], "usage": {"total_tokens": 10}}
    with (
        patch.object(cache_service, "is_enabled", return_value=True),
        patch.object(settings, "CACHE_ENABLED", True),
        patch.object(settings, "SEMANTIC_CACHE_ENABLED", False),
    ):
        await cache_service.set(mock_redis, "gpt-4", [{"role": "user", "content": "hi"}], 0.7, body)
        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args
        assert call_args[0][0].startswith("cache:")
        assert json.loads(call_args[0][2]) == body


@pytest.mark.asyncio
async def test_no_store_skips_cache_write(mock_redis, org_id):
    """cache_override=no-store skips set() — no Redis write."""
    with (
        patch.object(cache_service, "is_enabled", return_value=True),
        patch.object(settings, "CACHE_ENABLED", True),
    ):
        await cache_service.set(
            mock_redis,
            "gpt-4",
            [{"role": "user", "content": "hi"}],
            0.7,
            {"data": "x"},
            org_id=org_id,
            cache_override="no-store",
        )
        mock_redis.setex.assert_not_called()


# ── Embedding failure swallowed ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_embedding_failure_swallowed(mock_redis, org_id):
    """L3 embedding failure returns (None, None), does not propagate."""
    mock_db = AsyncMock(spec=AsyncSession)
    # Use unique messages so we don't hit L1 from a previous test
    messages = [{"role": "user", "content": "unique-embedding-fail-query-xyz"}]
    with (
        patch.object(cache_service, "is_enabled", return_value=True),
        patch.object(settings, "CACHE_ENABLED", False),
        patch.object(settings, "SEMANTIC_CACHE_ENABLED", True),
        patch("litellm.aembedding", new_callable=AsyncMock) as mock_emb,
    ):
        mock_emb.side_effect = RuntimeError("embedding API down")
        result, tier = await cache_service.get(
            mock_redis,
            "gpt-4",
            messages,
            0.9,
            org_id=org_id,
            db=mock_db,
        )
        assert result is None
        assert tier is None


# ── Cache metrics ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cache_metrics_incremented_on_exact_hit(mock_redis, org_id):
    """Exact hit increments cache:hits:exact and cache:tokens_saved."""
    cached = {"choices": [], "usage": {"total_tokens": 42}}
    mock_redis.get = AsyncMock(return_value=json.dumps(cached))
    with (
        patch.object(cache_service, "is_enabled", return_value=True),
        patch.object(settings, "CACHE_ENABLED", True),
        patch.object(settings, "SEMANTIC_CACHE_ENABLED", False),
    ):
        await cache_service.get(
            mock_redis,
            "gpt-4",
            [{"role": "user", "content": "hi"}],
            0.7,
            org_id=org_id,
        )
        await asyncio.sleep(0.1)
    mock_redis.incr.assert_called()
    mock_redis.incrby.assert_called()
    incr_calls = [c[0][0] for c in mock_redis.incr.call_args_list]
    assert any("cache:hits:exact" in k for k in incr_calls)
    incrby_calls = [c[0][0] for c in mock_redis.incrby.call_args_list]
    assert any("cache:tokens_saved" in k for k in incrby_calls)


@pytest.mark.asyncio
async def test_cache_miss_increments_misses(mock_redis, org_id):
    """Miss increments cache:misses."""
    mock_redis.get = AsyncMock(return_value=None)
    with (
        patch.object(cache_service, "is_enabled", return_value=True),
        patch.object(settings, "CACHE_ENABLED", True),
        patch.object(settings, "SEMANTIC_CACHE_ENABLED", False),
    ):
        await cache_service.get(
            mock_redis,
            "gpt-4",
            [{"role": "user", "content": "hi"}],
            0.7,
            org_id=org_id,
        )
        await asyncio.sleep(0.1)
    mock_redis.incr.assert_called()
    incr_calls = [c[0][0] for c in mock_redis.incr.call_args_list]
    assert any("cache:misses" in k for k in incr_calls)


# ── Different orgs don't share cache ───────────────────────────────────────


@pytest.mark.asyncio
async def test_different_orgs_use_different_metric_keys(mock_redis):
    """Metrics are scoped by org_id."""
    org_a = uuid.uuid4()
    org_b = uuid.uuid4()
    mock_redis.get = AsyncMock(return_value=None)
    with (
        patch.object(cache_service, "is_enabled", return_value=True),
        patch.object(settings, "CACHE_ENABLED", True),
        patch.object(settings, "SEMANTIC_CACHE_ENABLED", False),
    ):
        await cache_service.get(mock_redis, "gpt-4", [{"role": "user", "content": "a"}], 0.7, org_id=org_a)
        await cache_service.get(mock_redis, "gpt-4", [{"role": "user", "content": "b"}], 0.7, org_id=org_b)
        await asyncio.sleep(0.2)
    incr_calls = [c[0][0] for c in mock_redis.incr.call_args_list]
    keys_with_a = [k for k in incr_calls if str(org_a) in k]
    keys_with_b = [k for k in incr_calls if str(org_b) in k]
    assert keys_with_a
    assert keys_with_b
    assert keys_with_a != keys_with_b
