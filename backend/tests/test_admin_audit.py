"""Admin audit log tests — verify log_admin_action is called for every mutating admin action.

These tests follow the RED phase: they assert that routes call log_admin_action with
the correct `action` string. Before the implementation wires up log_admin_action, all
tests should FAIL. After wiring, all should PASS.
"""

from datetime import datetime, UTC
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.dependencies import get_current_user_from_jwt, get_db, get_redis
from app.main import app
from app.services.crypto_service import encrypt


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _admin_user(org_id=None):
    return SimpleNamespace(
        id=uuid4(),
        org_id=org_id or uuid4(),
        email="admin@example.com",
        name="Admin",
        role="admin",
        is_active=True,
    )


def _org(org_id, settings=None):
    return SimpleNamespace(
        id=org_id,
        name="AcmeCorp",
        slug="acmecorp",
        plan="starter",
        settings=settings or {},
        budget_monthly_usd=None,
        is_active=True,
        data_region="us",
        created_at=datetime.now(UTC),
    )


def _fake_key(org_id):
    key = SimpleNamespace(
        id=uuid4(),
        org_id=org_id,
        provider="openai",
        key_alias="my-key",
        api_key_encrypted=encrypt("sk-test1234"),
        weight=1,
        is_active=True,
        region="us",
        model_patterns=None,
        created_at=datetime.now(UTC),
    )
    return key


def _fake_user(org_id, role="developer"):
    return SimpleNamespace(
        id=uuid4(),
        org_id=org_id,
        email="dev@example.com",
        name="Dev",
        role=role,
        is_active=True,
        budget_daily_usd=None,
        budget_monthly_usd=None,
        created_at=datetime.now(UTC),
    )


def _fake_invite(org_id, email="invitee@example.com", role="developer"):
    return SimpleNamespace(
        id=uuid4(),
        org_id=org_id,
        email=email,
        role=role,
        invited_by=uuid4(),
        expires_at=datetime.now(UTC),
        accepted_at=None,
        created_at=datetime.now(UTC),
    )


class FakeDB:
    """Async DB stub that tracks add/commit calls."""

    @property
    def info(self) -> dict:
        # Mirrors AsyncSession.info (set_session_org_id stores the org there).
        return self.__dict__.setdefault("_info", {})


    def __init__(self, *, scalar_result=None, scalars_results=None, get_result=None):
        self.scalar_result = scalar_result
        self.scalars_results = list(scalars_results or [])
        self.get_result = get_result
        self.added = []
        self.deleted = []
        self.committed = False

    async def scalar(self, _stmt):
        return self.scalar_result

    async def scalars(self, _stmt):
        class _FakeScalarsResult:
            def __init__(self, rows):
                self._rows = rows

            def __iter__(self):
                return iter(self._rows)

        rows = self.scalars_results.pop(0) if self.scalars_results else []
        return _FakeScalarsResult(rows)

    async def get(self, model_cls, pk):  # noqa: ARG002
        return self.get_result

    def add(self, obj):
        self.added.append(obj)

    async def delete(self, obj):
        self.deleted.append(obj)

    async def flush(self):
        pass

    async def commit(self):
        self.committed = True

    async def refresh(self, obj):
        # Simulate DB assigning server-default fields after commit
        if getattr(obj, "id", None) is None:
            obj.id = uuid4()
        if getattr(obj, "created_at", None) is None:
            obj.created_at = datetime.now(UTC)

    async def execute(self, _stmt):
        # Return a simple result for count queries
        result = MagicMock()
        result.scalar_one = MagicMock(return_value=0)
        return result


class FakeRedis:
    async def get(self, _key):
        return None

    async def setex(self, *_args):
        return True

    async def delete(self, *_keys):
        return 1


# ---------------------------------------------------------------------------
# Test 1 — policy.updated
# ---------------------------------------------------------------------------


