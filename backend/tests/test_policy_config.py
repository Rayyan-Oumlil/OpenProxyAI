"""Policy Config API tests — GET/PATCH /api/v1/organizations/current/policy."""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.dependencies import get_current_user_from_jwt, get_db, get_redis
from app.main import app
from app.services import policy_service as policy_service_module
from app.services.policy_service import PolicyConfig, PolicyStore


class FakeDB:
	def __init__(self):
		self.added = []

	def add(self, obj):
		self.added.append(obj)

	async def commit(self):
		return None


class FakeRedis:
	def __init__(self) -> None:
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


# ── GET /current/policy ──────────────────────────────────────────────────────


def test_get_policy_returns_config(client, monkeypatch):
	org_id = uuid4()
	user = SimpleNamespace(id=uuid4(), org_id=org_id, email="admin@test.com", role="admin", is_active=True)

	async def fake_current_user_dep():
		return user

	async def fake_get_db():
		yield FakeDB()

	async def fake_get_redis():
		return FakeRedis()

	async def fake_policy_store_load(org_id, db, redis):  # noqa: ANN001
		return PolicyConfig(
			enforcement_mode="enforce",
			allowed_models=["openai/gpt-4o-mini"],
			blocked_keywords=["hack"],
			pii_detection_enabled=True,
			pii_entities=[],
		)

	monkeypatch.setattr(policy_service_module.policy_store, "load", fake_policy_store_load)
	app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
	app.dependency_overrides[get_db] = fake_get_db
	app.dependency_overrides[get_redis] = fake_get_redis

	response = client.get("/api/v1/organizations/current/policy", headers={"Authorization": "Bearer test"})

	assert response.status_code == 200
	data = response.json()
	assert data["enforcement_mode"] == "enforce"
	assert data["allowed_models"] == ["openai/gpt-4o-mini"]
	assert data["blocked_keywords"] == ["hack"]
	assert data["pii_detection_enabled"] is True


def test_get_policy_requires_auth(client):
	response = client.get("/api/v1/organizations/current/policy")
	assert response.status_code == 401


# ── PATCH /current/policy ────────────────────────────────────────────────────


def test_patch_policy_requires_admin(client, monkeypatch):
	"""Non-admin users must get 403."""
	org_id = uuid4()
	user = SimpleNamespace(id=uuid4(), org_id=org_id, email="user@test.com", role="member", is_active=True)

	async def fake_current_user_dep():
		return user

	async def fake_get_db():
		yield FakeDB()

	async def fake_get_redis():
		return FakeRedis()

	app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
	app.dependency_overrides[get_db] = fake_get_db
	app.dependency_overrides[get_redis] = fake_get_redis

	response = client.patch(
		"/api/v1/organizations/current/policy",
		json={"enforcement_mode": "enforce"},
		headers={"Authorization": "Bearer test"},
	)
	assert response.status_code == 403


def test_patch_policy_merges_fields(client, monkeypatch):
	"""Only provided fields change; others keep their current value."""
	org_id = uuid4()
	user = SimpleNamespace(id=uuid4(), org_id=org_id, email="admin@test.com", role="admin", is_active=True)
	saved: list[PolicyConfig] = []

	async def fake_current_user_dep():
		return user

	async def fake_get_db():
		yield FakeDB()

	async def fake_get_redis():
		return FakeRedis()

	async def fake_load(org_id, db, redis):  # noqa: ANN001
		return PolicyConfig(
			enforcement_mode="off",
			allowed_models=["openai/gpt-4o"],
			blocked_keywords=["secret"],
			pii_detection_enabled=False,
			pii_entities=[],
		)

	async def fake_save(org_id, config, db, redis):  # noqa: ANN001
		saved.append(config)

	monkeypatch.setattr(policy_service_module.policy_store, "load", fake_load)
	monkeypatch.setattr(policy_service_module.policy_store, "save", fake_save)
	app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
	app.dependency_overrides[get_db] = fake_get_db
	app.dependency_overrides[get_redis] = fake_get_redis

	response = client.patch(
		"/api/v1/organizations/current/policy",
		json={"enforcement_mode": "log_only"},
		headers={"Authorization": "Bearer test"},
	)

	assert response.status_code == 200
	data = response.json()
	# Updated field
	assert data["enforcement_mode"] == "log_only"
	# Untouched fields preserved
	assert data["allowed_models"] == ["openai/gpt-4o"]
	assert data["blocked_keywords"] == ["secret"]
	assert data["pii_detection_enabled"] is False
	# save was called once with the merged config
	assert len(saved) == 1
	assert saved[0].enforcement_mode == "log_only"
	assert saved[0].allowed_models == ["openai/gpt-4o"]


def test_patch_policy_invalid_mode_422(client, monkeypatch):
	"""Unknown enforcement_mode must be rejected by Pydantic."""
	org_id = uuid4()
	user = SimpleNamespace(id=uuid4(), org_id=org_id, email="admin@test.com", role="admin", is_active=True)

	async def fake_current_user_dep():
		return user

	async def fake_get_db():
		yield FakeDB()

	async def fake_get_redis():
		return FakeRedis()

	app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
	app.dependency_overrides[get_db] = fake_get_db
	app.dependency_overrides[get_redis] = fake_get_redis

	response = client.patch(
		"/api/v1/organizations/current/policy",
		json={"enforcement_mode": "banana"},
		headers={"Authorization": "Bearer test"},
	)
	assert response.status_code == 422


# ── PolicyConfig unit tests (pure, no I/O) ───────────────────────────────────


def test_policy_config_from_dict_roundtrip():
	config = PolicyConfig(
		enforcement_mode="log_only",
		allowed_models=["openai/gpt-4o"],
		blocked_keywords=["foo"],
		pii_detection_enabled=True,
		pii_entities=["EMAIL_ADDRESS"],
	)
	reloaded = PolicyConfig.from_dict(config.to_dict())
	assert reloaded.enforcement_mode == config.enforcement_mode
	assert reloaded.allowed_models == config.allowed_models
	assert reloaded.blocked_keywords == config.blocked_keywords
	assert reloaded.pii_detection_enabled == config.pii_detection_enabled
	assert reloaded.pii_entities == config.pii_entities


@pytest.mark.asyncio
async def test_policy_store_load_raises_on_db_error():
	"""When Redis misses and DB is unavailable, load() raises — never silently uses permissive defaults."""
	import pytest

	store = PolicyStore()
	with pytest.raises(Exception):
		await store.load(org_id=uuid4(), db=SimpleNamespace(), redis=FakeRedis())


@pytest.mark.asyncio
async def test_policy_store_load_caches_in_redis():
	"""After a miss, load() stores the result in Redis so the next call hits cache."""
	redis = FakeRedis()
	org_id = uuid4()

	# Pre-load with a known config via setex
	import json
	from app.services.policy_service import _POLICY_CACHE_KEY

	expected = PolicyConfig(enforcement_mode="enforce", blocked_keywords=["secret"])
	cache_key = _POLICY_CACHE_KEY.format(org_id=org_id)
	await redis.setex(cache_key, 60, json.dumps(expected.to_dict()))

	store = PolicyStore()
	config = await store.load(org_id=org_id, db=SimpleNamespace(), redis=redis)
	assert config.enforcement_mode == "enforce"
	assert config.blocked_keywords == ["secret"]
