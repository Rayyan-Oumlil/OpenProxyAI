"""Unit tests for CostTrackerService — budget enforcement, spend tracking, alerts."""

import asyncio
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.cost_tracker import CostTrackerService, _today_iso


# ── Inline FakeRedis (avoids conftest import chain) ─────────────────────


class FakeRedis:
    def __init__(self):
        self._store: dict[str, str] = {}
        self._zsets: dict[str, dict[str, float]] = {}

    async def get(self, key):
        return self._store.get(key)

    async def setex(self, key, ttl, value):
        self._store[key] = value
        return True

    async def exists(self, key):
        return 1 if key in self._store else 0

    async def incrbyfloat(self, key, amount):
        current = float(self._store.get(key, "0"))
        current += amount
        self._store[key] = str(current)
        return current

    async def expire(self, key, seconds):
        return True

    async def zadd(self, key, mapping):
        zset = self._zsets.setdefault(key, {})
        added = 0
        for member, score in mapping.items():
            if member not in zset:
                added += 1
            zset[member] = float(score)
        return added

    async def set(self, key, value, ex=None, nx=False):
        if nx and key in self._store:
            return False
        self._store[key] = value
        return True

    async def zrange(self, key, start, stop, withscores=False):
        items = sorted(self._zsets.get(key, {}).items(), key=lambda x: x[1])
        if stop == -1:
            slice_items = items[start:]
        else:
            slice_items = items[start:stop + 1]
        if withscores:
            return [(m, s) for m, s in slice_items]
        return [m for m, _ in slice_items]

    async def zrangebyscore(self, key, min_score, max_score):
        zset = self._zsets.get(key, {})
        lo = float("-inf") if min_score == "-inf" else float(min_score)
        hi = float("inf") if max_score == "+inf" else float(max_score)
        return [m for m, s in sorted(zset.items(), key=lambda x: x[1]) if lo <= s <= hi]


@pytest.fixture
def fake_redis():
    return FakeRedis()


@pytest.fixture
def svc() -> CostTrackerService:
    return CostTrackerService()


# ── calculate_cost_usd ──────────────────────────────────────────────────


class TestCalculateCostUSD:
    def test_known_float_rounds_to_six_decimals(self, monkeypatch):
        monkeypatch.setattr(
            "app.services.cost_tracker.completion_cost",
            lambda completion_response: 0.00012345678,
        )
        result = CostTrackerService.calculate_cost_usd(object())
        assert result == Decimal("0.000123")
        assert isinstance(result, Decimal)

    def test_zero_cost(self, monkeypatch):
        monkeypatch.setattr(
            "app.services.cost_tracker.completion_cost",
            lambda completion_response: 0.0,
        )
        assert CostTrackerService.calculate_cost_usd(object()) == Decimal("0.000000")

    def test_half_up_rounding(self, monkeypatch):
        monkeypatch.setattr(
            "app.services.cost_tracker.completion_cost",
            lambda completion_response: 0.0000005,
        )
        result = CostTrackerService.calculate_cost_usd(object())
        assert result == Decimal("0.000001")


# ── get_org_spend_today / get_user_spend_today ──────────────────────────


class TestGetSpendToday:
    @pytest.mark.asyncio
    async def test_org_spend_returns_decimal_from_redis(self, fake_redis, svc):
        key = f"rl:usd:org-1:{_today_iso()}"
        fake_redis._store[key] = "1.234567"

        result = await svc.get_org_spend_today(fake_redis, "org-1")
        assert result == Decimal("1.234567")
        assert isinstance(result, Decimal)

    @pytest.mark.asyncio
    async def test_org_spend_returns_zero_when_missing(self, fake_redis, svc):
        result = await svc.get_org_spend_today(fake_redis, "org-no-key")
        assert result == Decimal("0")

    @pytest.mark.asyncio
    async def test_user_spend_returns_decimal_from_redis(self, fake_redis, svc):
        key = f"rl:usd:user:user-42:{_today_iso()}"
        fake_redis._store[key] = "9.876543"

        result = await svc.get_user_spend_today(fake_redis, "user-42")
        assert result == Decimal("9.876543")

    @pytest.mark.asyncio
    async def test_user_spend_returns_zero_when_missing(self, fake_redis, svc):
        result = await svc.get_user_spend_today(fake_redis, "user-absent")
        assert result == Decimal("0")


