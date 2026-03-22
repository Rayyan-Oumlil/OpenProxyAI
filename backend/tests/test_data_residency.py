"""Data residency tests — region filtering for provider keys and org data_region."""

from datetime import datetime, UTC
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.dependencies import get_current_user_from_jwt, get_db
from app.main import app
from app.services.crypto_service import decrypt, encrypt
from app.services.llm_service import LLMService


class FakeOrg:
	"""Minimal Organization substitute."""

	def __init__(self, org_id: uuid4, data_region: str = "us"):
		self.id = org_id
		self.data_region = data_region


class FakeKey:
	"""Minimal LLMProviderKey ORM model substitute."""

	def __init__(
		self,
		org_id,
		provider,
		key_alias,
		api_key_encrypted,
		weight=1,
		is_active=True,
		region="us",
	):
		self.id = uuid4()
		self.org_id = org_id
		self.provider = provider
		self.key_alias = key_alias
		self.api_key_encrypted = api_key_encrypted
		self.weight = weight
		self.is_active = is_active
		self.region = region
		self.model_patterns = None
		self.created_at = datetime.now(UTC)


class FakeScalarsResult:
	def __init__(self, items):
		self._items = items

	def __iter__(self):
		return iter(self._items)


class DataResidencyFakeDB:
	"""Fake DB that supports get(Organization) and scalars() for _select_provider_keys.

	scalars() returns only keys matching org.data_region or region='global',
	simulating the real SQL filter.
	"""

	def __init__(self, org: FakeOrg | None, keys: list[FakeKey] | None = None):
		self._org = org
		self._keys = keys or []

	async def get(self, model, pk):
		if model.__name__ == "Organization" and self._org and str(self._org.id) == str(pk):
			return self._org
		return None

	async def scalars(self, _stmt):
		if not self._org:
			return FakeScalarsResult([])
		data_region = (self._org.data_region or "us").strip().lower()
		eligible = [k for k in self._keys if k.region == data_region or k.region == "global"]
		return FakeScalarsResult(eligible)

	async def commit(self):
		pass


@pytest.fixture(autouse=True)
def patch_policy_store(monkeypatch):
	from app.services.policy_service import PolicyConfig, policy_store

	async def _fake_load(org_id, db, redis):
		return PolicyConfig.from_settings()

	monkeypatch.setattr(policy_store, "load", _fake_load)


# ── _select_provider_keys region filtering ─────────────────────────────────────


@pytest.mark.asyncio
async def test_eu_org_gets_eu_or_global_keys_only(monkeypatch):
	"""Org with data_region=eu only gets keys with region=eu or region=global."""
	org_id = uuid4()
	org = FakeOrg(org_id, data_region="eu")
	raw = "sk-openai-eu-key-12345678"
	eu_key = FakeKey(org_id, "openai", "eu-prod", encrypt(raw), region="eu")
	global_key = FakeKey(org_id, "openai", "global-prod", encrypt("sk-openai-global-12345678"), region="global")
	db = DataResidencyFakeDB(org, keys=[eu_key, global_key])

	svc = LLMService()
	keys = await svc._select_provider_keys(db, org_id, "openai", model=None)
	assert len(keys) >= 1
	key_strings = [k[1] for k in keys]
	assert decrypt(eu_key.api_key_encrypted) in key_strings or decrypt(global_key.api_key_encrypted) in key_strings


@pytest.mark.asyncio
async def test_us_org_gets_us_or_global_keys_only(monkeypatch):
	"""Org with data_region=us only gets keys with region=us or region=global."""
	org_id = uuid4()
	org = FakeOrg(org_id, data_region="us")
	raw = "sk-openai-us-key-12345678"
	us_key = FakeKey(org_id, "openai", "us-prod", encrypt(raw), region="us")
	db = DataResidencyFakeDB(org, keys=[us_key])

	svc = LLMService()
	keys = await svc._select_provider_keys(db, org_id, "openai", model=None)
	assert len(keys) == 1
	assert decrypt(us_key.api_key_encrypted) == keys[0][1]


@pytest.mark.asyncio
async def test_global_keys_always_included(monkeypatch):
	"""Org in any region gets keys with region=global."""
	org_id = uuid4()
	org = FakeOrg(org_id, data_region="ap")
	raw = "sk-openai-global-12345678"
	global_key = FakeKey(org_id, "openai", "global", encrypt(raw), region="global")
	db = DataResidencyFakeDB(org, keys=[global_key])

	svc = LLMService()
	keys = await svc._select_provider_keys(db, org_id, "openai", model=None)
	assert len(keys) == 1
	assert keys[0][1] == decrypt(global_key.api_key_encrypted)


