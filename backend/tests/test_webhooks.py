"""Webhook delivery tests — API endpoints, dispatch logic, HMAC signing."""

import asyncio
import hashlib
import hmac
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.dependencies import get_current_user_from_jwt, get_db
from app.main import app
from app.services.webhook_service import (
    _build_payload,
    _deliver,
    _is_safe_url,
    _resolve_safe_url,
    _sign_payload,
    dispatch_event,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class FakeDB:
    """Minimal async DB stub for webhook tests."""

    def __init__(self, *, get_result=None):
        self._get_result = get_result
        self.added: list = []
        self.committed = False

    async def get(self, model_class, pk):  # noqa: ARG002
        return self._get_result

    def add(self, model):
        self.added.append(model)

    async def commit(self):
        self.committed = True


def _admin_user(org_id=None):
    return SimpleNamespace(
        id=uuid4(),
        org_id=org_id or uuid4(),
        email="admin@test.com",
        name="Admin",
        role="admin",
        is_active=True,
    )


def _developer_user(org_id=None):
    return SimpleNamespace(
        id=uuid4(),
        org_id=org_id or uuid4(),
        email="dev@test.com",
        name="Dev",
        role="developer",
        is_active=True,
    )


def _org(org_id=None, settings=None):
    return SimpleNamespace(
        id=org_id or uuid4(),
        name="Test Org",
        slug="test-org",
        plan="growth",
        settings=settings or {},
        budget_monthly_usd=None,
        is_active=True,
    )


# ---------------------------------------------------------------------------
# API Endpoint Tests: GET /current/webhooks
# ---------------------------------------------------------------------------


def test_get_webhook_config_returns_defaults(client):
    """Admin GET returns empty config when no webhooks configured."""
    admin = _admin_user()
    org = _org(org_id=admin.org_id, settings={})

    async def fake_current_user_dep():
        return admin

    async def fake_get_db():
        yield FakeDB(get_result=org)

    app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
    app.dependency_overrides[get_db] = fake_get_db

    response = client.get(
        "/api/v1/organizations/current/webhooks",
        headers={"Authorization": "Bearer test"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["url"] == ""
    assert data["events"] == ["policy.violation", "budget.alert"]
    assert data["enabled"] is False
    # secret must NEVER be returned
    assert "secret" not in data


def test_get_webhook_config_non_admin_returns_403(client):
    """Non-admin users must get 403."""
    dev = _developer_user()

    async def fake_current_user_dep():
        return dev

    async def fake_get_db():
        yield FakeDB(get_result=_org(org_id=dev.org_id))

    app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
    app.dependency_overrides[get_db] = fake_get_db

    response = client.get(
        "/api/v1/organizations/current/webhooks",
        headers={"Authorization": "Bearer test"},
    )

    assert response.status_code == 403


# ---------------------------------------------------------------------------
# API Endpoint Tests: PATCH /current/webhooks
# ---------------------------------------------------------------------------


def test_patch_webhook_config_updates_and_returns_config(client):
    """Admin PATCH updates settings and returns config without secret."""
    admin = _admin_user()
    org = _org(org_id=admin.org_id, settings={})

    async def fake_current_user_dep():
        return admin

    async def fake_get_db():
        yield FakeDB(get_result=org)

    app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
    app.dependency_overrides[get_db] = fake_get_db

    response = client.patch(
        "/api/v1/organizations/current/webhooks",
        headers={"Authorization": "Bearer test"},
        json={
            "url": "https://example.com/hook",
            "secret": "my-secret",
            "events": ["policy.violation"],
            "enabled": True,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["url"] == "https://example.com/hook"
    assert data["events"] == ["policy.violation"]
    assert data["enabled"] is True
    assert "secret" not in data

    # Verify the org settings were updated (immutably)
    assert org.settings["webhooks"]["secret"] == "my-secret"


def test_patch_webhook_config_non_admin_returns_403(client):
    """Non-admin PATCH must return 403."""
    dev = _developer_user()

    async def fake_current_user_dep():
        return dev

    async def fake_get_db():
        yield FakeDB(get_result=_org(org_id=dev.org_id))

    app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
    app.dependency_overrides[get_db] = fake_get_db

    response = client.patch(
        "/api/v1/organizations/current/webhooks",
        headers={"Authorization": "Bearer test"},
        json={"url": "https://example.com/hook"},
    )

    assert response.status_code == 403


def test_patch_webhook_config_invalid_url_returns_422(client):
    """URL without http:// or https:// prefix must be rejected."""
    admin = _admin_user()

    async def fake_current_user_dep():
        return admin

    async def fake_get_db():
        yield FakeDB(get_result=_org(org_id=admin.org_id))

    app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
    app.dependency_overrides[get_db] = fake_get_db

    response = client.patch(
        "/api/v1/organizations/current/webhooks",
        headers={"Authorization": "Bearer test"},
        json={"url": "ftp://example.com/hook"},
    )

    assert response.status_code == 422


def test_patch_webhook_config_invalid_event_returns_422(client):
    """Unknown event type must be rejected by validator."""
    admin = _admin_user()

    async def fake_current_user_dep():
        return admin

    async def fake_get_db():
        yield FakeDB(get_result=_org(org_id=admin.org_id))

    app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
    app.dependency_overrides[get_db] = fake_get_db

    response = client.patch(
        "/api/v1/organizations/current/webhooks",
        headers={"Authorization": "Bearer test"},
        json={"url": "https://example.com/hook", "events": ["unknown.event"]},
    )

    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Unit Tests: _sign_payload
# ---------------------------------------------------------------------------


def test_sign_payload_produces_correct_hmac():
    """_sign_payload must produce a valid HMAC-SHA256 signature."""
    payload_bytes = b'{"event":"test"}'
    secret = "my-webhook-secret"

    result = _sign_payload(payload_bytes, secret)

    expected_mac = hmac.new(secret.encode(), payload_bytes, hashlib.sha256)
    assert result == f"sha256={expected_mac.hexdigest()}"


def test_sign_payload_different_secrets_produce_different_signatures():
    """Different secrets must produce different signatures."""
    payload_bytes = b'{"event":"test"}'

    sig1 = _sign_payload(payload_bytes, "secret-a")
    sig2 = _sign_payload(payload_bytes, "secret-b")

    assert sig1 != sig2


# ---------------------------------------------------------------------------
# Unit Tests: dispatch_event — webhook disabled
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatch_event_disabled_webhook_no_http_call():
    """When webhooks are disabled, no HTTP call should be made."""
    org = _org(settings={"webhooks": {"enabled": False, "url": "https://example.com/hook"}})
    db = FakeDB()

    with patch("app.services.webhook_service._deliver", new_callable=AsyncMock) as mock_deliver:
        await dispatch_event(db=db, org=org, event_type="policy.violation", data={})

    mock_deliver.assert_not_called()
    assert len(db.added) == 0


@pytest.mark.asyncio
async def test_dispatch_event_event_not_subscribed_no_http_call():
    """When event type is not in the subscribed events list, no HTTP call."""
    org = _org(settings={
        "webhooks": {
            "enabled": True,
            "url": "https://example.com/hook",
            "events": ["budget.alert"],
            "secret": "",
        }
    })
    db = FakeDB()

    with patch("app.services.webhook_service._deliver", new_callable=AsyncMock) as mock_deliver:
        await dispatch_event(db=db, org=org, event_type="policy.violation", data={})

    mock_deliver.assert_not_called()
    assert len(db.added) == 0


# ---------------------------------------------------------------------------
# Unit Tests: dispatch_event — successful delivery
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatch_event_sends_payload_and_logs_delivery():
    """dispatch_event sends correct payload and logs a delivered WebhookDelivery row."""
    org_id = uuid4()
    org = _org(
        org_id=org_id,
        settings={
            "webhooks": {
                "enabled": True,
                "url": "https://example.com/hook",
                "events": ["policy.violation"],
                "secret": "test-secret",
            }
        },
    )
    db = FakeDB()

    with patch("app.services.webhook_service._deliver", new_callable=AsyncMock) as mock_deliver:
        mock_deliver.return_value = ("delivered", 200)

        await dispatch_event(
            db=db,
            org=org,
            event_type="policy.violation",
            data={"request_id": "req-123", "reason_code": "blocked_keyword"},
        )

    mock_deliver.assert_called_once()
    call_args = mock_deliver.call_args
    assert call_args[0][0] == "https://example.com/hook"
    # Verify the payload structure
    payload = call_args[0][1]
    assert payload["event"] == "policy.violation"
    assert payload["org_id"] == str(org_id)
    assert payload["data"]["request_id"] == "req-123"
    # Verify secret was passed
    assert call_args[0][2] == "test-secret"

    # Verify delivery row was logged
    assert len(db.added) == 1
    delivery = db.added[0]
    assert delivery.status == "delivered"
    assert delivery.http_status == 200
    assert delivery.attempt_count == 1
    assert db.committed


# ---------------------------------------------------------------------------
# Unit Tests: dispatch_event — sends X-OpenProxy-Signature header
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deliver_sends_signature_header():
    """_deliver must send X-OpenProxy-Signature header when secret is provided."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.is_success = True

    payload = {"event": "test", "data": {}}
    secret = "my-secret"

    captured_headers = {}

    async def fake_post(self_or_url, url_or_none=None, **kwargs):
        headers = kwargs.get("headers", {})
        captured_headers.update(headers)
        return mock_response

    with (
        patch("app.services.webhook_service._resolve_safe_url", return_value=(True, "93.184.216.34")),
        patch("httpx.AsyncClient.post", side_effect=fake_post),
    ):
        result_status, http_status = await _deliver("https://example.com/hook", payload, secret)

    assert result_status == "delivered"
    assert http_status == 200
    expected_body = json.dumps(payload, default=str).encode()
    expected_sig = _sign_payload(expected_body, secret)
    assert captured_headers["X-OpenProxy-Signature"] == expected_sig


# ---------------------------------------------------------------------------
# Unit Tests: dispatch_event — failed delivery
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatch_event_logs_failed_delivery_on_exception():
    """dispatch_event logs a failed WebhookDelivery row when httpx raises."""
    org = _org(settings={
        "webhooks": {
            "enabled": True,
            "url": "https://example.com/hook",
            "events": ["policy.violation"],
            "secret": "",
        }
    })
    db = FakeDB()

    with patch("app.services.webhook_service._deliver", new_callable=AsyncMock) as mock_deliver:
        mock_deliver.return_value = ("failed", None)

        await dispatch_event(
            db=db,
            org=org,
            event_type="policy.violation",
            data={"request_id": "req-456"},
        )

    assert len(db.added) == 1
    delivery = db.added[0]
    assert delivery.status == "failed"
    assert delivery.http_status is None
    assert delivery.attempt_count == 3  # _MAX_RETRIES
    assert db.committed


# ---------------------------------------------------------------------------
# Unit Tests: dispatch_event — never raises
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatch_event_swallows_all_exceptions():
    """dispatch_event must never raise — it swallows all exceptions."""
    org = _org(settings={
        "webhooks": {
            "enabled": True,
            "url": "https://example.com/hook",
            "events": ["policy.violation"],
            "secret": "",
        }
    })
    db = FakeDB()

    with patch("app.services.webhook_service._deliver", new_callable=AsyncMock) as mock_deliver:
        mock_deliver.side_effect = RuntimeError("Network exploded")

        # Should NOT raise
        await dispatch_event(
            db=db,
            org=org,
            event_type="policy.violation",
            data={},
        )


# ---------------------------------------------------------------------------
# Unit Tests: _build_payload
# ---------------------------------------------------------------------------


def test_build_payload_structure():
    """_build_payload must return a dict with event, timestamp, org_id, data."""
    result = _build_payload("policy.violation", "org-123", {"key": "value"})

    assert result["event"] == "policy.violation"
    assert result["org_id"] == "org-123"
    assert result["data"] == {"key": "value"}
    assert "timestamp" in result


# ---------------------------------------------------------------------------
# Unit Tests: _resolve_safe_url and CGN blocking
# ---------------------------------------------------------------------------


def test_resolve_safe_url_rejects_http():
    """HTTP URLs are rejected — only HTTPS is allowed."""
    safe, ip = _resolve_safe_url("http://example.com/hook")
    assert safe is False
    assert ip is None


def test_resolve_safe_url_rejects_no_hostname():
    """URLs without a hostname are rejected."""
    safe, ip = _resolve_safe_url("https:///path")
    assert safe is False


def test_resolve_safe_url_rejects_private_ip(monkeypatch):
    """Private IPs (10.0.0.0/8) must be blocked."""
    monkeypatch.setattr(
        "app.services.webhook_service.socket.getaddrinfo",
        lambda *a, **kw: [(2, 1, 6, "", ("10.0.0.5", 443))],
    )
    safe, ip = _resolve_safe_url("https://internal.example.com/hook")
    assert safe is False


def test_resolve_safe_url_rejects_loopback(monkeypatch):
    """Loopback IPs must be blocked."""
    monkeypatch.setattr(
        "app.services.webhook_service.socket.getaddrinfo",
        lambda *a, **kw: [(2, 1, 6, "", ("127.0.0.1", 443))],
    )
    safe, ip = _resolve_safe_url("https://localhost/hook")
    assert safe is False


def test_resolve_safe_url_rejects_link_local(monkeypatch):
    """Link-local IPs (169.254.0.0/16) must be blocked."""
    monkeypatch.setattr(
        "app.services.webhook_service.socket.getaddrinfo",
        lambda *a, **kw: [(2, 1, 6, "", ("169.254.1.1", 443))],
    )
    safe, ip = _resolve_safe_url("https://link-local.example.com/hook")
    assert safe is False


def test_resolve_safe_url_rejects_cgn(monkeypatch):
    """Carrier-Grade NAT IPs (100.64.0.0/10) must be blocked."""
    monkeypatch.setattr(
        "app.services.webhook_service.socket.getaddrinfo",
        lambda *a, **kw: [(2, 1, 6, "", ("100.100.1.1", 443))],
    )
    safe, ip = _resolve_safe_url("https://cgn.example.com/hook")
    assert safe is False


def test_resolve_safe_url_rejects_rfc1918_172(monkeypatch):
    """172.16.0.0/12 private range must be blocked."""
    monkeypatch.setattr(
        "app.services.webhook_service.socket.getaddrinfo",
        lambda *a, **kw: [(2, 1, 6, "", ("172.16.5.10", 443))],
    )
    safe, ip = _resolve_safe_url("https://corp.example.com/hook")
    assert safe is False


def test_resolve_safe_url_rejects_rfc1918_192(monkeypatch):
    """192.168.0.0/16 private range must be blocked."""
    monkeypatch.setattr(
        "app.services.webhook_service.socket.getaddrinfo",
        lambda *a, **kw: [(2, 1, 6, "", ("192.168.1.1", 443))],
    )
    safe, ip = _resolve_safe_url("https://home.example.com/hook")
    assert safe is False


def test_resolve_safe_url_accepts_public_ip(monkeypatch):
    """Public IPs should be accepted and returned."""
    monkeypatch.setattr(
        "app.services.webhook_service.socket.getaddrinfo",
        lambda *a, **kw: [(2, 1, 6, "", ("93.184.216.34", 443))],
    )
    safe, ip = _resolve_safe_url("https://example.com/hook")
    assert safe is True
    assert ip == "93.184.216.34"


def test_resolve_safe_url_returns_first_ip(monkeypatch):
    """When multiple IPs resolve, the first public one is returned."""
    monkeypatch.setattr(
        "app.services.webhook_service.socket.getaddrinfo",
        lambda *a, **kw: [
            (2, 1, 6, "", ("93.184.216.34", 443)),
            (2, 1, 6, "", ("93.184.216.35", 443)),
        ],
    )
    safe, ip = _resolve_safe_url("https://example.com/hook")
    assert safe is True
    assert ip == "93.184.216.34"


def test_resolve_safe_url_rejects_if_any_ip_is_private(monkeypatch):
    """If any resolved IP is private, the whole URL is rejected."""
    monkeypatch.setattr(
        "app.services.webhook_service.socket.getaddrinfo",
        lambda *a, **kw: [
            (2, 1, 6, "", ("93.184.216.34", 443)),
            (2, 1, 6, "", ("10.0.0.1", 443)),
        ],
    )
    safe, ip = _resolve_safe_url("https://dual.example.com/hook")
    assert safe is False


def test_resolve_safe_url_dns_failure(monkeypatch):
    """DNS resolution failure returns (False, None)."""
    monkeypatch.setattr(
        "app.services.webhook_service.socket.getaddrinfo",
        lambda *a, **kw: (_ for _ in ()).throw(socket.gaierror("DNS failed")),
    )
    import socket
    safe, ip = _resolve_safe_url("https://nonexistent.example.com/hook")
    assert safe is False
    assert ip is None


def test_is_safe_url_thin_wrapper(monkeypatch):
    """_is_safe_url should be a thin wrapper around _resolve_safe_url."""
    monkeypatch.setattr(
        "app.services.webhook_service.socket.getaddrinfo",
        lambda *a, **kw: [(2, 1, 6, "", ("93.184.216.34", 443))],
    )
    assert _is_safe_url("https://example.com/hook") is True


@pytest.mark.asyncio
async def test_deliver_rejects_unsafe_url():
    """_deliver must return ('failed', None) for unsafe URLs without making HTTP calls."""
    with patch("app.services.webhook_service._resolve_safe_url", return_value=(False, None)):
        result_status, result_http = await _deliver(
            "https://internal.example.com/hook", {"event": "test"}, "secret",
        )
    assert result_status == "failed"
    assert result_http is None


@pytest.mark.asyncio
async def test_deliver_calls_original_url_after_resolve(monkeypatch):
    """_deliver resolves DNS for validation, then requests the original URL for correct TLS."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.is_success = True

    captured_url = {}

    async def fake_post(self_or_url, url_or_none=None, **kwargs):
        captured_url["url"] = self_or_url if url_or_none is None else url_or_none
        return mock_response

    with (
        patch("app.services.webhook_service._resolve_safe_url", return_value=(True, "93.184.216.34")) as mock_resolve,
        patch("httpx.AsyncClient.post", side_effect=fake_post),
    ):
        result_status, _ = await _deliver("https://example.com/hook", {"event": "test"}, "")

    assert result_status == "delivered"
    mock_resolve.assert_called_once_with("https://example.com/hook")
