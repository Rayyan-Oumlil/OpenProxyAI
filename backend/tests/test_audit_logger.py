"""Unit tests for audit_logger.log_request — heavily mocked to isolate from DB/services."""

import asyncio
import uuid
from contextlib import asynccontextmanager
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.audit_logger import log_request


# ── Inline FakeRedis (avoids conftest import chain) ─────────────────────


class FakeRedis:
    def __init__(self):
        self._store: dict[str, str] = {}

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


@pytest.fixture
def fake_redis():
    return FakeRedis()


@pytest.fixture
def ids():
    return {
        "request_id": uuid.uuid4(),
        "org_id": uuid.uuid4(),
        "user_id": uuid.uuid4(),
        "api_key_id": uuid.uuid4(),
    }


@pytest.fixture
def _mock_db(monkeypatch):
    """Replace AsyncSessionLocal with an in-memory mock session."""
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    @asynccontextmanager
    async def fake_session_local():
        yield mock_session

    monkeypatch.setattr("app.services.audit_logger.AsyncSessionLocal", fake_session_local)
    return mock_session


@pytest.fixture(autouse=True)
def _isolate_side_effects(monkeypatch):
    """Disable all fire-and-forget tasks and optional integrations."""
    monkeypatch.setattr(asyncio, "create_task", lambda coro: coro.close())

    mock_alert = AsyncMock(return_value=False)
    monkeypatch.setattr(
        "app.services.audit_logger.cost_tracker_service.alert_at_threshold", mock_alert
    )

    langfuse = MagicMock()
    langfuse.is_enabled = MagicMock(return_value=False)
    monkeypatch.setattr("app.services.audit_logger.langfuse_service", langfuse, raising=False)

    clickhouse = MagicMock()
    clickhouse.is_enabled = MagicMock(return_value=False)
    monkeypatch.setattr("app.services.audit_logger.clickhouse_service", clickhouse, raising=False)

    monkeypatch.setattr("app.services.audit_logger.settings.PROMETHEUS_ENABLED", False)


# ── basic successful log ────────────────────────────────────────────────


class TestBasicLog:
    @pytest.mark.asyncio
    async def test_redis_spend_keys_incremented(self, fake_redis, ids, _mock_db):
        await log_request(
            redis=fake_redis,
            request_id=ids["request_id"],
            org_id=ids["org_id"],
            user_id=ids["user_id"],
            api_key_id=ids["api_key_id"],
            model="openai/gpt-4",
            provider="openai",
            prompt_tokens=100,
            completion_tokens=50,
            cost_usd=Decimal("0.005000"),
            latency_ms=320,
            ttft_ms=120,
            status_code=200,
        )

        from app.services.cost_tracker import _today_iso

        today = _today_iso()
        org_key = f"rl:usd:{ids['org_id']}:{today}"
        user_key = f"rl:usd:user:{ids['user_id']}:{today}"

        org_val = await fake_redis.get(org_key)
        user_val = await fake_redis.get(user_key)
        assert float(org_val) == pytest.approx(0.005, abs=1e-6)
        assert float(user_val) == pytest.approx(0.005, abs=1e-6)

    @pytest.mark.asyncio
    async def test_db_row_added(self, fake_redis, ids, _mock_db):
        await log_request(
            redis=fake_redis,
            request_id=ids["request_id"],
            org_id=ids["org_id"],
            user_id=ids["user_id"],
            api_key_id=ids["api_key_id"],
            model="openai/gpt-4",
            provider="openai",
            prompt_tokens=10,
            completion_tokens=5,
            cost_usd=Decimal("0.001000"),
            latency_ms=100,
            ttft_ms=None,
            status_code=200,
        )
        _mock_db.add.assert_called_once()
        _mock_db.commit.assert_awaited_once()


# ── labels ──────────────────────────────────────────────────────────────


class TestLabels:
    @pytest.mark.asyncio
    async def test_labels_merged_into_metadata(self, fake_redis, ids, _mock_db):
        await log_request(
            redis=fake_redis,
            request_id=ids["request_id"],
            org_id=ids["org_id"],
            user_id=ids["user_id"],
            api_key_id=ids["api_key_id"],
            model="openai/gpt-4",
            provider="openai",
            prompt_tokens=10,
            completion_tokens=5,
            cost_usd=Decimal("0.001000"),
            latency_ms=100,
            ttft_ms=None,
            status_code=200,
            labels={"env": "staging", "team": "ml"},
        )
        row = _mock_db.add.call_args[0][0]
        assert row.request_metadata["labels"] == {"env": "staging", "team": "ml"}


# ── policy block ────────────────────────────────────────────────────────


class TestPolicyBlock:
    @pytest.mark.asyncio
    async def test_policy_block_fires_webhook_path(self, fake_redis, ids, _mock_db, monkeypatch):
        """When status_code=403 and policy.action='block', the webhook code path is reached."""
        created_tasks = []
        monkeypatch.setattr(asyncio, "create_task", lambda coro: (created_tasks.append(coro), coro.close()))

        await log_request(
            redis=fake_redis,
            request_id=ids["request_id"],
            org_id=ids["org_id"],
            user_id=ids["user_id"],
            api_key_id=ids["api_key_id"],
            model="openai/gpt-4",
            provider="openai",
            prompt_tokens=0,
            completion_tokens=0,
            cost_usd=Decimal("0"),
            latency_ms=5,
            ttft_ms=None,
            status_code=403,
            request_metadata={"policy": {"action": "block", "reason_code": "blocked_model"}},
        )
        assert len(created_tasks) >= 1


# ── error message ───────────────────────────────────────────────────────


class TestErrorMessage:
    @pytest.mark.asyncio
    async def test_error_message_stored_in_row(self, fake_redis, ids, _mock_db):
        await log_request(
            redis=fake_redis,
            request_id=ids["request_id"],
            org_id=ids["org_id"],
            user_id=ids["user_id"],
            api_key_id=ids["api_key_id"],
            model="openai/gpt-4",
            provider="openai",
            prompt_tokens=0,
            completion_tokens=0,
            cost_usd=Decimal("0"),
            latency_ms=10,
            ttft_ms=None,
            status_code=502,
            error_message="provider_error: connection refused",
        )
        row = _mock_db.add.call_args[0][0]
        assert row.error_message == "provider_error: connection refused"
        assert row.status_code == 502
