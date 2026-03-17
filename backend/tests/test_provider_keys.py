"""Provider key management API tests — CRUD, masking, and org isolation."""

from datetime import datetime, UTC
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.dependencies import get_current_user_from_jwt, get_db
from app.main import app
from app.services.crypto_service import encrypt


class FakeKey:
	"""Minimal LLMProviderKey ORM model substitute."""

	def __init__(self, org_id, provider, key_alias, api_key_encrypted, weight=1, is_active=True):
		self.id = uuid4()
		self.org_id = org_id
		self.provider = provider
		self.key_alias = key_alias
		self.api_key_encrypted = api_key_encrypted
		self.weight = weight
		self.is_active = is_active
		self.model_patterns = None
		self.created_at = datetime.now(UTC)


class FakeScalarsResult:
	def __init__(self, items):
		self._items = items

	def __iter__(self):
		return iter(self._items)


class FakeDB:
	def __init__(self, keys=None):
		self._keys: list[FakeKey] = keys or []
		self._added: list = []
		self._deleted: list = []

	async def scalars(self, _stmt):
		return FakeScalarsResult(self._keys)

	async def scalar(self, _stmt):
		return self._keys[0] if self._keys else None

	def add(self, obj):
		self._added.append(obj)
		self._keys.append(obj)

	async def delete(self, obj):
		self._deleted.append(obj)

	async def commit(self):
		pass

	async def refresh(self, obj):
		# Simulate DB setting server-default fields
		if getattr(obj, "id", None) is None:
			obj.id = uuid4()
		if getattr(obj, "created_at", None) is None:
			obj.created_at = datetime.now(UTC)


# ── Auth guard ───────────────────────────────────────────────────────────────


def test_list_requires_auth(client):
	response = client.get("/api/v1/provider-keys")
	assert response.status_code == 401


def test_create_requires_auth(client):
	response = client.post("/api/v1/provider-keys", json={})
	assert response.status_code == 401


# ── LIST ─────────────────────────────────────────────────────────────────────


def test_list_returns_masked_keys(client, monkeypatch):
	org_id = uuid4()
	user = SimpleNamespace(id=uuid4(), org_id=org_id, role="admin", is_active=True)
	raw_key = "sk-openai-super-secret-key-1234"
	fake_key = FakeKey(org_id, "openai", "production", encrypt(raw_key))

	async def fake_current_user_dep():
		return user

	async def fake_get_db():
		yield FakeDB(keys=[fake_key])

	app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
	app.dependency_overrides[get_db] = fake_get_db

	response = client.get("/api/v1/provider-keys", headers={"Authorization": "Bearer test"})

	assert response.status_code == 200
	data = response.json()
	assert len(data) == 1
	item = data[0]
	assert item["provider"] == "openai"
	assert item["key_alias"] == "production"
	# Raw key must NOT appear in response
	assert raw_key not in str(data)
	# Prefix should be first 8 chars + ellipsis
	assert item["key_prefix"] == raw_key[:8] + "…"
	assert "api_key" not in item


# ── CREATE ───────────────────────────────────────────────────────────────────


def test_create_non_admin_gets_403(client, monkeypatch):
	org_id = uuid4()
	user = SimpleNamespace(id=uuid4(), org_id=org_id, role="member", is_active=True)

	async def fake_current_user_dep():
		return user

	async def fake_get_db():
		yield FakeDB()

	app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
	app.dependency_overrides[get_db] = fake_get_db

	response = client.post(
		"/api/v1/provider-keys",
		json={"provider": "openai", "key_alias": "test", "api_key": "sk-test-key-12345"},
		headers={"Authorization": "Bearer test"},
	)
	assert response.status_code == 403


def test_create_stores_encrypted_returns_masked(client, monkeypatch):
	org_id = uuid4()
	user = SimpleNamespace(id=uuid4(), org_id=org_id, role="admin", is_active=True, email="admin@test.com")
	db = FakeDB()
	raw_key = "sk-ant-api03-supersecretkey1234"

	async def fake_current_user_dep():
		return user

	async def fake_get_db():
		yield db

	app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
	app.dependency_overrides[get_db] = fake_get_db

	response = client.post(
		"/api/v1/provider-keys",
		json={"provider": "anthropic", "key_alias": "staging", "api_key": raw_key, "weight": 2},
		headers={"Authorization": "Bearer test"},
	)

	assert response.status_code == 201
	data = response.json()
	assert data["provider"] == "anthropic"
	assert data["key_alias"] == "staging"
	assert data["weight"] == 2
	assert data["is_active"] is True
	# Prefix check
	assert data["key_prefix"] == raw_key[:8] + "…"
	# Raw key must never appear
	assert raw_key not in str(data)
	# DB should have received an encrypted value (not the raw key)
	# _added[0] is the LLMProviderKey; _added[1] is the AdminAuditLog entry
	assert len(db._added) >= 1
	stored_encrypted = db._added[0].api_key_encrypted
	assert stored_encrypted != raw_key
	# But we can decrypt it back
	from app.services.crypto_service import decrypt
	assert decrypt(stored_encrypted) == raw_key


