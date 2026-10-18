"""SSO endpoint and service tests — OIDC connection CRUD, initiate, callback."""

import asyncio
import base64
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.dependencies import get_current_user_from_jwt, get_db, get_redis
from app.main import app
from app.services import sso_service


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class FakeScalarsResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class FakeExecuteResult:
    def __init__(self, *, scalars_rows=None, scalar_one_or_none_value=None):
        self._scalars_rows = scalars_rows or []
        self._scalar_one_or_none_value = scalar_one_or_none_value

    def scalars(self):
        return FakeScalarsResult(self._scalars_rows)

    def scalar_one_or_none(self):
        return self._scalar_one_or_none_value


class FakeDB:
    """Minimal async DB stub for SSO tests."""

    @property
    def info(self) -> dict:
        # Mirrors AsyncSession.info (set_session_org_id stores the org there).
        return self.__dict__.setdefault("_info", {})


    def __init__(
        self,
        *,
        get_results=None,
        execute_results=None,
    ):
        self._get_results = get_results or {}
        self._execute_results = execute_results or []
        self._execute_call_idx = 0
        self.added = []
        self.deleted = []
        self.committed = False

    async def get(self, model_class, pk):  # noqa: ARG002
        return self._get_results.get(pk)

    async def execute(self, query):  # noqa: ARG002
        if self._execute_call_idx < len(self._execute_results):
            result = self._execute_results[self._execute_call_idx]
            self._execute_call_idx += 1
            return result
        return FakeExecuteResult()

    def add(self, model):
        self.added.append(model)

    async def delete(self, model):
        self.deleted.append(model)

    async def commit(self):
        self.committed = True

    async def refresh(self, model):  # noqa: ARG002
        pass


class FakeRedis:
    def __init__(self):
        self._store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def setex(self, key: str, ttl: int, value: str) -> bool:  # noqa: ARG002
        self._store[key] = value
        return True

    async def delete(self, *keys: str) -> int:
        deleted = 0
        for key in keys:
            if key in self._store:
                del self._store[key]
                deleted += 1
        return deleted


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


def _enterprise_org(org_id):
    return SimpleNamespace(
        id=org_id, plan="enterprise", name="Enterprise Org", slug="enterprise-org"
    )


def _free_org(org_id):
    return SimpleNamespace(id=org_id, plan="free", name="Free Org", slug="free-org")


def _sso_connection(org_id):
    return SimpleNamespace(
        id=uuid4(),
        org_id=org_id,
        provider_name="okta",
        issuer_url="https://example.okta.com",
        client_id="test-client-id",
        client_secret_encrypted="encrypted-secret",
        domain_hint=None,
        is_active=True,
    )


# ---------------------------------------------------------------------------
# Test: Admin can create SSO connection (enterprise plan)
# ---------------------------------------------------------------------------


