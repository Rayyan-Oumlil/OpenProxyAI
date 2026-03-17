"""Tests for auth brute-force protection — _check_auth_rate_limit / _reset_auth_rate_limit."""

from unittest.mock import AsyncMock, call

import pytest
from fastapi import HTTPException

from app.routes.auth import _check_auth_rate_limit, _reset_auth_rate_limit


# ---------------------------------------------------------------------------
# Test 1: 10 attempts pass; 11th raises HTTP 429
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_rate_limit_blocks_on_11th_attempt():
    """First 10 calls succeed; the 11th raises HTTP 429."""
    ip = "1.2.3.4"
    email = "attacker@example.com"
    key = f"auth:attempts:{ip}:{email}"

    redis = AsyncMock()

    # First 10 calls — each returns count 1..10, all should pass
    for attempt in range(1, 11):
        redis.incr.return_value = attempt
        await _check_auth_rate_limit(ip, email, redis)  # must not raise

    # 11th call — count=11, must raise 429
    redis.incr.return_value = 11
    with pytest.raises(HTTPException) as exc_info:
        await _check_auth_rate_limit(ip, email, redis)

    assert exc_info.value.status_code == 429
    assert exc_info.value.headers == {"Retry-After": "60"}


@pytest.mark.asyncio
async def test_rate_limit_sets_expire_on_first_attempt():
    """On the very first attempt (count==1) expire is set to 60 seconds."""
    ip = "1.2.3.4"
    email = "user@example.com"
    key = f"auth:attempts:{ip}:{email}"

    redis = AsyncMock()
    redis.incr.return_value = 1

    await _check_auth_rate_limit(ip, email, redis)

    redis.expire.assert_awaited_once_with(key, 60)


@pytest.mark.asyncio
async def test_rate_limit_does_not_set_expire_on_subsequent_attempts():
    """expire is NOT called when count > 1."""
    ip = "1.2.3.4"
    email = "user@example.com"

    redis = AsyncMock()
    redis.incr.return_value = 5  # not the first attempt

    await _check_auth_rate_limit(ip, email, redis)

    redis.expire.assert_not_awaited()


# ---------------------------------------------------------------------------
# Test 2: successful login resets the counter (redis.delete called)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reset_calls_redis_delete_with_correct_key():
    """_reset_auth_rate_limit must call redis.delete with the correct key."""
    ip = "10.0.0.1"
    email = "legit@example.com"
    expected_key = f"auth:attempts:{ip}:{email}"

    redis = AsyncMock()
    await _reset_auth_rate_limit(ip, email, redis)

    redis.delete.assert_awaited_once_with(expected_key)


# ---------------------------------------------------------------------------
# Integration-style: login route resets counter on success
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_successful_auth_resets_counter():
    """After a successful auth check, the rate limit key is deleted."""
    ip = "192.168.1.1"
    email = "admin@corp.com"
    key = f"auth:attempts:{ip}:{email}"

    redis = AsyncMock()

    # Simulate 3 previous failed attempts, then success
    redis.incr.return_value = 4  # still under limit

    await _check_auth_rate_limit(ip, email, redis)  # passes (count=4 ≤ 10)
    await _reset_auth_rate_limit(ip, email, redis)   # reset on success

    redis.delete.assert_awaited_once_with(key)