def test_policy_update_creates_audit_row(client, monkeypatch):
    """PATCH /current/policy should call log_admin_action with action='policy.updated'."""
    admin = _admin_user()
    org = _org(admin.org_id, settings={})
    fake_db = FakeDB(scalar_result=org, get_result=org)
    fake_redis = FakeRedis()

    async def fake_user_dep():
        return admin

    async def fake_db_dep():
        yield fake_db

    async def fake_redis_dep():
        return fake_redis

    app.dependency_overrides[get_current_user_from_jwt] = fake_user_dep
    app.dependency_overrides[get_db] = fake_db_dep
    app.dependency_overrides[get_redis] = fake_redis_dep

    with patch(
        "app.routes.organizations.log_admin_action", new_callable=AsyncMock
    ) as mock_log:
        response = client.patch(
            "/api/v1/organizations/current/policy",
            headers={"Authorization": "Bearer test"},
            json={"enforcement_mode": "log_only"},
        )

    assert response.status_code == 200, response.text
    mock_log.assert_called_once()
    call_kwargs = mock_log.call_args.kwargs
    assert call_kwargs["action"] == "policy.updated"
    assert call_kwargs["resource_type"] == "policy"


# ---------------------------------------------------------------------------
# Test 2 — webhook.updated (secret must NOT be in after)
# ---------------------------------------------------------------------------


def test_webhook_update_creates_audit_row(client, monkeypatch):
    """PATCH /current/webhooks should call log_admin_action and exclude secret from after."""
    admin = _admin_user()
    org = _org(
        admin.org_id,
        settings={"webhooks": {"url": "https://1.1.1.1/old", "secret": "s3cr3t", "events": [], "enabled": False}},
    )
    fake_db = FakeDB(get_result=org)

    async def fake_user_dep():
        return admin

    async def fake_db_dep():
        yield fake_db

    app.dependency_overrides[get_current_user_from_jwt] = fake_user_dep
    app.dependency_overrides[get_db] = fake_db_dep

    with patch(
        "app.routes.organizations.log_admin_action", new_callable=AsyncMock
    ) as mock_log:
        response = client.patch(
            "/api/v1/organizations/current/webhooks",
            headers={"Authorization": "Bearer test"},
            json={"url": "https://1.1.1.1/new", "secret": "newsecret", "events": ["policy.violation"], "enabled": True},
        )

    assert response.status_code == 200, response.text
    mock_log.assert_called_once()
    call_kwargs = mock_log.call_args.kwargs
    assert call_kwargs["action"] == "webhook.updated"
    # secret must not leak into the after snapshot
    after = call_kwargs.get("after", {})
    assert "secret" not in after


# ---------------------------------------------------------------------------
# Test 3 — provider_key.created
# ---------------------------------------------------------------------------


def test_provider_key_create_creates_audit_row(client):
    """POST /provider-keys/ should call log_admin_action with action='provider_key.created', before=None."""
    admin = _admin_user()
    fake_db = FakeDB()

    async def fake_user_dep():
        return admin

    async def fake_db_dep():
        yield fake_db

    app.dependency_overrides[get_current_user_from_jwt] = fake_user_dep
    app.dependency_overrides[get_db] = fake_db_dep

    with patch(
        "app.routes.provider_keys.log_admin_action", new_callable=AsyncMock
    ) as mock_log:
        response = client.post(
            "/api/v1/provider-keys",
            headers={"Authorization": "Bearer test"},
            json={"provider": "openai", "key_alias": "prod-key", "api_key": "sk-test1234", "weight": 1},
        )

    assert response.status_code == 201, response.text
    mock_log.assert_called_once()
    call_kwargs = mock_log.call_args.kwargs
    assert call_kwargs["action"] == "provider_key.created"
    assert call_kwargs["before"] is None


# ---------------------------------------------------------------------------
# Test 4 — provider_key.rotated
# ---------------------------------------------------------------------------


def test_provider_key_rotate_creates_audit_row(client):
    """POST /provider-keys/{id}/rotate should call log_admin_action with action='provider_key.rotated'."""
    admin = _admin_user()
    key = _fake_key(admin.org_id)
    fake_db = FakeDB(scalar_result=key)

    async def fake_user_dep():
        return admin

    async def fake_db_dep():
        yield fake_db

    app.dependency_overrides[get_current_user_from_jwt] = fake_user_dep
    app.dependency_overrides[get_db] = fake_db_dep

    with patch(
        "app.services.provider_key_service.log_admin_action", new_callable=AsyncMock
    ) as mock_log:
        response = client.post(
            f"/api/v1/provider-keys/{key.id}/rotate",
            headers={"Authorization": "Bearer test"},
        )

    assert response.status_code == 200, response.text
    mock_log.assert_called_once()
    call_kwargs = mock_log.call_args.kwargs
    assert call_kwargs["action"] == "provider_key.rotated"