# ── PATCH ────────────────────────────────────────────────────────────────────


def test_update_non_admin_gets_403(client, monkeypatch):
	org_id = uuid4()
	user = SimpleNamespace(id=uuid4(), org_id=org_id, role="member", is_active=True)

	async def fake_current_user_dep():
		return user

	async def fake_get_db():
		yield FakeDB()

	app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
	app.dependency_overrides[get_db] = fake_get_db

	response = client.patch(
		f"/api/v1/provider-keys/{uuid4()}",
		json={"weight": 5},
		headers={"Authorization": "Bearer test"},
	)
	assert response.status_code == 403


def test_update_not_found_404(client, monkeypatch):
	org_id = uuid4()
	user = SimpleNamespace(id=uuid4(), org_id=org_id, role="admin", is_active=True)

	async def fake_current_user_dep():
		return user

	async def fake_get_db():
		yield FakeDB(keys=[])  # empty → 404

	app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
	app.dependency_overrides[get_db] = fake_get_db

	response = client.patch(
		f"/api/v1/provider-keys/{uuid4()}",
		json={"weight": 5},
		headers={"Authorization": "Bearer test"},
	)
	assert response.status_code == 404


def test_update_weight_and_alias(client, monkeypatch):
	org_id = uuid4()
	user = SimpleNamespace(id=uuid4(), org_id=org_id, role="admin", is_active=True, email="admin@test.com")
	raw_key = "sk-openai-updatetest123456"
	fake_key = FakeKey(org_id, "openai", "old-alias", encrypt(raw_key), weight=1)

	async def fake_current_user_dep():
		return user

	async def fake_get_db():
		yield FakeDB(keys=[fake_key])

	app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
	app.dependency_overrides[get_db] = fake_get_db

	response = client.patch(
		f"/api/v1/provider-keys/{fake_key.id}",
		json={"key_alias": "new-alias", "weight": 5},
		headers={"Authorization": "Bearer test"},
	)

	assert response.status_code == 200
	data = response.json()
	assert data["key_alias"] == "new-alias"
	assert data["weight"] == 5
	assert data["key_prefix"] == raw_key[:8] + "…"


# ── DELETE ───────────────────────────────────────────────────────────────────


def test_delete_non_admin_gets_403(client, monkeypatch):
	org_id = uuid4()
	user = SimpleNamespace(id=uuid4(), org_id=org_id, role="member", is_active=True)

	async def fake_current_user_dep():
		return user

	async def fake_get_db():
		yield FakeDB()

	app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
	app.dependency_overrides[get_db] = fake_get_db

	response = client.delete(
		f"/api/v1/provider-keys/{uuid4()}",
		headers={"Authorization": "Bearer test"},
	)
	assert response.status_code == 403


def test_delete_not_found_404(client, monkeypatch):
	org_id = uuid4()
	user = SimpleNamespace(id=uuid4(), org_id=org_id, role="admin", is_active=True)

	async def fake_current_user_dep():
		return user

	async def fake_get_db():
		yield FakeDB(keys=[])

	app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
	app.dependency_overrides[get_db] = fake_get_db

	response = client.delete(
		f"/api/v1/provider-keys/{uuid4()}",
		headers={"Authorization": "Bearer test"},
	)
	assert response.status_code == 404


def test_delete_returns_204(client, monkeypatch):
	org_id = uuid4()
	user = SimpleNamespace(id=uuid4(), org_id=org_id, role="admin", is_active=True, email="admin@test.com")
	fake_key = FakeKey(org_id, "openai", "to-delete", encrypt("sk-openai-deleteme1234567"))

	async def fake_current_user_dep():
		return user

	async def fake_get_db():
		yield FakeDB(keys=[fake_key])

	app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
	app.dependency_overrides[get_db] = fake_get_db

	response = client.delete(
		f"/api/v1/provider-keys/{fake_key.id}",
		headers={"Authorization": "Bearer test"},
	)
	assert response.status_code == 204
