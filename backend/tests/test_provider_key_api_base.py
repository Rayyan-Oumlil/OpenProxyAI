"""Provider keys carry api_base / max_data_class / is_internal: API, selection, calls, health."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.config import settings
from app.dependencies import get_current_user_from_jwt, get_db
from app.main import app
from app.services.crypto_service import encrypt
from app.services.llm_service import LLMService
from tests.test_provider_keys import FakeDB, FakeKey

AUTH = {"Authorization": "Bearer test"}


def _admin(org_id=None):
	return SimpleNamespace(id=uuid4(), org_id=org_id or uuid4(), role="admin", is_active=True, email="admin@test.com")


def _wire(user, db):
	async def _user():
		return user

	async def _db():
		yield db

	app.dependency_overrides[get_current_user_from_jwt] = _user
	app.dependency_overrides[get_db] = _db


@pytest.fixture(autouse=True)
def _no_internal(monkeypatch):
	monkeypatch.setattr(settings, "AIRGAP_MODE", False)
	monkeypatch.setattr(settings, "ALLOW_INTERNAL_PROVIDER_ENDPOINTS", False)


# ── API ──────────────────────────────────────────────────────────────────────


def test_create_defaults_keep_existing_behaviour(client):
	_wire(_admin(), FakeDB())
	r = client.post("/api/v1/provider-keys", json={"provider": "openai", "key_alias": "a", "api_key": "sk-test-key-12345"}, headers=AUTH)
	assert r.status_code == 201
	body = r.json()
	assert (body["api_base"], body["max_data_class"], body["is_internal"]) == (None, "internal", False)


def test_create_stores_a_public_api_base(client):
	db = FakeDB()
	_wire(_admin(), db)
	r = client.post(
		"/api/v1/provider-keys",
		json={"provider": "openai", "key_alias": "vllm", "api_key": "sk-test-key-12345", "api_base": "https://8.8.8.8/v1", "max_data_class": "confidential"},
		headers=AUTH,
	)
	assert r.status_code == 201
	assert r.json()["api_base"] == "https://8.8.8.8/v1"
	assert r.json()["max_data_class"] == "confidential"
	assert db._added[0].api_base == "https://8.8.8.8/v1"


def test_create_rejects_an_unsafe_api_base(client):
	_wire(_admin(), FakeDB())
	r = client.post(
		"/api/v1/provider-keys",
		json={"provider": "openai", "key_alias": "x", "api_key": "sk-test-key-12345", "api_base": "https://169.254.169.254/latest"},
		headers=AUTH,
	)
	assert r.status_code == 422
	assert r.json()["detail"]["error"] == "invalid_api_base"


def test_create_rejects_an_unknown_data_class(client):
	_wire(_admin(), FakeDB())
	r = client.post(
		"/api/v1/provider-keys",
		json={"provider": "openai", "key_alias": "x", "api_key": "sk-test-key-12345", "max_data_class": "top-secret"},
		headers=AUTH,
	)
	assert r.status_code == 422


def test_create_internal_needs_the_operator_switch(client, monkeypatch):
	body = {"provider": "openai", "key_alias": "local", "api_key": "sk-test-key-12345", "api_base": "http://10.0.0.5:8000/v1", "is_internal": True}
	_wire(_admin(), FakeDB())
	assert client.post("/api/v1/provider-keys", json=body, headers=AUTH).status_code == 422
	monkeypatch.setattr(settings, "ALLOW_INTERNAL_PROVIDER_ENDPOINTS", True)
	_wire(_admin(), FakeDB())
	r = client.post("/api/v1/provider-keys", json=body, headers=AUTH)
	assert r.status_code == 201 and r.json()["is_internal"] is True


def test_update_validates_the_merged_result_and_can_clear_api_base(client):
	org = uuid4()
	key = FakeKey(org, "openai", "k", encrypt("sk-test-key-12345"))
	key.api_base, key.max_data_class, key.is_internal = "https://8.8.8.8/v1", "internal", False
	_wire(_admin(org), FakeDB(keys=[key]))
	assert client.patch(f"/api/v1/provider-keys/{key.id}", json={"api_base": "http://8.8.8.8/v1"}, headers=AUTH).status_code == 422
	cleared = client.patch(f"/api/v1/provider-keys/{key.id}", json={"api_base": None}, headers=AUTH)
	assert cleared.status_code == 200 and cleared.json()["api_base"] is None
	raised = client.patch(f"/api/v1/provider-keys/{key.id}", json={"max_data_class": "secret"}, headers=AUTH)
	assert raised.json()["max_data_class"] == "secret"


def test_non_admin_cannot_set_api_base(client):
	user = SimpleNamespace(id=uuid4(), org_id=uuid4(), role="member", is_active=True)
	_wire(user, FakeDB())
	body = {"provider": "openai", "key_alias": "x", "api_key": "sk-test-key-12345", "api_base": "https://8.8.8.8/v1"}
	assert client.post("/api/v1/provider-keys", json=body, headers=AUTH).status_code == 403


# ── selection and calls ──────────────────────────────────────────────────────


def _row(api_base):
	key = MagicMock()
	key.id, key.weight, key.model_patterns, key.api_base, key.is_internal = uuid4(), 1, None, api_base, False
	key.api_key_encrypted = encrypt("sk-only-key-123456")
	return key


async def test_selection_returns_the_keys_api_base():
	db = MagicMock()
	db.get = AsyncMock(return_value=None)
	db.scalars = AsyncMock(return_value=iter([_row("https://8.8.8.8/v1")]))
	[candidate] = await LLMService()._select_provider_keys(db, uuid4(), "openai")
	assert candidate[0] is not None and candidate[1] == "sk-only-key-123456"
	assert candidate[2] == "https://8.8.8.8/v1"


async def test_selection_skips_a_key_whose_endpoint_no_longer_validates(monkeypatch):
	from app.utils import provider_endpoint

	provider_endpoint.clear_runtime_cache()

	async def unsafe(url):
		return None

	monkeypatch.setattr(provider_endpoint, "resolve_public_ip", unsafe)
	safe_row, unsafe_row = _row(None), _row("https://1.1.1.1/v1")
	db = MagicMock()
	db.get = AsyncMock(return_value=None)
	db.scalars = AsyncMock(return_value=iter([safe_row, unsafe_row]))
	result = await LLMService()._select_provider_keys(db, uuid4(), "openai")
	assert [c.key_id for c in result] == [safe_row.id]


async def test_selection_never_falls_back_to_the_gateways_own_key_when_every_endpoint_was_dropped(monkeypatch):
	from fastapi import HTTPException

	from app.utils import provider_endpoint

	provider_endpoint.clear_runtime_cache()
	monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-gateway-env-key")
	monkeypatch.setattr(settings, "SHARED_KEY_REGIONS", "us,global")

	async def unsafe(url):
		return None

	monkeypatch.setattr(provider_endpoint, "resolve_public_ip", unsafe)
	db = MagicMock()
	db.get = AsyncMock(return_value=None)
	db.scalars = AsyncMock(return_value=iter([_row("https://1.1.1.1/v1")]))
	with pytest.raises(HTTPException) as exc:
		await LLMService()._select_provider_keys(db, uuid4(), "openai")
	assert exc.value.status_code == 503
	assert exc.value.detail["error"] == "no_provider_key"


async def test_execute_with_fallback_passes_api_base_only_when_set():
	seen = []

	async def call(key, api_base=None):
		seen.append((key, api_base))
		return "ok"

	await LLMService._execute_with_fallback([(None, "env-key")], call, "m")
	assert seen == [("env-key", None)]  # legacy 2-tuples still work
	seen.clear()
	await LLMService._execute_with_fallback([(uuid4(), "k2", "https://8.8.8.8/v1")], call, "m")
	assert seen == [("k2", "https://8.8.8.8/v1")]


async def test_one_argument_call_functions_still_work_without_api_base():
	async def call(key):
		return key

	response, _, _ = await LLMService._execute_with_fallback([(None, "only")], call, "m")
	assert response == "only"


async def test_chat_completion_sends_api_base_to_litellm(monkeypatch, fake_redis):
	from tests.test_provider_fallback import _call, _make_litellm_response

	captured = {}

	async def fake_acompletion(**kwargs):
		captured.update(kwargs)
		return _make_litellm_response()

	await _call(monkeypatch, fake_redis, [(uuid4(), "sk-1", "https://8.8.8.8/v1")], fake_acompletion)
	assert captured["api_base"] == "https://8.8.8.8/v1"
	assert captured["api_key"] == "sk-1"


async def test_chat_completion_without_api_base_does_not_send_the_kwarg(monkeypatch, fake_redis):
	from tests.test_provider_fallback import _call, _make_litellm_response

	captured = {}

	async def fake_acompletion(**kwargs):
		captured.update(kwargs)
		return _make_litellm_response()

	await _call(monkeypatch, fake_redis, [(uuid4(), "sk-1")], fake_acompletion)
	assert "api_base" not in captured


# ── health check ─────────────────────────────────────────────────────────────


async def test_health_check_uses_the_keys_own_endpoint(monkeypatch):
	from app.services import provider_health_service as health

	calls = []

	class _Client:
		def __init__(self, *a, **k): ...

		async def __aenter__(self):
			return self

		async def __aexit__(self, *a):
			return False

		async def get(self, url, headers=None):
			calls.append(url)
			return SimpleNamespace(status_code=200)

	monkeypatch.setattr(health.httpx, "AsyncClient", _Client)
	assert await health._ping_provider("openai", "sk-1", "https://8.8.8.8/v1/") is True
	assert calls == ["https://8.8.8.8/v1/models"]  # not api.openai.com
