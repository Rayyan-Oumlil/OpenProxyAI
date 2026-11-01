"""Tests for the retry_failed_webhooks APScheduler job in main.py."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch
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
    org_id=None,
) -> SimpleNamespace:
    """Build a fake WebhookDelivery object."""
    return SimpleNamespace(
        id=uuid4(),
        org_id=org_id or uuid4(),
        url=url,
        payload=payload or {"event": "policy.violation"},
        status=status,
        attempt_count=attempt_count,
        last_attempted_at=datetime.now(UTC) - timedelta(minutes=minutes_since_last_attempt),
        http_status=http_status,
    )


def _org(org_id=None, settings=None):
    return SimpleNamespace(
        id=org_id or uuid4(),
        settings=settings or {"webhooks": {"secret": "s3cret"}},
    )


class FakeScalarResult:
    """Mimics SQLAlchemy ScalarResult.all()."""

    def __init__(self, items: list) -> None:
        self._items = items

    def all(self) -> list:
        return self._items


class FakeDB:
    """Minimal async DB session stub."""

    @property
    def info(self) -> dict:
        # Mirrors AsyncSession.info (set_session_org_id stores the org there).
        return self.__dict__.setdefault("_info", {})


    def __init__(
        self,
        deliveries: list | None = None,
        org=None,
        orgs: list | None = None,
    ) -> None:
        self._deliveries = deliveries or []
        self._org = org
        self._orgs = orgs  # When provided, first scalars() returns these (Organization query)
        self._scalars_call_count = 0
        self.committed = False

    async def execute(self, *args, **kwargs):  # noqa: ARG002
        return None

    async def scalars(self, query):  # noqa: ARG002
        self._scalars_call_count += 1
        if self._orgs is not None and self._scalars_call_count == 1:
            return FakeScalarResult(self._orgs)
        return FakeScalarResult(self._deliveries)

    async def get(self, model_class, pk):  # noqa: ARG002
        return self._org

    async def commit(self) -> None:
        self.committed = True

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retry_delivers_failed_webhook():
    """A failed delivery with attempt_count < 3 is retried and marked delivered on 2xx."""
    org_id = uuid4()
    delivery = _delivery(attempt_count=1, minutes_since_last_attempt=10, org_id=org_id)
    org = _org(org_id=org_id)
    db = FakeDB(deliveries=[delivery], org=org)

    async def fake_deliver(url, payload, secret):
        return "delivered", 200

    with (
        patch("app.main.AsyncSessionLocal", return_value=db),
        patch("app.main._webhook_deliver", side_effect=fake_deliver),
    ):
        from app.main import retry_failed_webhooks
        await retry_failed_webhooks()

    assert delivery.status == "delivered"
    assert delivery.http_status == 200
    assert db.committed


@pytest.mark.asyncio
async def test_retry_increments_attempt_count_on_http_error():
    """A failed _deliver increments attempt_count but does not mark as exhausted yet."""
    org_id = uuid4()
    delivery = _delivery(attempt_count=1, minutes_since_last_attempt=10, org_id=org_id)
    org = _org(org_id=org_id)
    db = FakeDB(deliveries=[delivery], org=org)

    async def fake_deliver(url, payload, secret):
        return "failed", 500

    with (
        patch("app.main.AsyncSessionLocal", return_value=db),
        patch("app.main._webhook_deliver", side_effect=fake_deliver),
    ):
        from app.main import retry_failed_webhooks
        await retry_failed_webhooks()

    assert delivery.attempt_count == 2
    assert delivery.status == "failed"
    assert db.committed


@pytest.mark.asyncio
async def test_retry_exhausts_after_reaching_max_attempts_http_error():
    """When attempt_count reaches 3 after a failed retry, status becomes exhausted."""
    org_id = uuid4()
    delivery = _delivery(attempt_count=2, minutes_since_last_attempt=600, org_id=org_id)
    org = _org(org_id=org_id)
    db = FakeDB(deliveries=[delivery], org=org)

    async def fake_deliver(url, payload, secret):
        return "failed", 503

    with (
        patch("app.main.AsyncSessionLocal", return_value=db),
        patch("app.main._webhook_deliver", side_effect=fake_deliver),
    ):
        from app.main import retry_failed_webhooks
        await retry_failed_webhooks()

    assert delivery.attempt_count == 3
    assert delivery.status == "exhausted"
    assert db.committed


@pytest.mark.asyncio
async def test_retry_exhausts_on_failed_deliver():
    """A failed delivery increments attempt_count; exhausted when count hits 3."""
    org_id = uuid4()
    delivery = _delivery(attempt_count=2, minutes_since_last_attempt=600, org_id=org_id)
    org = _org(org_id=org_id)
    db = FakeDB(deliveries=[delivery], org=org)

    async def fake_deliver(url, payload, secret):
        return "failed", None

    with (
        patch("app.main.AsyncSessionLocal", return_value=db),
        patch("app.main._webhook_deliver", side_effect=fake_deliver),
    ):
        from app.main import retry_failed_webhooks
        await retry_failed_webhooks()

    assert delivery.attempt_count == 3
    assert delivery.status == "exhausted"
    assert db.committed


@pytest.mark.asyncio
async def test_retry_respects_backoff_window():
    """Delivery within the backoff window is skipped (not retried yet)."""
    delivery = _delivery(attempt_count=1, minutes_since_last_attempt=2)
    db = FakeDB(deliveries=[delivery])

    async def fake_deliver(url, payload, secret):
        return "delivered", 200

    with (
        patch("app.main.AsyncSessionLocal", return_value=db),
        patch("app.main._webhook_deliver", side_effect=fake_deliver),
    ):
        from app.main import retry_failed_webhooks
        await retry_failed_webhooks()

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
        await retry_failed_webhooks()


@pytest.mark.asyncio
async def test_retry_processes_multiple_deliveries():
    """Multiple eligible deliveries are all processed in a single run."""
    org_id = uuid4()
    deliveries = [
        _delivery(attempt_count=1, minutes_since_last_attempt=10, org_id=org_id),
        _delivery(attempt_count=1, minutes_since_last_attempt=10, org_id=org_id),
    ]
    org = _org(org_id=org_id)
    db = FakeDB(deliveries=deliveries, org=org)

    async def fake_deliver(url, payload, secret):
        return "delivered", 200

    with (
        patch("app.main.AsyncSessionLocal", return_value=db),
        patch("app.main._webhook_deliver", side_effect=fake_deliver),
    ):
        from app.main import retry_failed_webhooks
        await retry_failed_webhooks()

    assert all(d.status == "delivered" for d in deliveries)
    assert db.committed


@pytest.mark.asyncio
async def test_retry_passes_org_webhook_secret():
    """The retry job must look up the org's webhook secret and pass it to _deliver."""
    org_id = uuid4()
    delivery = _delivery(attempt_count=1, minutes_since_last_attempt=10, org_id=org_id)
    org = _org(org_id=org_id, settings={"webhooks": {"secret": "org-secret-123"}})
    db = FakeDB(deliveries=[delivery], org=org, orgs=[org])

    captured_secret = {}

    async def fake_deliver(url, payload, secret):
        captured_secret["value"] = secret
        return "delivered", 200

    with (
        patch("app.main.AsyncSessionLocal", return_value=db),
        patch("app.main._webhook_deliver", side_effect=fake_deliver),
    ):
        from app.main import retry_failed_webhooks
        await retry_failed_webhooks()

    assert captured_secret["value"] == "org-secret-123"


@pytest.mark.asyncio
async def test_retry_uses_empty_secret_when_org_not_found():
    """If the org is not found in DB, secret defaults to empty string."""
    delivery = _delivery(attempt_count=1, minutes_since_last_attempt=10)
    db = FakeDB(deliveries=[delivery], org=None)

    captured_secret = {}

    async def fake_deliver(url, payload, secret):
        captured_secret["value"] = secret
        return "delivered", 200

    with (
        patch("app.main.AsyncSessionLocal", return_value=db),
        patch("app.main._webhook_deliver", side_effect=fake_deliver),
    ):
        from app.main import retry_failed_webhooks
        await retry_failed_webhooks()

    assert captured_secret["value"] == ""
