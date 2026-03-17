"""Tests for cache_service — exact-match Redis cache."""
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.fixture
def mock_redis():
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.setex = AsyncMock(return_value=True)
    return redis


@pytest.mark.asyncio
async def test_cache_disabled_returns_none(mock_redis):
    """When CACHE_ENABLED=False, get() always returns None."""
    from app.services import cache_service
    with patch.object(cache_service, 'is_enabled', return_value=False):
        result = await cache_service.get(mock_redis, "gpt-4", [{"role": "user", "content": "hi"}], 0.7)
    assert result is None
    mock_redis.get.assert_not_called()


@pytest.mark.asyncio
async def test_cache_hit_returns_cached_value(mock_redis):
    """When cache is enabled and key exists, get() returns the cached response."""
    from app.services import cache_service
    cached_data = {"choices": [{"message": {"content": "Hello!"}}]}
    mock_redis.get = AsyncMock(return_value=json.dumps(cached_data).encode())
    with patch.object(cache_service, 'is_enabled', return_value=True):
        result = await cache_service.get(mock_redis, "gpt-4", [{"role": "user", "content": "hi"}], 0.7)
    assert result == cached_data


@pytest.mark.asyncio
async def test_cache_miss_returns_none(mock_redis):
    """Cache miss (key not in Redis) returns None."""
    from app.services import cache_service
    mock_redis.get = AsyncMock(return_value=None)
    with patch.object(cache_service, 'is_enabled', return_value=True):
        result = await cache_service.get(mock_redis, "gpt-4", [{"role": "user", "content": "hi"}], 0.7)
    assert result is None


@pytest.mark.asyncio
async def test_cache_set_disabled_does_nothing(mock_redis):
    """When CACHE_ENABLED=False, set() does nothing."""
    from app.services import cache_service
    with patch.object(cache_service, 'is_enabled', return_value=False):
        await cache_service.set(mock_redis, "gpt-4", [], None, {"data": "x"})
    mock_redis.setex.assert_not_called()


@pytest.mark.asyncio
async def test_cache_get_swallows_redis_exception(mock_redis):
    """Redis exception in get() returns None, does not propagate."""
    from app.services import cache_service
    mock_redis.get = AsyncMock(side_effect=ConnectionError("redis down"))
    with patch.object(cache_service, 'is_enabled', return_value=True):
        result = await cache_service.get(mock_redis, "gpt-4", [], None)
    assert result is None


@pytest.mark.asyncio
async def test_same_request_produces_same_cache_key(mock_redis):
    """Same model+messages+temperature always hits the same cache key."""
    from app.services import cache_service
    messages = [{"role": "user", "content": "hello"}]
    key1 = cache_service._make_key("gpt-4", messages, 0.0)
    key2 = cache_service._make_key("gpt-4", messages, 0.0)
    assert key1 == key2


def test_different_requests_produce_different_cache_keys():
    """Different inputs produce different cache keys."""
    from app.services import cache_service
    key1 = cache_service._make_key("gpt-4", [{"role": "user", "content": "hello"}], 0.0)
    key2 = cache_service._make_key("gpt-4", [{"role": "user", "content": "world"}], 0.0)
    assert key1 != key2