def test_create_sso_connection_admin_enterprise(client, monkeypatch):
    org_id = uuid4()
    admin = _admin_user(org_id)
    org = _enterprise_org(org_id)
    conn = _sso_connection(org_id)

    async def fake_create(**kwargs):
        return conn

    async def fake_current_user_dep():
        return admin

    async def fake_get_db():
        yield FakeDB(get_results={org_id: org})

    monkeypatch.setattr(sso_service, "create_sso_connection", fake_create)
    app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
    app.dependency_overrides[get_db] = fake_get_db

    response = client.post(
        "/api/v1/sso/connections",
        headers={"Authorization": "Bearer test"},
        json={
            "provider_name": "okta",
            "issuer_url": "https://example.okta.com",
            "client_id": "test-client-id",
            "client_secret": "test-secret",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["provider_name"] == "okta"
    assert data["client_id"] == "test-client-id"
    assert "client_secret" not in data


# ---------------------------------------------------------------------------
# Test: Non-admin cannot create SSO connection -> 403
# ---------------------------------------------------------------------------


def test_create_sso_connection_non_admin_returns_403(client):
    dev = _developer_user()

    async def fake_current_user_dep():
        return dev

    async def fake_get_db():
        yield FakeDB()

    app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
    app.dependency_overrides[get_db] = fake_get_db

    response = client.post(
        "/api/v1/sso/connections",
        headers={"Authorization": "Bearer test"},
        json={
            "provider_name": "okta",
            "issuer_url": "https://example.okta.com",
            "client_id": "test-client-id",
            "client_secret": "test-secret",
        },
    )

    assert response.status_code == 403
    assert "admin" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Test: Free plan org cannot create SSO connection -> 402
# ---------------------------------------------------------------------------


def test_create_sso_connection_free_plan_returns_402(client):
    org_id = uuid4()
    admin = _admin_user(org_id)
    org = _free_org(org_id)

    async def fake_current_user_dep():
        return admin

    async def fake_get_db():
        yield FakeDB(get_results={org_id: org})

    app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
    app.dependency_overrides[get_db] = fake_get_db

    response = client.post(
        "/api/v1/sso/connections",
        headers={"Authorization": "Bearer test"},
        json={
            "provider_name": "okta",
            "issuer_url": "https://example.okta.com",
            "client_id": "test-client-id",
            "client_secret": "test-secret",
        },
    )

    assert response.status_code == 402
    data = response.json()["detail"]
    assert data["error"] == "plan_limit_exceeded"
    assert data["feature"] == "sso_enabled"


# ---------------------------------------------------------------------------
# Test: Admin can list SSO connections
# ---------------------------------------------------------------------------


def test_list_sso_connections_admin(client, monkeypatch):
    org_id = uuid4()
    admin = _admin_user(org_id)
    conn = _sso_connection(org_id)

    async def fake_list(db, org_id):  # noqa: ARG001
        return [conn]

    async def fake_current_user_dep():
        return admin

    async def fake_get_db():
        yield FakeDB()

    monkeypatch.setattr(sso_service, "list_sso_connections", fake_list)
    app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
    app.dependency_overrides[get_db] = fake_get_db

    response = client.get(
        "/api/v1/sso/connections",
        headers={"Authorization": "Bearer test"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["provider_name"] == "okta"


# ---------------------------------------------------------------------------
# Test: Admin can delete SSO connection -> 204
# ---------------------------------------------------------------------------


def test_delete_sso_connection_admin_returns_204(client, monkeypatch):
    admin = _admin_user()
    connection_id = uuid4()

    async def fake_delete(db, org_id, cid):  # noqa: ARG001
        return True

    async def fake_current_user_dep():
        return admin

    async def fake_get_db():
        yield FakeDB()

    monkeypatch.setattr(sso_service, "delete_sso_connection", fake_delete)
    app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
    app.dependency_overrides[get_db] = fake_get_db

    response = client.delete(
        f"/api/v1/sso/connections/{connection_id}",
        headers={"Authorization": "Bearer test"},
    )

    assert response.status_code == 204


# ---------------------------------------------------------------------------
# Test: Delete non-existent connection -> 404
# ---------------------------------------------------------------------------


def test_delete_sso_connection_not_found_returns_404(client, monkeypatch):
    admin = _admin_user()
    connection_id = uuid4()

    async def fake_delete(db, org_id, cid):  # noqa: ARG001
        return False

    async def fake_current_user_dep():
        return admin

    async def fake_get_db():
        yield FakeDB()

    monkeypatch.setattr(sso_service, "delete_sso_connection", fake_delete)
    app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
    app.dependency_overrides[get_db] = fake_get_db

    response = client.delete(
        f"/api/v1/sso/connections/{connection_id}",
        headers={"Authorization": "Bearer test"},
    )

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Test: sso_initiate redirects to IdP URL
# ---------------------------------------------------------------------------


def test_sso_initiate_redirects_to_idp(client, monkeypatch):
    auth_url = "https://example.okta.com/authorize?response_type=code&client_id=cid"

    async def fake_initiate(db, redis, connection_id, redirect_uri):  # noqa: ARG001
        return auth_url

    async def fake_get_db():
        yield FakeDB()

    async def fake_get_redis():
        return FakeRedis()

    monkeypatch.setattr(sso_service, "initiate_sso", fake_initiate)
    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_redis] = fake_get_redis

    # redirect_uri is not validated when initiate_sso is mocked
    response = client.get(
        "/api/v1/auth/sso/initiate",
        params={"connection_id": str(uuid4()), "redirect_uri": "https://app.test/api/v1/auth/sso/callback"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["location"] == auth_url


def test_sso_initiate_rejects_invalid_redirect_uri(client, monkeypatch):
    """C02: redirect_uri must match APP_BASE_URL callback."""
    org_id = uuid4()
    conn = _sso_connection(org_id)

    async def fake_get_db():
        yield FakeDB(execute_results=[FakeExecuteResult(scalar_one_or_none_value=conn)])

    async def fake_get_redis():
        return FakeRedis()

    monkeypatch.setattr(
        "app.services.sso_service.settings.APP_BASE_URL",
        "https://api.example.com",
    )

    async def fake_fetch_oidc(u):
        return {
            "authorization_endpoint": "https://example.com/authorize",
            "token_endpoint": "https://example.com/token",
            "jwks_uri": "https://example.com/jwks",
        }

    monkeypatch.setattr(
        "app.services.sso_service._fetch_oidc_config",
        fake_fetch_oidc,
    )
    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_redis] = fake_get_redis

    # Wrong redirect_uri (evildomain)
    response = client.get(
        "/api/v1/auth/sso/initiate",
        params={
            "connection_id": str(conn.id),
            "redirect_uri": "https://evil.com/callback",
        },
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert "redirect_uri" in response.json().get("detail", "").lower()


# ---------------------------------------------------------------------------
# Test: handle_sso_callback with invalid state -> 400
# ---------------------------------------------------------------------------


def test_handle_sso_callback_invalid_state_returns_400():
    redis = FakeRedis()
    db = FakeDB()

    async def run():
        return await sso_service.handle_sso_callback(
            db=db,
            redis=redis,
            code="authcode",
            state="invalid-state",
            redirect_uri="https://app.test/callback",
            base_url="OpenProxyAI",
        )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(run())

    assert exc_info.value.status_code == 400
    assert "invalid or expired" in exc_info.value.detail.lower()


# ---------------------------------------------------------------------------
# Test: handle_sso_callback with mismatched nonce -> 400
# ---------------------------------------------------------------------------


def test_handle_sso_callback_mismatched_nonce_returns_400(monkeypatch):
    redis = FakeRedis()
    conn_id = str(uuid4())
    org_id = uuid4()

    state_key = "test-state-key"
    state_data = json.dumps({
        "connection_id": conn_id,
        "nonce": "expected-nonce-value",
        "redirect_uri": "https://app.test/callback",
    })

    conn = _sso_connection(org_id)
    conn.id = conn_id

    db = FakeDB(
        execute_results=[
            FakeExecuteResult(scalar_one_or_none_value=conn),
        ]
    )

    fake_token_response = {
        "access_token": "at",
        "id_token": "header.payload.sig",
    }

    def fake_verify_id_token(id_token, jwks_uri, client_id, issuer):  # noqa: ARG001
        return {"sub": "user123", "email": "sso@test.com", "nonce": "wrong-nonce-value"}

    fake_oidc_config = {
        "authorization_endpoint": "https://example.okta.com/authorize",
        "token_endpoint": "https://example.okta.com/token",
        "jwks_uri": "https://example.okta.com/jwks",
        "issuer": "https://example.okta.com",
    }

    async def fake_fetch_oidc_config(issuer_url):  # noqa: ARG001
        return fake_oidc_config

    monkeypatch.setattr(sso_service, "_fetch_oidc_config", fake_fetch_oidc_config)
    monkeypatch.setattr(sso_service, "_verify_and_decode_id_token", fake_verify_id_token)
    monkeypatch.setattr(sso_service, "decrypt", lambda ct: "decrypted-secret")

    class FakeHttpxResponse:
        is_success = True
        text = ""

        def json(self):
            return fake_token_response

    class FakeHttpxClient:
        async def post(self, *args, **kwargs):
            return FakeHttpxResponse()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

    monkeypatch.setattr(
        sso_service.httpx, "AsyncClient", lambda **kwargs: FakeHttpxClient()
    )

    async def run():
        await redis.setex(f"sso_state:{state_key}", 600, state_data)
        return await sso_service.handle_sso_callback(
            db=db,
            redis=redis,
            code="authcode",
            state=state_key,
            redirect_uri="https://app.test/callback",
            base_url="OpenProxyAI",
        )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(run())

    assert exc_info.value.status_code == 400
    assert "nonce" in exc_info.value.detail.lower()


# ---------------------------------------------------------------------------
# Test: Non-admin list SSO connections -> 403
# ---------------------------------------------------------------------------


def test_list_sso_connections_non_admin_returns_403(client):
    dev = _developer_user()

    async def fake_current_user_dep():
        return dev

    async def fake_get_db():
        yield FakeDB()

    app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
    app.dependency_overrides[get_db] = fake_get_db

    response = client.get(
        "/api/v1/sso/connections",
        headers={"Authorization": "Bearer test"},
    )

    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Test: Non-admin delete SSO connection -> 403
# ---------------------------------------------------------------------------


def test_delete_sso_connection_non_admin_returns_403(client):
    dev = _developer_user()

    async def fake_current_user_dep():
        return dev

    async def fake_get_db():
        yield FakeDB()

    app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
    app.dependency_overrides[get_db] = fake_get_db

    response = client.delete(
        f"/api/v1/sso/connections/{uuid4()}",
        headers={"Authorization": "Bearer test"},
    )

    assert response.status_code == 403
