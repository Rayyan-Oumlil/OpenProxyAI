"""Circuit breaker service tests."""

import time
from uuid import uuid4

import pytest

from app.services.circuit_breaker_service import (
    get_open_until,
    is_circuit_open,
    record_failure,
    record_success,
)


@pytest.fixture
def key_id():
    return uuid4()


@pytest.mark.asyncio
async def test_is_circuit_open_returns_false_when_no_redis():
    """is_circuit_open returns False when redis is None."""
    result = await is_circuit_open(None, uuid4())
    assert result is False


@pytest.mark.asyncio
async def test_is_circuit_open_returns_false_when_key_id_none(fake_redis):
    """is_circuit_open returns False when key_id is None."""
    result = await is_circuit_open(fake_redis, None)
    assert result is False


@pytest.mark.asyncio
async def test_record_success_resets_failures(fake_redis, key_id, monkeypatch):
    """record_success clears failure count."""
    monkeypatch.setattr("app.services.circuit_breaker_service.is_enabled", lambda: True)
    monkeypatch.setattr("app.services.circuit_breaker_service._threshold", lambda: 3)
    await record_failure(fake_redis, key_id)
    await record_failure(fake_redis, key_id)
    await record_success(fake_redis, key_id)
    # After success, failures should be cleared; next failure starts at 1
    await record_failure(fake_redis, key_id)
    from app.services.circuit_breaker_service import _key_failures

    count_raw = await fake_redis.get(_key_failures(key_id))
    assert count_raw is not None
    assert int(count_raw) == 1


@pytest.mark.asyncio
async def test_record_failure_opens_circuit_at_threshold(fake_redis, key_id, monkeypatch):
    """After N failures, circuit opens (open_until set)."""
    monkeypatch.setattr("app.services.circuit_breaker_service.is_enabled", lambda: True)
    monkeypatch.setattr("app.services.circuit_breaker_service._threshold", lambda: 3)
    monkeypatch.setattr("app.services.circuit_breaker_service._cooldown_seconds", lambda: 60)

    await record_failure(fake_redis, key_id)
    await record_failure(fake_redis, key_id)
    assert await is_circuit_open(fake_redis, key_id) is False

    await record_failure(fake_redis, key_id)
    assert await is_circuit_open(fake_redis, key_id) is True

    open_until = await get_open_until(fake_redis, key_id)
    assert open_until is not None
    assert open_until > time.time()


@pytest.mark.asyncio
async def test_select_provider_keys_filters_open_circuits(fake_redis, monkeypatch):
    """When circuit breaker enabled and all keys open, _select_provider_keys raises 503."""
    from app.config import settings as app_settings
    from app.services.crypto_service import encrypt
    from app.services.llm_service import LLMService
    from tests.test_data_residency import DataResidencyFakeDB, FakeKey, FakeOrg

    new_settings = app_settings.model_copy(
        update={"CIRCUIT_BREAKER_ENABLED": True, "CIRCUIT_BREAKER_COOLDOWN_SECONDS": 60},
    )
    monkeypatch.setattr("app.services.llm_service.settings", new_settings)

    org_id = uuid4()
    org = FakeOrg(org_id, data_region="us")
    k1 = FakeKey(org_id, "openai", "key1", encrypt("sk-key-1"), region="us")
    db = DataResidencyFakeDB(org, keys=[k1])

    async def mock_is_open(redis, key_id):
        return key_id == k1.id  # Circuit open for our only key

    monkeypatch.setattr(
        "app.services.llm_service.is_circuit_open",
        mock_is_open,
    )

    svc = LLMService()
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        await svc._select_provider_keys(db, org_id, "openai", model=None, redis=fake_redis)
    assert exc_info.value.status_code == 503
    assert "Retry-After" in exc_info.value.headers
