"""Tests for clickhouse_service — dual-write analytics."""
import pytest
from unittest.mock import MagicMock, patch


def test_is_enabled_returns_false_when_url_not_set():
    """is_enabled() returns False when CLICKHOUSE_URL is empty."""
    import app.services.clickhouse_service as cs
    # Reset singleton state
    cs._initialized = False
    cs._client = None
    with patch("app.config.settings") as mock_settings:
        mock_settings.CLICKHOUSE_URL = ""
        result = cs.is_enabled()
    cs._initialized = False
    cs._client = None
    assert result is False


def test_is_enabled_returns_false_when_package_missing():
    """is_enabled() returns False when clickhouse-connect is not installed."""
    import sys
    import app.services.clickhouse_service as cs
    cs._initialized = False
    cs._client = None
    with patch.dict(sys.modules, {"clickhouse_connect": None}):
        with patch("app.config.settings") as mock_settings:
            mock_settings.CLICKHOUSE_URL = "clickhouse://localhost:8123"
            result = cs.is_enabled()
    cs._initialized = False
    cs._client = None
    assert result is False


@pytest.mark.asyncio
async def test_write_log_calls_client_insert():
    """write_log() calls client.insert with the correct table and data."""
    import app.services.clickhouse_service as cs
    from datetime import UTC, datetime

    mock_client = MagicMock()
    mock_client.insert = MagicMock(return_value=None)

    cs._initialized = True
    cs._client = mock_client

    with patch("app.config.settings") as mock_settings:
        mock_settings.CLICKHOUSE_DATABASE = "openproxy"
        await cs.write_log({
            "request_id": "abc-123",
            "org_id": "org-1",
            "user_id": "user-1",
            "api_key_id": "key-1",
            "model": "gpt-4o",
            "provider": "openai",
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
            "cost_usd": 0.001,
            "latency_ms": 500,
            "ttft_ms": 100,
            "status_code": 200,
            "policy_action": "allow",
            "created_at": datetime.now(UTC),
        })

    mock_client.insert.assert_called_once()
    call_args = mock_client.insert.call_args
    assert "request_logs_ch" in call_args[0][0]

    # Reset
    cs._initialized = False
    cs._client = None


@pytest.mark.asyncio
async def test_write_log_swallows_exception():
    """Exception in write_log() does not propagate."""
    import app.services.clickhouse_service as cs

    mock_client = MagicMock()
    mock_client.insert = MagicMock(side_effect=ConnectionError("CH down"))

    cs._initialized = True
    cs._client = mock_client

    with patch("app.config.settings") as mock_settings:
        mock_settings.CLICKHOUSE_DATABASE = "openproxy"
        # Must not raise
        await cs.write_log({"request_id": "x", "model": "gpt-4o"})

    cs._initialized = False
    cs._client = None


@pytest.mark.asyncio
async def test_write_log_does_nothing_when_disabled():
    """write_log() is a no-op when ClickHouse is not enabled."""
    import app.services.clickhouse_service as cs

    cs._initialized = True
    cs._client = None  # disabled

    mock_insert = MagicMock()
    # Should not call insert at all
    await cs.write_log({"request_id": "x"})
    mock_insert.assert_not_called()

    cs._initialized = False