# ---------------------------------------------------------------------------
# Test 5 — provider_key.deleted
# ---------------------------------------------------------------------------


def test_provider_key_delete_creates_audit_row(client):
    """DELETE /provider-keys/{id} should call log_admin_action with action='provider_key.deleted', after=None."""
    admin = _admin_user()
    key = _fake_key(admin.org_id)
    fake_db = FakeDB(scalar_result=key)

    async def fake_user_dep():
        return admin

    async def fake_db_dep():
        yield fake_db

    app.dependency_overrides[get_current_user_from_jwt] = fake_user_dep
    app.dependency_overrides[get_db] = fake_db_dep

    with patch(
        "app.routes.provider_keys.log_admin_action", new_callable=AsyncMock
    ) as mock_log:
        response = client.delete(
            f"/api/v1/provider-keys/{key.id}",
            headers={"Authorization": "Bearer test"},
        )

    assert response.status_code == 204, response.text
    mock_log.assert_called_once()
    call_kwargs = mock_log.call_args.kwargs
    assert call_kwargs["action"] == "provider_key.deleted"
    assert call_kwargs["after"] is None


# ---------------------------------------------------------------------------
# Test 6 — user.deactivated
# ---------------------------------------------------------------------------


def test_user_deactivation_creates_audit_row(client):
    """PATCH /users/{id} with is_active=False should produce action='user.deactivated'."""
    admin = _admin_user()
    target = _fake_user(admin.org_id, role="developer")
    fake_db = FakeDB(scalar_result=target, scalars_results=[[]])

    async def fake_user_dep():
        return admin

    async def fake_db_dep():
        yield fake_db

    app.dependency_overrides[get_current_user_from_jwt] = fake_user_dep
    app.dependency_overrides[get_db] = fake_db_dep

    with patch(
        "app.routes.users.log_admin_action", new_callable=AsyncMock
    ) as mock_log:
        response = client.patch(
            f"/api/v1/users/{target.id}",
            headers={"Authorization": "Bearer test"},
            json={"is_active": False},
        )

    assert response.status_code == 200, response.text
    mock_log.assert_called_once()
    call_kwargs = mock_log.call_args.kwargs
    assert call_kwargs["action"] == "user.deactivated"


# ---------------------------------------------------------------------------
# Test 7 — user.role_changed
# ---------------------------------------------------------------------------


def test_user_role_change_creates_audit_row(client):
    """PATCH /users/{id} with a role change should produce action='user.role_changed'."""
    admin = _admin_user()
    target = _fake_user(admin.org_id, role="developer")
    fake_db = FakeDB(scalar_result=target, scalars_results=[[]])

    async def fake_user_dep():
        return admin

    async def fake_db_dep():
        yield fake_db

    app.dependency_overrides[get_current_user_from_jwt] = fake_user_dep
    app.dependency_overrides[get_db] = fake_db_dep

    with patch(
        "app.routes.users.log_admin_action", new_callable=AsyncMock
    ) as mock_log:
        response = client.patch(
            f"/api/v1/users/{target.id}",
            headers={"Authorization": "Bearer test"},
            json={"role": "admin"},
        )

    assert response.status_code == 200, response.text
    mock_log.assert_called_once()
    call_kwargs = mock_log.call_args.kwargs
    assert call_kwargs["action"] == "user.role_changed"


# ---------------------------------------------------------------------------
# Test 8 — invite.sent
# ---------------------------------------------------------------------------


