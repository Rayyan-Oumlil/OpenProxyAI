"""GET /v1/models endpoint tests."""

from types import SimpleNamespace
from uuid import uuid4


from app.dependencies import get_current_user_from_api_key, get_db, get_redis
from app.main import app
from app.routes import proxy as proxy_routes


class _AllResult:
	def __init__(self, items):
		self._items = items

	def all(self):
		return self._items


class FakeDB:
	def __init__(self, *, scalars_items=None):
		self._scalars_items = scalars_items or []

	async def scalars(self, *args, **kwargs):
		return _AllResult(self._scalars_items)


def _make_provider_key(provider: str, model_patterns: list[str] | None = None):
	return SimpleNamespace(
		provider=provider,
		model_patterns=model_patterns,
		is_active=True,
	)


def test_models_200_with_valid_api_key_returns_model_list(client, fake_redis, monkeypatch):
	org_id = uuid4()
	user = SimpleNamespace(id=uuid4(), org_id=org_id, is_active=True)
	api_key = SimpleNamespace(id=uuid4(), org_id=org_id, user=user)

	key_openai = _make_provider_key("openai", model_patterns=None)
	fake_db = FakeDB(scalars_items=[key_openai])

	async def fake_proxy_auth_dep():
		return user, api_key

	async def fake_get_db():
		yield fake_db

	async def fake_get_redis():
		return fake_redis

	# Patch litellm.models_by_provider for deterministic test (no external API)
	fake_registry = {
		"openai": ["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"],
		"anthropic": ["claude-3-5-sonnet", "claude-3-haiku"],
	}
	monkeypatch.setattr(proxy_routes.litellm, "models_by_provider", fake_registry)

	app.dependency_overrides[get_current_user_from_api_key] = fake_proxy_auth_dep
	app.dependency_overrides[get_db] = fake_get_db
	app.dependency_overrides[get_redis] = fake_get_redis

	response = client.get(
		"/v1/models",
		headers={"Authorization": "Bearer opai_dev_test"},
	)

	assert response.status_code == 200
	data = response.json()
	assert data["object"] == "list"
	assert "data" in data
	ids = [m["id"] for m in data["data"]]
	assert ids == ["openai/gpt-3.5-turbo", "openai/gpt-4o", "openai/gpt-4o-mini"]
	assert all(m["object"] == "model" for m in data["data"])
	assert all("owned_by" in m for m in data["data"])


def test_models_401_without_api_key(client):
	response = client.get("/v1/models")
	assert response.status_code == 401


def test_models_empty_list_when_org_has_no_active_provider_keys(client, fake_redis, monkeypatch):
	org_id = uuid4()
	user = SimpleNamespace(id=uuid4(), org_id=org_id, is_active=True)
	api_key = SimpleNamespace(id=uuid4(), org_id=org_id, user=user)

	fake_db = FakeDB(scalars_items=[])

	async def fake_proxy_auth_dep():
		return user, api_key

	async def fake_get_db():
		yield fake_db

	async def fake_get_redis():
		return fake_redis

	app.dependency_overrides[get_current_user_from_api_key] = fake_proxy_auth_dep
	app.dependency_overrides[get_db] = fake_get_db
	app.dependency_overrides[get_redis] = fake_get_redis

	response = client.get(
		"/v1/models",
		headers={"Authorization": "Bearer opai_dev_test"},
	)

	assert response.status_code == 200
	data = response.json()
	assert data["object"] == "list"
	assert data["data"] == []


def test_models_model_patterns_filter_models(client, fake_redis, monkeypatch):
	org_id = uuid4()
	user = SimpleNamespace(id=uuid4(), org_id=org_id, is_active=True)
	api_key = SimpleNamespace(id=uuid4(), org_id=org_id, user=user)

	key_openai = _make_provider_key("openai", model_patterns=["gpt-4*"])
	fake_db = FakeDB(scalars_items=[key_openai])

	async def fake_proxy_auth_dep():
		return user, api_key

	async def fake_get_db():
		yield fake_db

	async def fake_get_redis():
		return fake_redis

	fake_registry = {
		"openai": ["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo", "gpt-4-turbo"],
	}
	monkeypatch.setattr(proxy_routes.litellm, "models_by_provider", fake_registry)

	app.dependency_overrides[get_current_user_from_api_key] = fake_proxy_auth_dep
	app.dependency_overrides[get_db] = fake_get_db
	app.dependency_overrides[get_redis] = fake_get_redis

	response = client.get(
		"/v1/models",
		headers={"Authorization": "Bearer opai_dev_test"},
	)

	assert response.status_code == 200
	data = response.json()
	ids = [m["id"] for m in data["data"]]
	assert set(ids) == {"openai/gpt-4o", "openai/gpt-4o-mini", "openai/gpt-4-turbo"}
	assert "openai/gpt-3.5-turbo" not in ids


def test_models_deduplication_when_multiple_keys_cover_same_provider(client, fake_redis, monkeypatch):
	org_id = uuid4()
	user = SimpleNamespace(id=uuid4(), org_id=org_id, is_active=True)
	api_key = SimpleNamespace(id=uuid4(), org_id=org_id, user=user)

	key1 = _make_provider_key("openai", model_patterns=["gpt-4o"])
	key2 = _make_provider_key("openai", model_patterns=["gpt-4o-mini"])
	fake_db = FakeDB(scalars_items=[key1, key2])

	async def fake_proxy_auth_dep():
		return user, api_key

	async def fake_get_db():
		yield fake_db

	async def fake_get_redis():
		return fake_redis

	fake_registry = {
		"openai": ["gpt-4o", "gpt-4o-mini"],
	}
	monkeypatch.setattr(proxy_routes.litellm, "models_by_provider", fake_registry)

	app.dependency_overrides[get_current_user_from_api_key] = fake_proxy_auth_dep
	app.dependency_overrides[get_db] = fake_get_db
	app.dependency_overrides[get_redis] = fake_get_redis

	response = client.get(
		"/v1/models",
		headers={"Authorization": "Bearer opai_dev_test"},
	)

	assert response.status_code == 200
	data = response.json()
	ids = [m["id"] for m in data["data"]]
	assert ids == ["openai/gpt-4o", "openai/gpt-4o-mini"]
	assert len(ids) == len(set(ids))
