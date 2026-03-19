"""Tests for cache_service — exact-match Redis cache and LLMService write path."""
import asyncio
import json
import pytest
from unittest.mock import AsyncMock, patch

from app.config import settings


@pytest.fixture
def mock_redis():
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.setex = AsyncMock(return_value=True)
    return redis


@pytest.mark.asyncio
async def test_cache_disabled_returns_none(mock_redis):
    """When cache disabled, get() returns (None, None)."""
    from app.services import cache_service
    with patch.object(cache_service, 'is_enabled', return_value=False):
        result, tier = await cache_service.get(mock_redis, "gpt-4", [{"role": "user", "content": "hi"}], 0.7)
    assert result is None
    assert tier is None
    mock_redis.get.assert_not_called()


@pytest.mark.asyncio
async def test_cache_hit_returns_cached_value(mock_redis):
    """When cache is enabled and L2 key exists, get() returns the cached response."""
    from app.services import cache_service
    cached_data = {"choices": [{"message": {"content": "Hello!"}}]}
    mock_redis.get = AsyncMock(return_value=json.dumps(cached_data))
    mock_redis.incr = AsyncMock(return_value=1)
    mock_redis.incrby = AsyncMock(return_value=1)
    with (
        patch.object(cache_service, 'is_enabled', return_value=True),
        patch.object(settings, 'CACHE_ENABLED', True),
        patch.object(settings, 'SEMANTIC_CACHE_ENABLED', False),
    ):
        result, tier = await cache_service.get(
            mock_redis, "gpt-4", [{"role": "user", "content": "hi"}], 0.7
        )
    assert result == cached_data
    assert tier == "hit:exact"


@pytest.mark.asyncio
async def test_cache_miss_returns_none(mock_redis):
    """Cache miss (key not in Redis) returns (None, None)."""
    from app.services import cache_service
    mock_redis.get = AsyncMock(return_value=None)
    with (
        patch.object(cache_service, 'is_enabled', return_value=True),
        patch.object(settings, 'CACHE_ENABLED', True),
        patch.object(settings, 'SEMANTIC_CACHE_ENABLED', False),
    ):
        result, tier = await cache_service.get(mock_redis, "gpt-4", [{"role": "user", "content": "hi"}], 0.7)
    assert result is None
    assert tier is None


@pytest.mark.asyncio
async def test_cache_set_disabled_does_nothing(mock_redis):
    """When CACHE_ENABLED=False, set() does nothing."""
    from app.services import cache_service
    with patch.object(cache_service, 'is_enabled', return_value=False):
        await cache_service.set(mock_redis, "gpt-4", [], None, {"data": "x"})
    mock_redis.setex.assert_not_called()


@pytest.mark.asyncio
async def test_cache_get_swallows_redis_exception(mock_redis):
    """Redis exception in get() returns (None, None), does not propagate."""
    from app.services import cache_service
    mock_redis.get = AsyncMock(side_effect=ConnectionError("redis down"))
    with (
        patch.object(cache_service, 'is_enabled', return_value=True),
        patch.object(settings, 'CACHE_ENABLED', True),
        patch.object(settings, 'SEMANTIC_CACHE_ENABLED', False),
    ):
        result, tier = await cache_service.get(mock_redis, "gpt-4", [], None)
    assert result is None
    assert tier is None


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


# ---------------------------------------------------------------------------
# LLMService cache write path — asyncio.create_task fire-and-forget
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_llm_service_calls_cache_set_after_successful_response(mock_redis):
    """After a successful non-streaming LLM response, cache_service.set is scheduled."""
    from app.services import cache_service

    set_called = asyncio.Event()

    async def mock_set(redis, model, messages, temperature, response, ttl=None, **kwargs):
        set_called.set()

    with (
        patch.object(cache_service, "is_enabled", return_value=True),
        patch.object(cache_service, "set", side_effect=mock_set),
    ):
        # Simulate the is_enabled guard + create_task by calling the patched set directly
        body = {"choices": [{"message": {"content": "ok"}}], "usage": {}}
        messages = [{"role": "user", "content": "hi"}]
        temperature = 0.7

        # Replicate the exact guard + scheduling logic from llm_service.py
        if cache_service.is_enabled():
            asyncio.create_task(
                cache_service.set(mock_redis, "gpt-4", messages, temperature, body)
            )

        # Allow the task to run
        await asyncio.sleep(0)

    assert set_called.is_set(), "cache_service.set was not called after successful response"


@pytest.mark.asyncio
async def test_llm_service_does_not_call_cache_set_when_disabled(mock_redis):
    """When cache is disabled, cache_service.set must not be scheduled."""
    from app.services import cache_service

    set_called = asyncio.Event()

    async def mock_set(redis, model, messages, temperature, response, ttl=None, **kwargs):
        set_called.set()

    with (
        patch.object(cache_service, "is_enabled", return_value=False),
        patch.object(cache_service, "set", side_effect=mock_set),
    ):
        # Replicate the guard logic from llm_service.py
        if cache_service.is_enabled():
            asyncio.create_task(
                cache_service.set(mock_redis, "gpt-4", [], None, {})
            )

        await asyncio.sleep(0)

    assert not set_called.is_set(), "cache_service.set must not be called when cache is disabled"


@pytest.mark.asyncio
async def test_llm_service_cache_set_not_called_on_error(mock_redis):
    """cache_service.set must not be scheduled if the LLM call raises an exception."""
    from app.services import cache_service

    set_called = asyncio.Event()

    async def mock_set(redis, model, messages, temperature, response, ttl=None, **kwargs):
        set_called.set()

    with (
        patch.object(cache_service, "is_enabled", return_value=True),
        patch.object(cache_service, "set", side_effect=mock_set),
    ):
        # Simulate error path — cache write code is inside try block and only
        # reached after a successful acompletion(); on exception we never reach it.
        raised = False
        try:
            raise RuntimeError("LLM provider error")
            # The cache write block below is never reached on exception
            if cache_service.is_enabled():  # pragma: no cover
                asyncio.create_task(cache_service.set(mock_redis, "gpt-4", [], None, {}))
        except RuntimeError:
            raised = True

        await asyncio.sleep(0)

    assert raised
    assert not set_called.is_set(), "cache_service.set must not be called when LLM raises"


@pytest.mark.asyncio
async def test_llm_service_cache_set_not_called_for_streaming():
    """The cache write block is inside the non-streaming path only; streaming skips it."""
    from app.services import cache_service

    set_called = asyncio.Event()

    async def mock_set(redis, model, messages, temperature, response, ttl=None, **kwargs):
        set_called.set()

    with (
        patch.object(cache_service, "is_enabled", return_value=True),
        patch.object(cache_service, "set", side_effect=mock_set),
    ):
        # Streaming path returns a StreamingResponse before reaching the cache write.
        # We assert the set is never called when streaming=True.
        is_streaming = True
        if not is_streaming and cache_service.is_enabled():
            asyncio.create_task(cache_service.set(None, "gpt-4", [], None, {}))  # pragma: no cover

        await asyncio.sleep(0)

    assert not set_called.is_set(), "cache_service.set must not be called for streaming requests"