def test_invite_sent_creates_audit_row(client, monkeypatch):
    """POST /invites/ should call log_admin_action with action='invite.sent'."""
    admin = _admin_user()
    invite = _fake_invite(admin.org_id, email="newperson@example.com")
    fake_db = FakeDB(scalar_result=None)

    async def fake_user_dep():
        return admin

    async def fake_db_dep():
        yield fake_db

    app.dependency_overrides[get_current_user_from_jwt] = fake_user_dep
    app.dependency_overrides[get_db] = fake_db_dep

    # Stub invite_service.create_invite so it doesn't need a real DB
    async def fake_create_invite(db, org_id, email, role, invited_by_id, base_url="https://app.openproxyai.com"):
        return invite, "https://app.openproxyai.com/accept-invite?token=fake"

    monkeypatch.setattr("app.routes.invites.invite_service.create_invite", fake_create_invite)

    with patch(
        "app.routes.invites.log_admin_action", new_callable=AsyncMock
    ) as mock_log:
        response = client.post(
            "/api/v1/invites/",
            headers={"Authorization": "Bearer test"},
            json={"email": "newperson@example.com", "role": "developer"},
        )

    assert response.status_code == 201, response.text
    mock_log.assert_called_once()
    call_kwargs = mock_log.call_args.kwargs
    assert call_kwargs["action"] == "invite.sent"


# ---------------------------------------------------------------------------
# Test 9 — invite.revoked
# ---------------------------------------------------------------------------


def test_invite_revoked_creates_audit_row(client, monkeypatch):
    """DELETE /invites/{id} should call log_admin_action with action='invite.revoked'."""
    admin = _admin_user()
    invite = _fake_invite(admin.org_id, email="leaving@example.com")
    fake_db = FakeDB(scalar_result=invite)

    async def fake_user_dep():
        return admin

    async def fake_db_dep():
        yield fake_db

    app.dependency_overrides[get_current_user_from_jwt] = fake_user_dep
    app.dependency_overrides[get_db] = fake_db_dep

    # Stub invite_service.revoke_invite to avoid real DB
    async def fake_revoke_invite(db, org_id, invite_id):
        return True

    monkeypatch.setattr("app.routes.invites.invite_service.revoke_invite", fake_revoke_invite)

    with patch(
        "app.routes.invites.log_admin_action", new_callable=AsyncMock
    ) as mock_log:
        response = client.delete(
            f"/api/v1/invites/{invite.id}",
            headers={"Authorization": "Bearer test"},
        )

    assert response.status_code == 204, response.text
    mock_log.assert_called_once()
    call_kwargs = mock_log.call_args.kwargs
    assert call_kwargs["action"] == "invite.revoked"


# ---------------------------------------------------------------------------
# Test 10 — audit row is added before commit (same transaction)
# ---------------------------------------------------------------------------


def test_audit_row_not_committed_separately(client):
    """Verify db.add() is called before db.commit() — same transaction, no separate commit."""
    admin = _admin_user()
    target = _fake_user(admin.org_id, role="developer")

    call_order = []

    class TrackingDB(FakeDB):
        def add(self, obj):
            call_order.append(("add", type(obj).__name__))
            super().add(obj)

        async def commit(self):
            call_order.append(("commit", None))
            await super().commit()

    fake_db = TrackingDB(scalar_result=target)

    async def fake_user_dep():
        return admin

    async def fake_db_dep():
        yield fake_db

    app.dependency_overrides[get_current_user_from_jwt] = fake_user_dep
    app.dependency_overrides[get_db] = fake_db_dep

    response = client.patch(
        f"/api/v1/users/{target.id}",
        headers={"Authorization": "Bearer test"},
        json={"role": "admin"},
    )

    assert response.status_code == 200, response.text

    # db.add() must appear before db.commit()
    add_indices = [i for i, (op, _) in enumerate(call_order) if op == "add"]
    commit_indices = [i for i, (op, _) in enumerate(call_order) if op == "commit"]
    assert add_indices, "db.add() was never called"
    assert commit_indices, "db.commit() was never called"
    # The last add before commit must come before the first commit
    assert max(add_indices) < min(commit_indices), (
        f"Expected db.add() before db.commit(). Call order: {call_order}"
    )
    # Only one commit (atomic)
    assert len(commit_indices) == 1, f"Expected 1 commit, got {len(commit_indices)}: {call_order}"