@pytest.mark.asyncio
async def test_503_when_no_keys_match_region(monkeypatch):
	"""Org data_region=eu with only US keys returns 503 with region-specific message."""
	monkeypatch.setattr("app.services.llm_service.settings.OPENAI_API_KEY", "")
	monkeypatch.setattr("app.services.llm_service.settings.ANTHROPIC_API_KEY", "")
	monkeypatch.setattr("app.services.llm_service.settings.AZURE_API_KEY", "")

	org_id = uuid4()
	org = FakeOrg(org_id, data_region="eu")
	us_key = FakeKey(org_id, "openai", "us-only", encrypt("sk-openai-us-12345678"), region="us")
	db = DataResidencyFakeDB(org, keys=[us_key])

	svc = LLMService()
	from fastapi import HTTPException

	with pytest.raises(HTTPException) as exc_info:
		await svc._select_provider_keys(db, org_id, "openai", model=None)
	assert exc_info.value.status_code == 503
	detail = exc_info.value.detail
	assert "eu" in str(detail)
	assert "global" in str(detail)


# ── Provider key CRUD with region ─────────────────────────────────────────────


def test_provider_key_crud_accepts_region(client, monkeypatch):
	"""POST/PATCH/GET include region; response contains region."""
	org_id = uuid4()
	user = SimpleNamespace(id=uuid4(), org_id=org_id, role="admin", is_active=True, email="admin@test.com")
	raw_key = "sk-openai-region-test-123456"

	async def fake_current_user_dep():
		return user

	class FakeDBWithGet:
		def __init__(self):
			self._keys = []
			self._added = []

		async def scalars(self, _stmt):
			# Only return provider keys (not AdminAuditLog etc.)
			pks = [k for k in self._keys if hasattr(k, "api_key_encrypted")]
			return FakeScalarsResult(pks)

		async def scalar(self, _stmt):
			pks = [k for k in self._keys if hasattr(k, "api_key_encrypted")]
			return pks[0] if pks else None

		def add(self, obj):
			self._added.append(obj)
			self._keys.append(obj)

		async def commit(self):
			pass

		async def refresh(self, obj):
			if getattr(obj, "id", None) is None:
				obj.id = uuid4()
			if getattr(obj, "created_at", None) is None:
				obj.created_at = datetime.now(UTC)
			if getattr(obj, "region", None) is None:
				obj.region = "us"

	db = FakeDBWithGet()

	async def fake_get_db():
		yield db

	app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
	app.dependency_overrides[get_db] = fake_get_db

	# POST with region
	response = client.post(
		"/api/v1/provider-keys",
		json={
			"provider": "openai",
			"key_alias": "eu-key",
			"api_key": raw_key,
			"weight": 1,
			"region": "eu",
		},
		headers={"Authorization": "Bearer test"},
	)
	assert response.status_code == 201
	data = response.json()
	assert data["region"] == "eu"
	assert len(db._added) >= 1
	pk = next((o for o in db._added if hasattr(o, "api_key_encrypted")), None)
	assert pk is not None and pk.region == "eu"

	# GET returns region
	response = client.get("/api/v1/provider-keys", headers={"Authorization": "Bearer test"})
	assert response.status_code == 200
	items = response.json()
	assert len(items) >= 1
	assert any(k["region"] == "eu" for k in items)


def test_default_region_is_us(client, monkeypatch):
	"""New key without region in body defaults to us."""
	org_id = uuid4()
	user = SimpleNamespace(id=uuid4(), org_id=org_id, role="admin", is_active=True, email="admin@test.com")

	class FakeDBWithGet:
		def __init__(self):
			self._keys = []
			self._added = []

		async def scalars(self, _stmt):
			return FakeScalarsResult(self._keys)

		async def scalar(self, _stmt):
			return self._keys[0] if self._keys else None

		def add(self, obj):
			self._added.append(obj)
			self._keys.append(obj)

		async def commit(self):
			pass

		async def refresh(self, obj):
			if getattr(obj, "id", None) is None:
				obj.id = uuid4()
			if getattr(obj, "created_at", None) is None:
				obj.created_at = datetime.now(UTC)

	db = FakeDBWithGet()

	async def fake_current_user_dep():
		return user

	async def fake_get_db():
		yield db

	app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
	app.dependency_overrides[get_db] = fake_get_db

	response = client.post(
		"/api/v1/provider-keys",
		json={"provider": "openai", "key_alias": "default-region", "api_key": "sk-openai-default-12345678"},
		headers={"Authorization": "Bearer test"},
	)
	assert response.status_code == 201
	assert response.json()["region"] == "us"
	pk = next((o for o in db._added if hasattr(o, "api_key_encrypted")), None)
	assert pk is not None and pk.region == "us"


def test_invalid_region_returns_422(client, monkeypatch):
	"""POST with invalid region returns 422."""
	org_id = uuid4()
	user = SimpleNamespace(id=uuid4(), org_id=org_id, role="admin", is_active=True)

	class MinimalFakeDB:
		async def scalars(self, _stmt):
			return FakeScalarsResult([])
		async def scalar(self, _stmt):
			return None
		def add(self, obj):
			pass
		async def commit(self):
			pass
		async def refresh(self, obj):
			pass

	async def fake_current_user_dep():
		return user

	async def fake_get_db():
		yield MinimalFakeDB()

	app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
	app.dependency_overrides[get_db] = fake_get_db

	response = client.post(
		"/api/v1/provider-keys",
		json={
			"provider": "openai",
			"key_alias": "bad-region",
			"api_key": "sk-openai-bad-12345678",
			"region": "invalid",
		},
		headers={"Authorization": "Bearer test"},
	)
	assert response.status_code == 422
