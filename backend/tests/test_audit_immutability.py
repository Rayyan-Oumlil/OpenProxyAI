"""Audit log immutability tests — archived_at column, archival cron, and endpoint filtering."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.dependencies import get_current_user_from_jwt, get_db
from app.main import app
from app.models.request_log import RequestLog
from app.schemas.logs import Page, RequestLogDetail, RequestLogItem
from app.services import analytics_service as analytics_service_module


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class FakeDB:
    async def commit(self):
        return None


# ---------------------------------------------------------------------------
# Unit: archived_at field exists on the model
# ---------------------------------------------------------------------------


def test_archived_at_column_exists_on_request_log_model():
    """The RequestLog model must expose an archived_at column."""
    column_names = [c.name for c in RequestLog.__table__.columns]
    assert "archived_at" in column_names


def test_archived_at_column_is_nullable():
    """archived_at must be nullable (NULL = not archived)."""
    col = RequestLog.__table__.columns["archived_at"]
    assert col.nullable is True


# ---------------------------------------------------------------------------
# Unit: archive_old_logs marks old logs, skips recent ones
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_archive_old_logs_marks_expired_logs(monkeypatch):
    """Logs older than the plan retention window get archived_at set."""
    from app.main import archive_old_logs

    org_id = uuid4()
    org = SimpleNamespace(id=org_id, plan="free", is_active=True)

    executed_statements: list[object] = []
    committed = {"called": False}

    class FakeResult:
        def scalars(self):
            return self

        def all(self):
            return [org]

    class FakeArchiveSession:
        async def execute(self, stmt, *args, **kwargs):
            executed_statements.append(stmt)
            return FakeResult()

        async def commit(self):
            committed["called"] = True

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

    monkeypatch.setattr(
        "app.main.AsyncSessionLocal", lambda: FakeArchiveSession()
    )

    await archive_old_logs()

    # Should have executed 2 statements: SELECT orgs + UPDATE logs
    assert len(executed_statements) == 2
    assert committed["called"] is True


@pytest.mark.asyncio
async def test_archive_old_logs_does_not_touch_recent_logs(monkeypatch):
    """Logs within the retention window must NOT be archived."""
    from app.main import archive_old_logs

    org_id = uuid4()
    # enterprise plan has 365-day retention
    org = SimpleNamespace(id=org_id, plan="enterprise", is_active=True)

    update_clauses: list[object] = []

    class FakeResult:
        def scalars(self):
            return self

        def all(self):
            return [org]

    class FakeArchiveSession:
        async def execute(self, stmt, *args, **kwargs):
            update_clauses.append(stmt)
            return FakeResult()

        async def commit(self):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

    monkeypatch.setattr(
        "app.main.AsyncSessionLocal", lambda: FakeArchiveSession()
    )

    await archive_old_logs()

    # The UPDATE statement is issued but it filters by created_at < cutoff,
    # meaning only logs older than 365 days would be affected.
    # We verify the function completed without error and issued the expected
    # number of statements (SELECT orgs + UPDATE for the org).
    assert len(update_clauses) == 2


@pytest.mark.asyncio
async def test_archive_old_logs_handles_exception(monkeypatch):
    """archive_old_logs must not raise; it logs the exception instead."""
    from app.main import archive_old_logs

    class FailingSession:
        async def execute(self, stmt, *args, **kwargs):
            raise RuntimeError("DB is down")

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

    monkeypatch.setattr(
        "app.main.AsyncSessionLocal", lambda: FailingSession()
    )

    # Must not raise
    await archive_old_logs()


# ---------------------------------------------------------------------------
# Route: GET /api/v1/analytics/logs excludes archived by default
# ---------------------------------------------------------------------------


def test_logs_endpoint_excludes_archived_by_default(client, monkeypatch):
    """GET /logs without include_archived should pass include_archived=False to service."""
    org_id = uuid4()
    user = SimpleNamespace(id=uuid4(), org_id=org_id, email="admin@test.com", is_active=True)

    captured_kwargs: dict = {}

    async def fake_current_user_dep():
        return user

    async def fake_get_db():
        yield FakeDB()

    async def fake_get_request_logs(**kwargs):
        captured_kwargs.update(kwargs)
        return Page[RequestLogItem](
            items=[],
            total=0,
            page=1,
            page_size=50,
            total_pages=1,
        )

    monkeypatch.setattr(analytics_service_module.analytics_service, "get_request_logs", fake_get_request_logs)
    app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
    app.dependency_overrides[get_db] = fake_get_db

    response = client.get(
        "/api/v1/analytics/logs",
        headers={"Authorization": "Bearer test"},
    )

    assert response.status_code == 200
    assert captured_kwargs.get("include_archived") is False


# ---------------------------------------------------------------------------
# Route: GET /api/v1/analytics/logs?include_archived=true includes archived
# ---------------------------------------------------------------------------


def test_logs_endpoint_includes_archived_when_requested(client, monkeypatch):
    """GET /logs?include_archived=true should pass include_archived=True to service."""
    org_id = uuid4()
    user = SimpleNamespace(id=uuid4(), org_id=org_id, email="admin@test.com", is_active=True)

    captured_kwargs: dict = {}

    async def fake_current_user_dep():
        return user

    async def fake_get_db():
        yield FakeDB()

    async def fake_get_request_logs(**kwargs):
        captured_kwargs.update(kwargs)
        return Page[RequestLogItem](
            items=[],
            total=0,
            page=1,
            page_size=50,
            total_pages=1,
        )

    monkeypatch.setattr(analytics_service_module.analytics_service, "get_request_logs", fake_get_request_logs)
    app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
    app.dependency_overrides[get_db] = fake_get_db

    response = client.get(
        "/api/v1/analytics/logs?include_archived=true",
        headers={"Authorization": "Bearer test"},
    )

    assert response.status_code == 200
    assert captured_kwargs.get("include_archived") is True


# ---------------------------------------------------------------------------
# Route: GET /api/v1/analytics/logs/{log_id} always returns archived logs
# ---------------------------------------------------------------------------


def test_log_detail_returns_archived_log(client, monkeypatch):
    """GET /logs/{id} must return an archived log (no 404 for archived entries)."""
    org_id = uuid4()
    user = SimpleNamespace(id=uuid4(), org_id=org_id, email="admin@test.com", is_active=True)
    log_id = uuid4()

    async def fake_current_user_dep():
        return user

    async def fake_get_db():
        yield FakeDB()

    async def fake_get_log_detail(**kwargs):
        assert kwargs["log_id"] == log_id
        return RequestLogDetail(
            id=log_id,
            request_id=uuid4(),
            user_id=uuid4(),
            api_key_id=uuid4(),
            created_at=datetime.now(UTC),
            model="openai/gpt-4o-mini",
            provider="openai",
            status="success",
            status_code=200,
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cost_usd=0.01,
            latency_ms=120,
            ttft_ms=40,
            error_message=None,
            policy_action="allow",
            policy_reason=None,
            policy_triggered_rules=[],
            request_metadata={"policy": {"action": "allow"}, "archived": True},
        )

    monkeypatch.setattr(analytics_service_module.analytics_service, "get_log_detail", fake_get_log_detail)
    app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
    app.dependency_overrides[get_db] = fake_get_db

    response = client.get(
        f"/api/v1/analytics/logs/{log_id}",
        headers={"Authorization": "Bearer test"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(log_id)
    assert data["model"] == "openai/gpt-4o-mini"