# ── check_user_budget ───────────────────────────────────────────────────


class TestCheckUserBudget:
    @pytest.mark.asyncio
    async def test_under_budget_returns_true(self, fake_redis, svc):
        key = f"rl:usd:user:u1:{_today_iso()}"
        fake_redis._store[key] = "5.0"

        result = await svc.check_user_budget(fake_redis, "u1", Decimal("10.0"))
        assert result is True

    @pytest.mark.asyncio
    async def test_over_budget_returns_false(self, fake_redis, svc):
        key = f"rl:usd:user:u1:{_today_iso()}"
        fake_redis._store[key] = "15.0"

        result = await svc.check_user_budget(fake_redis, "u1", Decimal("10.0"))
        assert result is False

    @pytest.mark.asyncio
    async def test_exactly_at_budget_returns_false(self, fake_redis, svc):
        key = f"rl:usd:user:u1:{_today_iso()}"
        fake_redis._store[key] = "10.0"

        result = await svc.check_user_budget(fake_redis, "u1", Decimal("10.0"))
        assert result is False

    @pytest.mark.asyncio
    async def test_none_budget_always_returns_true(self, fake_redis, svc):
        key = f"rl:usd:user:u1:{_today_iso()}"
        fake_redis._store[key] = "99999.0"

        result = await svc.check_user_budget(fake_redis, "u1", None)
        assert result is True


# ── alert_at_threshold ──────────────────────────────────────────────────


class TestAlertAtThreshold:
    @pytest.fixture(autouse=True)
    def _patch_create_task(self, monkeypatch):
        monkeypatch.setattr(asyncio, "create_task", lambda coro: coro.close())

    @pytest.mark.asyncio
    async def test_below_threshold_returns_false(self, fake_redis, svc):
        result = await svc.alert_at_threshold(
            fake_redis, "org-1", Decimal("3.0"), Decimal("10.0"), threshold=0.8
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_above_threshold_first_call_returns_true(self, fake_redis, svc):
        result = await svc.alert_at_threshold(
            fake_redis, "org-1", Decimal("9.0"), Decimal("10.0"), threshold=0.8
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_above_threshold_second_call_returns_false(self, fake_redis, svc):
        await svc.alert_at_threshold(
            fake_redis, "org-1", Decimal("9.0"), Decimal("10.0"), threshold=0.8
        )
        result = await svc.alert_at_threshold(
            fake_redis, "org-1", Decimal("9.5"), Decimal("10.0"), threshold=0.8
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_zero_budget_returns_false(self, fake_redis, svc):
        result = await svc.alert_at_threshold(
            fake_redis, "org-1", Decimal("5.0"), Decimal("0"), threshold=0.8
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_negative_budget_returns_false(self, fake_redis, svc):
        result = await svc.alert_at_threshold(
            fake_redis, "org-1", Decimal("5.0"), Decimal("-1.0"), threshold=0.8
        )
        assert result is False


# ── check_anomaly ───────────────────────────────────────────────────────


class TestCheckAnomaly:
    @pytest.mark.asyncio
    async def test_no_baseline_does_not_raise(self, fake_redis, svc, monkeypatch):
        monkeypatch.setattr(
            "app.config.settings.COST_ANOMALY_MIN_BASELINE_DAYS", 3,
        )
        monkeypatch.setattr(
            "app.config.settings.COST_ANOMALY_MULTIPLIER", 3.0,
        )
        db_session = AsyncMock()
        org = MagicMock()
        await svc.check_anomaly(fake_redis, "org-1", "user-1", db_session, org)

    @pytest.mark.asyncio
    async def test_swallows_exceptions(self, fake_redis, svc, monkeypatch):
        monkeypatch.setattr(
            "app.config.settings.COST_ANOMALY_MIN_BASELINE_DAYS", 3,
        )
        monkeypatch.setattr(
            "app.config.settings.COST_ANOMALY_MULTIPLIER", 3.0,
        )
        broken_redis = MagicMock()
        broken_redis.get = AsyncMock(side_effect=RuntimeError("boom"))
        db_session = AsyncMock()
        org = MagicMock()
        await svc.check_anomaly(broken_redis, "org-1", None, db_session, org)
