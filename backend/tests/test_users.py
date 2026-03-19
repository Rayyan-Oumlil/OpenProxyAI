"""User management route tests — list, get, update, RBAC, edge cases."""

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from app.dependencies import get_current_user_from_jwt, get_db
from app.main import app
from app.services import admin_audit_service as audit_module


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class FakeScalarResult:
	def __init__(self, items):
		self._items = items

	def __iter__(self):
		return iter(self._items)


class FakeDB:
	def __init__(self, *, scalars_result=None, scalar_result=None):
		self._scalars_result = scalars_result
		self._scalar_result = scalar_result
		self.committed = False
		self.added = []

	async def scalars(self, *args, **kwargs):
		return FakeScalarResult(self._scalars_result or [])

	async def scalar(self, *args, **kwargs):
		return self._scalar_result

	async def commit(self):
		self.committed = True

	async def refresh(self, obj):
		pass

	def add(self, obj):
		self.added.append(obj)


def _make_user_model(org_id, *, user_id=None, role="admin", email="admin@test.com", is_active=True):
	return SimpleNamespace(
		id=user_id or uuid4(),
		org_id=org_id,
		email=email,
		name="Test User",
		role=role,
		budget_daily_usd=None,
		budget_monthly_usd=None,
		is_active=is_active,
		created_at=datetime.now(UTC),
	)


def _override_auth(user):
	async def dep():
		return user
	app.dependency_overrides[get_current_user_from_jwt] = dep


def _override_db(db_instance):
	async def dep():
		yield db_instance
	app.dependency_overrides[get_db] = dep


def _noop_audit(monkeypatch):
	async def noop_log(*args, **kwargs):
		return SimpleNamespace(id=uuid4())

	monkeypatch.setattr(audit_module, "log_admin_action", noop_log)
	monkeypatch.setattr(audit_module, "serialize_user", lambda u: {})


# ---------------------------------------------------------------------------
# GET /api/v1/users — list users
# ---------------------------------------------------------------------------


def test_list_users_success(client):
	org_id = uuid4()
	current_user = _make_user_model(org_id)
	users = [
		_make_user_model(org_id, email="a@test.com"),
		_make_user_model(org_id, email="b@test.com", role="developer"),
	]

	_override_auth(current_user)
	_override_db(FakeDB(scalars_result=users))

	response = client.get("/api/v1/users", headers={"Authorization": "Bearer test"})
	assert response.status_code == 200
	data = response.json()
	assert len(data) == 2
	assert data[0]["email"] == "a@test.com"
	assert data[1]["role"] == "developer"


def test_list_users_empty(client):
	org_id = uuid4()
	current_user = _make_user_model(org_id)

	_override_auth(current_user)
	_override_db(FakeDB(scalars_result=[]))

	response = client.get("/api/v1/users", headers={"Authorization": "Bearer test"})
	assert response.status_code == 200
	assert response.json() == []


def test_list_users_requires_auth(client):
	response = client.get("/api/v1/users")
	assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/v1/users/{user_id} — get single user
# ---------------------------------------------------------------------------


def test_get_user_success(client):
	org_id = uuid4()
	current_user = _make_user_model(org_id)
	target_user = _make_user_model(org_id, email="target@test.com", role="developer")

	_override_auth(current_user)
	_override_db(FakeDB(scalar_result=target_user))

	response = client.get(
		f"/api/v1/users/{target_user.id}",
		headers={"Authorization": "Bearer test"},
	)
	assert response.status_code == 200
	data = response.json()
	assert data["email"] == "target@test.com"
	assert data["role"] == "developer"


def test_get_user_not_found(client):
	org_id = uuid4()
	current_user = _make_user_model(org_id)

	_override_auth(current_user)
	_override_db(FakeDB(scalar_result=None))

	response = client.get(
		f"/api/v1/users/{uuid4()}",
		headers={"Authorization": "Bearer test"},
	)
	assert response.status_code == 404
	assert response.json()["detail"] == "User not found"


def test_get_user_requires_auth(client):
	response = client.get(f"/api/v1/users/{uuid4()}")
	assert response.status_code == 401


# ---------------------------------------------------------------------------
# PATCH /api/v1/users/{user_id} — update user (admin only)
# ---------------------------------------------------------------------------


def test_update_user_success(client, monkeypatch):
	org_id = uuid4()
	admin = _make_user_model(org_id, role="admin")
	target = _make_user_model(org_id, role="developer", email="dev@test.com")

	_noop_audit(monkeypatch)
	_override_auth(admin)

	class PatchDB(FakeDB):
		async def scalar(self, *args, **kwargs):
			return target

		async def scalars(self, *args, **kwargs):
			return FakeScalarResult([admin.id])

	_override_db(PatchDB())

	response = client.patch(
		f"/api/v1/users/{target.id}",
		json={"name": "New Name"},
		headers={"Authorization": "Bearer test"},
	)
	assert response.status_code == 200
	assert target.name == "New Name"


