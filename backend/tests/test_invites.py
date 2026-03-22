"""Invite endpoint tests — create, list, revoke, accept-invite flows."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.dependencies import get_current_user_from_jwt, get_db, get_redis
from app.main import app
from app.routes import invites as invite_routes
from app.routes import auth as auth_routes
from app.services import invite_service


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class FakeScalarResult:
    def __init__(self, rows):
        self._rows = rows

    def __iter__(self):
        return iter(self._rows)


class FakeDB:
    """Minimal async DB stub used across invite tests."""

    def __init__(
        self,
        *,
        scalar_result=None,
        scalars_results=None,
    ):
        self.scalar_result = scalar_result
        self.scalars_results = scalars_results or []
        self.added = []
        self.deleted = []
        self.committed = False
        self.flushed = False
        self._refresh_target = None

    async def scalar(self, query):  # noqa: ARG002
        return self.scalar_result

    async def scalars(self, query):  # noqa: ARG002
        rows = self.scalars_results.pop(0) if self.scalars_results else []
        return FakeScalarResult(rows)

    def add(self, model):
        self.added.append(model)

    async def delete(self, model):
        self.deleted.append(model)

    async def flush(self):
        self.flushed = True

    async def commit(self):
        self.committed = True

    async def refresh(self, model):
        self._refresh_target = model


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


def _invite(
    *,
    org_id,
    invited_by=None,
    accepted_at=None,
    expires_at=None,
    role="developer",
):
    # Use naive UTC to match DB timestamp columns and invite_service comparisons
    now = datetime.now(UTC).replace(tzinfo=None)
    return SimpleNamespace(
        id=uuid4(),
        org_id=org_id,
        email="newuser@test.com",
        role=role,
        token_hash="fakehash",
        invited_by=invited_by or uuid4(),
        expires_at=expires_at or (now + timedelta(days=7)),
        accepted_at=accepted_at,
        created_at=now,
    )


def _user_from_invite(invite):
    return SimpleNamespace(
        id=uuid4(),
        org_id=invite.org_id,
        email=invite.email,
        name="New User",
        role=invite.role,
        is_active=True,
        created_at=datetime.now(UTC).replace(tzinfo=None),
        budget_daily_usd=None,
        budget_monthly_usd=None,
    )


# ---------------------------------------------------------------------------
# Test: Admin creates an invite
# ---------------------------------------------------------------------------

def test_create_invite_returns_invite_url(client, monkeypatch):
    admin = _admin_user()
    invite = _invite(org_id=admin.org_id, invited_by=admin.id)
    raw_token = "rawtoken123"

    async def fake_create_invite(**kwargs):  # noqa: ANN003
        return invite, f"https://app.openproxyai.com/accept-invite?token={raw_token}"

    async def fake_current_user_dep():
        return admin

    async def fake_get_db():
        yield FakeDB()

    monkeypatch.setattr(invite_routes.invite_service, "create_invite", fake_create_invite)
    app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
    app.dependency_overrides[get_db] = fake_get_db

    response = client.post(
        "/api/v1/invites/",
        headers={"Authorization": "Bearer test"},
        json={"email": "newuser@test.com", "role": "developer"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "newuser@test.com"
    assert data["role"] == "developer"
    assert "invite_url" in data
    assert raw_token in data["invite_url"]


# ---------------------------------------------------------------------------
# Test: List pending invites returns only valid ones
# ---------------------------------------------------------------------------

def test_list_pending_invites_returns_active_only(client, monkeypatch):
    admin = _admin_user()
    pending = _invite(org_id=admin.org_id)

    async def fake_get_pending(db, org_id):  # noqa: ARG001
        return [pending]

    async def fake_current_user_dep():
        return admin

    async def fake_get_db():
        yield FakeDB()

    monkeypatch.setattr(invite_routes.invite_service, "get_pending_invites", fake_get_pending)
    app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
    app.dependency_overrides[get_db] = fake_get_db

    response = client.get(
        "/api/v1/invites/",
        headers={"Authorization": "Bearer test"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["email"] == "newuser@test.com"
    assert data[0]["accepted_at"] is None


# ---------------------------------------------------------------------------
# Test: Revoke invite → 204
# ---------------------------------------------------------------------------

def test_revoke_invite_returns_204(client, monkeypatch):
    admin = _admin_user()
    invite_id = uuid4()
    invite = _invite(org_id=admin.org_id)
    invite.id = invite_id

    async def fake_revoke(db, org_id, invite_id):  # noqa: ARG001
        return True

    async def fake_current_user_dep():
        return admin

    async def fake_get_db():
        yield FakeDB(scalar_result=invite)

    monkeypatch.setattr(invite_routes.invite_service, "revoke_invite", fake_revoke)
    app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
    app.dependency_overrides[get_db] = fake_get_db

    response = client.delete(
        f"/api/v1/invites/{invite_id}",
        headers={"Authorization": "Bearer test"},
    )

    assert response.status_code == 204


# ---------------------------------------------------------------------------
# Test: Revoke invite → 404 when not found
# ---------------------------------------------------------------------------

def test_revoke_invite_not_found_returns_404(client, monkeypatch):
    admin = _admin_user()
    invite_id = uuid4()

    async def fake_revoke(db, org_id, invite_id):  # noqa: ARG001
        return False

    async def fake_current_user_dep():
        return admin

    async def fake_get_db():
        yield FakeDB()

    monkeypatch.setattr(invite_routes.invite_service, "revoke_invite", fake_revoke)
    app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
    app.dependency_overrides[get_db] = fake_get_db

    response = client.delete(
        f"/api/v1/invites/{invite_id}",
        headers={"Authorization": "Bearer test"},
    )

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Test: Accept invite creates user and returns tokens
# ---------------------------------------------------------------------------

def test_accept_invite_creates_user_and_returns_tokens(client, fake_redis, monkeypatch):
    admin = _admin_user()
    invite = _invite(org_id=admin.org_id)
    new_user = _user_from_invite(invite)

    async def fake_accept_invite(db, token, name, password):  # noqa: ARG001
        return new_user

    async def fake_get_db():
        yield FakeDB()

    async def fake_get_redis():
        return fake_redis

    monkeypatch.setattr(auth_routes.invite_service, "accept_invite", fake_accept_invite)
    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_redis] = fake_get_redis

    response = client.post(
        "/api/v1/auth/accept-invite",
        json={"token": "validtoken", "name": "New User", "password": "securepass123"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["token_type"] == "bearer"
    assert data["access_token"]
    assert data["refresh_token"]
    assert data["expires_in"] > 0


# ---------------------------------------------------------------------------
# Test: Accept expired token → 410
# ---------------------------------------------------------------------------

def test_accept_expired_invite_returns_410(client, fake_redis, monkeypatch):
    from fastapi import HTTPException, status

    async def fake_accept_invite(db, token, name, password):  # noqa: ARG001
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Invite has expired",
        )

    async def fake_get_db():
        yield FakeDB()

    async def fake_get_redis():
        return fake_redis

    monkeypatch.setattr(auth_routes.invite_service, "accept_invite", fake_accept_invite)
    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_redis] = fake_get_redis

    response = client.post(
        "/api/v1/auth/accept-invite",
        json={"token": "expiredtoken", "name": "Bob", "password": "securepass123"},
    )

    assert response.status_code == 410
    assert "expired" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Test: Accept already-accepted token → 409
# ---------------------------------------------------------------------------

def test_accept_already_accepted_invite_returns_409(client, fake_redis, monkeypatch):
    from fastapi import HTTPException, status

    async def fake_accept_invite(db, token, name, password):  # noqa: ARG001
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Invite already accepted",
        )

    async def fake_get_db():
        yield FakeDB()

    async def fake_get_redis():
        return fake_redis

    monkeypatch.setattr(auth_routes.invite_service, "accept_invite", fake_accept_invite)
    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_redis] = fake_get_redis

    response = client.post(
        "/api/v1/auth/accept-invite",
        json={"token": "usedtoken", "name": "Bob", "password": "securepass123"},
    )

    assert response.status_code == 409
    assert "already accepted" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Test: Accept non-existent token → 404
# ---------------------------------------------------------------------------

def test_accept_nonexistent_invite_returns_404(client, fake_redis, monkeypatch):
    from fastapi import HTTPException, status

    async def fake_accept_invite(db, token, name, password):  # noqa: ARG001
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invite not found",
        )

    async def fake_get_db():
        yield FakeDB()

    async def fake_get_redis():
        return fake_redis

    monkeypatch.setattr(auth_routes.invite_service, "accept_invite", fake_accept_invite)
    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_redis] = fake_get_redis

    response = client.post(
        "/api/v1/auth/accept-invite",
        json={"token": "nosuchtoken", "name": "Bob", "password": "securepass123"},
    )

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Test: Non-admin trying to create invite → 403
# ---------------------------------------------------------------------------

def test_non_admin_create_invite_returns_403(client, monkeypatch):
    dev = _developer_user()

    async def fake_current_user_dep():
        return dev

    async def fake_get_db():
        yield FakeDB()

    app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
    app.dependency_overrides[get_db] = fake_get_db

    response = client.post(
        "/api/v1/invites/",
        headers={"Authorization": "Bearer test"},
        json={"email": "newuser@test.com", "role": "developer"},
    )

    assert response.status_code == 403
    assert "admin" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Test: Non-admin trying to list invites → 403
# ---------------------------------------------------------------------------

def test_non_admin_list_invites_returns_403(client):
    dev = _developer_user()

    async def fake_current_user_dep():
        return dev

    async def fake_get_db():
        yield FakeDB()

    app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
    app.dependency_overrides[get_db] = fake_get_db

    response = client.get(
        "/api/v1/invites/",
        headers={"Authorization": "Bearer test"},
    )

    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Test: Double-accept same invite → 409 (unit test of service logic)
# ---------------------------------------------------------------------------

def test_double_accept_same_invite_raises_409(monkeypatch):
    """
    Simulates the service layer being called twice with an already-accepted invite.
    The second call should raise HTTP 409 because accepted_at is set.
    """
    import asyncio
    from fastapi import HTTPException

    # Naive UTC to match invite_service's now (DB timestamp columns)
    now_naive = datetime.now(UTC).replace(tzinfo=None)
    past = now_naive - timedelta(hours=1)
    future = now_naive + timedelta(days=6)
    already_accepted = SimpleNamespace(
        id=uuid4(),
        org_id=uuid4(),
        email="already@test.com",
        role="developer",
        token_hash="somehash",
        invited_by=uuid4(),
        expires_at=future,
        accepted_at=past,  # already accepted
    )

    db = FakeDB(scalar_result=already_accepted)

    async def run():
        return await invite_service.accept_invite(
            db=db,
            token="sometoken",
            name="Alice",
            password="securepass123",
        )

    # Patch _hash_token so it matches without needing real SHA-256
    monkeypatch.setattr(invite_service, "_hash_token", lambda t: "somehash")

    with pytest.raises(HTTPException) as exc_info:
        asyncio.get_event_loop().run_until_complete(run())

    assert exc_info.value.status_code == 409
    assert "already accepted" in exc_info.value.detail.lower()


# ---------------------------------------------------------------------------
# Test: accept_invite service raises 410 for expired invite
# ---------------------------------------------------------------------------

def test_accept_invite_service_raises_410_for_expired(monkeypatch):
    """Service layer raises 410 directly when expires_at is in the past."""
    import asyncio
    from fastapi import HTTPException

    past_expiry = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=1)
    expired_invite = SimpleNamespace(
        id=uuid4(),
        org_id=uuid4(),
        email="expired@test.com",
        role="developer",
        token_hash="expiredhash",
        invited_by=uuid4(),
        expires_at=past_expiry,
        accepted_at=None,
    )

    db = FakeDB(scalar_result=expired_invite)

    async def run():
        return await invite_service.accept_invite(
            db=db,
            token="sometoken",
            name="Alice",
            password="securepass123",
        )

    monkeypatch.setattr(invite_service, "_hash_token", lambda t: "expiredhash")

    with pytest.raises(HTTPException) as exc_info:
        asyncio.get_event_loop().run_until_complete(run())

    assert exc_info.value.status_code == 410
    assert "expired" in exc_info.value.detail.lower()


# ---------------------------------------------------------------------------
# Test: accept_invite service raises 404 when token not found
# ---------------------------------------------------------------------------

def test_accept_invite_service_raises_404_for_missing_token(monkeypatch):
    """Service layer raises 404 when no invite matches the token hash."""
    import asyncio
    from fastapi import HTTPException

    db = FakeDB(scalar_result=None)

    async def run():
        return await invite_service.accept_invite(
            db=db,
            token="nosuchtoken",
            name="Alice",
            password="securepass123",
        )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.get_event_loop().run_until_complete(run())

    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# Test: revoke then confirm not in list
# ---------------------------------------------------------------------------

def test_revoke_invite_then_not_in_list(client, monkeypatch):
    admin = _admin_user()
    invite_id = uuid4()
    invite = _invite(org_id=admin.org_id)
    invite.id = invite_id

    revoked_ids: set = set()

    async def fake_revoke(db, org_id, invite_id):  # noqa: ARG001
        revoked_ids.add(invite_id)
        return True

    async def fake_get_pending(db, org_id):  # noqa: ARG001
        return [i for i in [invite] if i.id not in revoked_ids]

    async def fake_current_user_dep():
        return admin

    async def fake_get_db():
        # The DELETE route does db.scalar() to look up the invite before delegating to the service.
        # Yield a DB that returns the invite for the scalar() lookup.
        yield FakeDB(scalar_result=invite)

    monkeypatch.setattr(invite_routes.invite_service, "revoke_invite", fake_revoke)
    monkeypatch.setattr(invite_routes.invite_service, "get_pending_invites", fake_get_pending)
    app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
    app.dependency_overrides[get_db] = fake_get_db

    # Confirm invite is in the list before revocation
    list_before = client.get("/api/v1/invites/", headers={"Authorization": "Bearer test"})
    assert list_before.status_code == 200
    assert len(list_before.json()) == 1

    # Revoke the invite
    revoke_res = client.delete(
        f"/api/v1/invites/{invite_id}",
        headers={"Authorization": "Bearer test"},
    )
    assert revoke_res.status_code == 204

    # Confirm it is no longer in the list
    list_after = client.get("/api/v1/invites/", headers={"Authorization": "Bearer test"})
    assert list_after.status_code == 200
    assert len(list_after.json()) == 0


# ---------------------------------------------------------------------------
# Test: accept invite — user appears in GET /users
# ---------------------------------------------------------------------------

def test_accepted_user_appears_in_users_list(client, fake_redis, monkeypatch):
    admin = _admin_user()
    invite = _invite(org_id=admin.org_id)
    new_user = _user_from_invite(invite)

    async def fake_accept_invite(db, token, name, password):  # noqa: ARG001
        return new_user

    async def fake_current_user_dep():
        return admin

    async def fake_get_db():
        yield FakeDB()

    async def fake_get_redis():
        return fake_redis

    monkeypatch.setattr(auth_routes.invite_service, "accept_invite", fake_accept_invite)
    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_redis] = fake_get_redis

    accept_res = client.post(
        "/api/v1/auth/accept-invite",
        json={"token": "validtoken", "name": "New User", "password": "securepass123"},
    )
    assert accept_res.status_code == 200

    # Now simulate GET /users finding that new user

    async def fake_list_db():
        yield FakeDB(scalars_results=[[new_user]])

    app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
    app.dependency_overrides[get_db] = fake_list_db

    users_res = client.get("/api/v1/users", headers={"Authorization": "Bearer test"})
    assert users_res.status_code == 200
    user_emails = [u["email"] for u in users_res.json()]
    assert new_user.email in user_emails
