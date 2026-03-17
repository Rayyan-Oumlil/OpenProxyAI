"""Tests for the retry_failed_webhooks APScheduler job in main.py."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _delivery(
    *,
    status: str = "failed",
    attempt_count: int = 1,
    minutes_since_last_attempt: int = 10,
    url: str = "https://example.com/hook",
    payload: dict | None = None,
    http_status: int | None = None,
) -> SimpleNamespace:
    """Build a fake WebhookDelivery object."""
    return SimpleNamespace(
        id=uuid4(),
        org_id=uuid4(),
        url=url,
        payload=payload or {"event": "policy.violation"},
        status=status,
        attempt_count=attempt_count,
        last_attempted_at=datetime.now(UTC) - timedelta(minutes=minutes_since_last_attempt),
        http_status=http_status,
    )


class FakeScalarResult:
    """Mimics SQLAlchemy ScalarResult.all()."""

    def __init__(self, items: list) -> None:
        self._items = items

    def all(self) -> list:
        return self._items


class FakeDB:
    """Minimal async DB session stub that ignores the query and returns preset deliveries."""

    def __init__(self, deliveries: list | None = None) -> None:
        self._deliveries = deliveries or []
        self.committed = False

    async def scalars(self, query):  # noqa: ARG002
        return FakeScalarResult(self._deliveries)

    async def commit(self) -> None:
        self.committed = True

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


def _make_http_client(status_code: int = 200, raises: Exception | None = None) -> AsyncMock:
    """Build a mock httpx.AsyncClient."""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code

    client = AsyncMock()
    if raises is not None:
        client.post = AsyncMock(side_effect=raises)
    else:
        client.post = AsyncMock(return_value=mock_resp)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retry_delivers_failed_webhook():
    """A failed delivery with attempt_count < 3 is retried and marked delivered on 2xx."""
    delivery = _delivery(attempt_count=1, minutes_since_last_attempt=10)
    db = FakeDB(deliveries=[delivery])
    http_client = _make_http_client(status_code=200)

    with (
        patch("app.main.AsyncSessionLocal", return_value=db),
        patch("httpx.AsyncClient", return_value=http_client),
    ):
        from app.main import retry_failed_webhooks
        await retry_failed_webhooks()

    assert delivery.status == "delivered"
    assert delivery.http_status == 200
    assert db.committed


@pytest.mark.asyncio
async def test_retry_increments_attempt_count_on_http_error():
    """A 5xx response increments attempt_count but does not mark as exhausted yet."""
    delivery = _delivery(attempt_count=1, minutes_since_last_attempt=10)
    db = FakeDB(deliveries=[delivery])
    http_client = _make_http_client(status_code=500)

    with (
        patch("app.main.AsyncSessionLocal", return_value=db),
        patch("httpx.AsyncClient", return_value=http_client),
    ):
        from app.main import retry_failed_webhooks
        await retry_failed_webhooks()

    assert delivery.attempt_count == 2
    assert delivery.status == "failed"  # not exhausted yet (< 3)
    assert db.committed


@pytest.mark.asyncio
async def test_retry_exhausts_after_reaching_max_attempts_http_error():
    """When attempt_count reaches 3 after a failed HTTP retry, status becomes exhausted."""
    # attempt_count=2, backoff = 5^2 * 60 = 1500s; 600 minutes >> 1500s
    delivery = _delivery(attempt_count=2, minutes_since_last_attempt=600)
    db = FakeDB(deliveries=[delivery])
    http_client = _make_http_client(status_code=503)

    with (
        patch("app.main.AsyncSessionLocal", return_value=db),
        patch("httpx.AsyncClient", return_value=http_client),
    ):
        from app.main import retry_failed_webhooks
        await retry_failed_webhooks()

    assert delivery.attempt_count == 3
    assert delivery.status == "exhausted"
    assert db.committed


@pytest.mark.asyncio
async def test_retry_exhausts_on_network_exception():
    """A network exception increments attempt_count; exhausted when count hits 3."""
    delivery = _delivery(attempt_count=2, minutes_since_last_attempt=600)
    db = FakeDB(deliveries=[delivery])
    http_client = _make_http_client(raises=ConnectionError("network down"))

    with (
        patch("app.main.AsyncSessionLocal", return_value=db),
        patch("httpx.AsyncClient", return_value=http_client),
    ):
        from app.main import retry_failed_webhooks
        await retry_failed_webhooks()

    assert delivery.attempt_count == 3
    assert delivery.status == "exhausted"
    assert db.committed


@pytest.mark.asyncio
async def test_retry_respects_backoff_window():
    """Delivery within the backoff window is skipped (not retried yet)."""
    # attempt_count=1 → backoff = 5^1 * 60 = 300 seconds
    # last_attempted_at = 2 minutes (120s) ago → within backoff window, skip
    delivery = _delivery(attempt_count=1, minutes_since_last_attempt=2)
    db = FakeDB(deliveries=[delivery])
    http_client = _make_http_client(status_code=200)

    with (
        patch("app.main.AsyncSessionLocal", return_value=db),
        patch("httpx.AsyncClient", return_value=http_client),
    ):
        from app.main import retry_failed_webhooks
        await retry_failed_webhooks()

    # Status and count unchanged — skipped due to backoff
    assert delivery.status == "failed"
    assert delivery.attempt_count == 1
    assert db.committed


@pytest.mark.asyncio
async def test_retry_no_deliveries_commits_cleanly():
    """When there are no eligible deliveries, job completes without error."""
    db = FakeDB(deliveries=[])

    with patch("app.main.AsyncSessionLocal", return_value=db):
        from app.main import retry_failed_webhooks
        await retry_failed_webhooks()

    assert db.committed


@pytest.mark.asyncio
async def test_retry_swallows_db_exception():
    """If the DB session raises, retry_failed_webhooks swallows the exception."""

    class BrokenDB:
        async def scalars(self, query):
            raise RuntimeError("DB unavailable")

        async def commit(self):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

    with patch("app.main.AsyncSessionLocal", return_value=BrokenDB()):
        from app.main import retry_failed_webhooks
        # Must not raise
        await retry_failed_webhooks()


@pytest.mark.asyncio
async def test_retry_processes_multiple_deliveries():
    """Multiple eligible deliveries are all processed in a single run."""
    deliveries = [
        _delivery(attempt_count=1, minutes_since_last_attempt=10),
        _delivery(attempt_count=1, minutes_since_last_attempt=10),
    ]
    db = FakeDB(deliveries=deliveries)
    http_client = _make_http_client(status_code=200)

    with (
        patch("app.main.AsyncSessionLocal", return_value=db),
        patch("httpx.AsyncClient", return_value=http_client),
    ):
        from app.main import retry_failed_webhooks
        await retry_failed_webhooks()

    assert all(d.status == "delivered" for d in deliveries)
    assert db.committed