def test_update_user_role_change(client, monkeypatch):
	org_id = uuid4()
	admin = _make_user_model(org_id, role="admin")
	target = _make_user_model(org_id, role="developer", email="dev@test.com")

	_noop_audit(monkeypatch)
	_override_auth(admin)

	class PatchDB(FakeDB):
		async def scalar(self, *args, **kwargs):
			return target

		async def scalars(self, *args, **kwargs):
			return FakeScalarResult([admin.id, target.id])

	_override_db(PatchDB())

	response = client.patch(
		f"/api/v1/users/{target.id}",
		json={"role": "viewer"},
		headers={"Authorization": "Bearer test"},
	)
	assert response.status_code == 200
	assert target.role == "viewer"


def test_update_user_forbidden_non_admin(client):
	org_id = uuid4()
	viewer = _make_user_model(org_id, role="viewer")

	_override_auth(viewer)
	_override_db(FakeDB())

	response = client.patch(
		f"/api/v1/users/{uuid4()}",
		json={"name": "Nope"},
		headers={"Authorization": "Bearer test"},
	)
	assert response.status_code == 403
	assert response.json()["detail"] == "Forbidden"


def test_update_user_not_found(client, monkeypatch):
	org_id = uuid4()
	admin = _make_user_model(org_id, role="admin")

	_noop_audit(monkeypatch)
	_override_auth(admin)
	_override_db(FakeDB(scalar_result=None))

	response = client.patch(
		f"/api/v1/users/{uuid4()}",
		json={"name": "Ghost"},
		headers={"Authorization": "Bearer test"},
	)
	assert response.status_code == 404
	assert response.json()["detail"] == "User not found"


def test_update_user_requires_auth(client):
	response = client.patch(f"/api/v1/users/{uuid4()}", json={"name": "x"})
	assert response.status_code == 401


# ---------------------------------------------------------------------------
# 400 — cannot remove own admin access
# ---------------------------------------------------------------------------


def test_update_user_cannot_remove_own_admin(client, monkeypatch):
	org_id = uuid4()
	admin_id = uuid4()
	admin = _make_user_model(org_id, user_id=admin_id, role="admin")

	_noop_audit(monkeypatch)
	_override_auth(admin)

	class SelfDB(FakeDB):
		async def scalar(self, *args, **kwargs):
			return admin

	_override_db(SelfDB())

	response = client.patch(
		f"/api/v1/users/{admin_id}",
		json={"role": "developer"},
		headers={"Authorization": "Bearer test"},
	)
	assert response.status_code == 400
	assert "Cannot remove your own active admin access" in response.json()["detail"]


def test_update_user_cannot_deactivate_self(client, monkeypatch):
	org_id = uuid4()
	admin_id = uuid4()
	admin = _make_user_model(org_id, user_id=admin_id, role="admin")

	_noop_audit(monkeypatch)
	_override_auth(admin)

	class SelfDB(FakeDB):
		async def scalar(self, *args, **kwargs):
			return admin

	_override_db(SelfDB())

	response = client.patch(
		f"/api/v1/users/{admin_id}",
		json={"is_active": False},
		headers={"Authorization": "Bearer test"},
	)
	assert response.status_code == 400
	assert "Cannot remove your own active admin access" in response.json()["detail"]


# ---------------------------------------------------------------------------
# 400 — cannot remove last admin
# ---------------------------------------------------------------------------


def test_update_user_cannot_remove_last_admin(client, monkeypatch):
	org_id = uuid4()
	admin = _make_user_model(org_id, role="admin")
	target_id = uuid4()
	target = _make_user_model(org_id, user_id=target_id, role="admin", email="last@test.com")

	_noop_audit(monkeypatch)
	_override_auth(admin)

	class LastAdminDB(FakeDB):
		async def scalar(self, *args, **kwargs):
			return target

		async def scalars(self, *args, **kwargs):
			return FakeScalarResult([target_id])

	_override_db(LastAdminDB())

	response = client.patch(
		f"/api/v1/users/{target_id}",
		json={"role": "developer"},
		headers={"Authorization": "Bearer test"},
	)
	assert response.status_code == 400
	assert "last active admin" in response.json()["detail"]


def test_update_user_allows_demote_when_other_admins_exist(client, monkeypatch):
	org_id = uuid4()
	admin = _make_user_model(org_id, role="admin")
	target_id = uuid4()
	target = _make_user_model(org_id, user_id=target_id, role="admin", email="extra@test.com")
	other_admin_id = uuid4()

	_noop_audit(monkeypatch)
	_override_auth(admin)

	class MultiAdminDB(FakeDB):
		async def scalar(self, *args, **kwargs):
			return target

		async def scalars(self, *args, **kwargs):
			return FakeScalarResult([target_id, other_admin_id])

	_override_db(MultiAdminDB())

	response = client.patch(
		f"/api/v1/users/{target_id}",
		json={"role": "developer"},
		headers={"Authorization": "Bearer test"},
	)
	assert response.status_code == 200
	assert target.role == "developer"
