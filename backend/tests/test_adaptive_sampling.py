"""Tests for adaptive load balancing sampling and metrics."""

from uuid import uuid4

import pytest

from app.services.adaptive_sampling_service import (
    get_error_rate,
    get_latency_p99,
    run_adaptive_sampling,
)


class FakeRedisForAdaptive:
    """Redis mock with get/setex/pipeline for adaptive sampling."""

    def __init__(self):
        self._store = {}

    async def get(self, key):
        return self._store.get(key)

    async def setex(self, key, ttl, value):
        self._store[key] = value

    def pipeline(self):
        return _FakePipeline(self._store)

    async def aclose(self):
        pass


class _FakePipeline:
    def __init__(self, store):
        self._store = store
        self._ops = []

    def setex(self, key, ttl, value):
        self._ops.append(("setex", key, value))
        return self

    async def execute(self):
        for op in self._ops:
            self._store[op[1]] = op[2]


class FakeDBForSampling:
    """Session that returns mock aggregate rows for run_adaptive_sampling."""

    def __init__(self, rows=None):
        self._rows = rows or []

    async def execute(self, stmt, params=None):
        rows = self._rows

        class MockResult:
            def mappings(self):
                return self

            def all(self):
                return rows

        return MockResult()


@pytest.fixture
def fake_adaptive_redis():
    return FakeRedisForAdaptive()


@pytest.mark.asyncio
async def test_run_adaptive_sampling_empty_db(fake_adaptive_redis):
    """Empty result -> no keys updated."""
    fake_db = FakeDBForSampling(rows=[])
    count = await run_adaptive_sampling(fake_adaptive_redis, fake_db)
    assert count == 0


@pytest.mark.asyncio
async def test_get_latency_p99_missing(fake_adaptive_redis):
    """Missing key returns None."""
    key_id = uuid4()
    val = await get_latency_p99(fake_adaptive_redis, key_id)
    assert val is None


@pytest.mark.asyncio
async def test_get_error_rate_missing(fake_adaptive_redis):
    """Missing key returns None."""
    key_id = uuid4()
    val = await get_error_rate(fake_adaptive_redis, key_id)
    assert val is None


@pytest.mark.asyncio
async def test_run_adaptive_sampling_writes_to_redis(fake_adaptive_redis):
    """run_adaptive_sampling with mock rows writes p99 and error_rate to Redis."""
    key_id = uuid4()
    rows = [
        {
            "provider_key_id": key_id,
            "p99": 250.5,
            "total": 10,
            "errors": 2,
        },
    ]
    fake_db = FakeDBForSampling(rows=rows)
    count = await run_adaptive_sampling(fake_adaptive_redis, fake_db)
    assert count == 1
    p99 = await get_latency_p99(fake_adaptive_redis, key_id)
    err = await get_error_rate(fake_adaptive_redis, key_id)
    assert p99 == 250.5
    assert err == 0.2
