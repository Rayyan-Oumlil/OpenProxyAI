"""Auth endpoint tests — register, login, API key CRUD."""

from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.dependencies import get_current_user_from_jwt, get_db, get_redis
from app.main import app
from app.routes import api_keys as api_keys_routes
from app.routes import auth as auth_routes


class FakeScalarResult:
	def __init__(self, rows):
		self._rows = rows

	def __iter__(self):
		return iter(self._rows)


class FakeDB:
	def __init__(self, keys: list[SimpleNamespace] | None = None):
		self.keys = keys or []

	async def scalars(self, query):  # noqa: ARG002
		return FakeScalarResult(self.keys)

	async def get(self, model, key_id):  # noqa: ARG002
		for key in self.keys:
			if key.id == key_id:
				return key
		return None

	async def commit(self):
		return None


@pytest.fixture(autouse=True)
def clear_overrides():
	app.dependency_overrides.clear()
	yield
	app.dependency_overrides.clear()


def test_register_returns_tokens(client, fake_redis, monkeypatch):
	test_user = SimpleNamespace(id=uuid4(), org_id=uuid4(), role="admin")

	async def fake_create_user(**kwargs):  # noqa: ANN003
		return test_user

	async def fake_get_db():
		yield FakeDB()

	async def fake_get_redis():
		return fake_redis

	monkeypatch.setattr(auth_routes, "create_user", fake_create_user)
	app.dependency_overrides[get_db] = fake_get_db
	app.dependency_overrides[get_redis] = fake_get_redis

	response = client.post(
		"/api/v1/auth/register",
		json={
			"email": "admin@test.com",
			"password": "testpass123",
			"name": "Admin",
			"org_name": "TestOrg",
		},
	)

	assert response.status_code == 200
	data = response.json()
	assert data["token_type"] == "bearer"
	assert data["expires_in"] == 86400
	assert data["access_token"]
	assert data["refresh_token"]


def test_login_returns_tokens(client, fake_redis, monkeypatch):
	test_user = SimpleNamespace(id=uuid4(), org_id=uuid4(), role="developer")

	async def fake_authenticate_user(**kwargs):  # noqa: ANN003
		return test_user

	async def fake_get_db():
		yield FakeDB()

	async def fake_get_redis():
		return fake_redis

	monkeypatch.setattr(auth_routes, "authenticate_user", fake_authenticate_user)
	app.dependency_overrides[get_db] = fake_get_db
	app.dependency_overrides[get_redis] = fake_get_redis

	response = client.post(
		"/api/v1/auth/login",
		json={"email": "admin@test.com", "password": "testpass123"},
	)

	assert response.status_code == 200
	data = response.json()
	assert data["token_type"] == "bearer"
	assert data["access_token"]
	assert data["refresh_token"]


def test_me_returns_current_user(client):
	current_user = SimpleNamespace(
		id=uuid4(),
		org_id=uuid4(),
		email="admin@test.com",
		name="Admin",
		role="admin",
		is_active=True,
	)

	async def fake_current_user_dep():
		return current_user

	app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep

	response = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer test"})
	assert response.status_code == 200
	data = response.json()
	assert data["email"] == "admin@test.com"
	assert data["role"] == "admin"


def test_refresh_and_logout_blocklist(client, fake_redis):
	refresh_payload = {
		"sub": str(uuid4()),
		"org_id": str(uuid4()),
		"role": "admin",
	}

	async def fake_verify_refresh_token(token, redis=None):  # noqa: ANN001
		return refresh_payload

	monkeypatch = pytest.MonkeyPatch()
	monkeypatch.setattr(auth_routes, "verify_refresh_token", fake_verify_refresh_token)

	async def fake_get_redis():
		return fake_redis

	app.dependency_overrides[get_redis] = fake_get_redis

	refresh_res = client.post("/api/v1/auth/refresh", headers={"Authorization": "Bearer rtok"})
	assert refresh_res.status_code == 200
	refresh_data = refresh_res.json()
	assert refresh_data["access_token"]
	assert refresh_data["refresh_token"]

	logout_res = client.post("/api/v1/auth/logout", headers={"Authorization": "Bearer atok"})
	assert logout_res.status_code == 200
	assert logout_res.json()["status"] == "logged_out"
	monkeypatch.undo()


def test_api_key_create_list_revoke(client, monkeypatch):
	user = SimpleNamespace(
		id=uuid4(),
		org_id=uuid4(),
		email="admin@test.com",
		name="Admin",
		role="admin",
		is_active=True,
	)
	model = SimpleNamespace(
		id=uuid4(),
		name="My Dev Key",
		key_prefix="opai_dev_abcd1234_",
		permissions=["proxy:llm"],
		is_active=True,
		expires_at=None,
		created_at=datetime.utcnow(),
		org_id=user.org_id,
	)

	async def fake_current_user_dep():
		return user

	async def fake_get_db():
		yield FakeDB(keys=[model])

	async def fake_create_api_key(**kwargs):  # noqa: ANN003
		return model, "opai_dev_abcd1234_deadbeefdeadbeefdeadbeefabcd"

	monkeypatch.setattr(api_keys_routes, "create_api_key", fake_create_api_key)
	app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
	app.dependency_overrides[get_db] = fake_get_db

	create_res = client.post(
		"/api/v1/api-keys",
		headers={"Authorization": "Bearer token"},
		json={"name": "My Dev Key"},
	)
	assert create_res.status_code == 201
	create_data = create_res.json()
	assert create_data["key"].startswith("opai_dev_")

	list_res = client.get("/api/v1/api-keys", headers={"Authorization": "Bearer token"})
	assert list_res.status_code == 200
	list_data = list_res.json()
	assert len(list_data) == 1
	assert "key" not in list_data[0]

	revoke_res = client.delete(
		f"/api/v1/api-keys/{model.id}",
		headers={"Authorization": "Bearer token"},
	)
	assert revoke_res.status_code == 204


def test_me_requires_auth_token(client):
	response = client.get("/api/v1/auth/me")
	assert response.status_code == 401


def test_refresh_requires_auth_token(client):
	response = client.post("/api/v1/auth/refresh")
	assert response.status_code == 401

