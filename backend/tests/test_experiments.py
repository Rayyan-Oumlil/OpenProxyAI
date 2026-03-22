"""Experiment A/B testing tests.

Verifies:
- _resolve_experiment returns variant when active experiment exists (mocked DB)
- _resolve_experiment returns requested model when no experiment
- Policy evaluates resolved model (variant not in allowed_models -> 403)
- Experiments API auth and admin checks
"""

from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from unittest.mock import AsyncMock, MagicMock

import app.database as database_module
from app.dependencies import get_current_user_from_jwt
from app.main import app
from app.services.policy_service import PolicyConfig, policy_service
from app.services import llm_service as llm_service_module


def _permissive_policy(allowed_models=None):
	return SimpleNamespace(
		enforcement_mode="enforce" if allowed_models else "off",
		allowed_models=allowed_models or [],
		blocked_keywords=[],
		pii_detection_enabled=False,
		pii_entities=[],
		model_rate_limits={},
		prompt_injection_detection_enabled=False,
		response_guardrails_enabled=False,
		response_pii_redact=False,
	)


def _patch_llm_common(monkeypatch, policy_allowed_models=None):
	async def _load(*a, **kw):
		return _permissive_policy(policy_allowed_models)
	monkeypatch.setattr(llm_service_module.policy_store, "load", _load)
	async def _check_limits(**kw):
		return (True, {}, None, None, None)
	monkeypatch.setattr(llm_service_module.rate_limiter_service, "check_limits", _check_limits)
	async def _log(**kw):
		pass
	monkeypatch.setattr(llm_service_module, "log_request", _log)
	monkeypatch.setattr(
		llm_service_module.cost_tracker_service,
		"calculate_cost_usd",
		lambda *a, **kw: Decimal("0"),
	)


@pytest.mark.asyncio
async def test_resolve_experiment_no_experiment_returns_requested_model(monkeypatch):
	"""When db.scalar returns None (no experiment), return requested model and None."""
	async def _noop_set_org(*a, **kw):
		pass
	monkeypatch.setattr(database_module, "set_session_org_id", _noop_set_org)

	fake_db = MagicMock()
	fake_db.scalar = AsyncMock(return_value=None)

	svc = llm_service_module.LLMService()
	resolved, info = await svc._resolve_experiment(fake_db, uuid4(), "openai/gpt-4o")
	assert resolved == "openai/gpt-4o"
	assert info is None


@pytest.mark.asyncio
async def test_resolve_experiment_empty_variants_returns_requested_model(monkeypatch):
	"""When experiment has no variants, return requested model and None."""
	async def _noop_set_org(*a, **kw):
		pass
	monkeypatch.setattr(database_module, "set_session_org_id", _noop_set_org)

	exp = SimpleNamespace(id=uuid4(), variants=[])
	fake_db = MagicMock()
	fake_db.scalar = AsyncMock(return_value=exp)

	svc = llm_service_module.LLMService()
	resolved, info = await svc._resolve_experiment(fake_db, uuid4(), "openai/gpt-4o")
	assert resolved == "openai/gpt-4o"
	assert info is None


@pytest.mark.asyncio
async def test_resolve_experiment_routes_to_variant(monkeypatch):
	"""Active experiment with variants returns variant model and experiment_info."""
	async def _noop_set_org(*a, **kw):
		pass
	monkeypatch.setattr(database_module, "set_session_org_id", _noop_set_org)

	variant = SimpleNamespace(id=uuid4(), model="anthropic/claude-3-5-sonnet", traffic_weight=100)
	exp = SimpleNamespace(id=uuid4(), variants=[variant])
	fake_db = MagicMock()
	fake_db.scalar = AsyncMock(return_value=exp)

	svc = llm_service_module.LLMService()
	resolved, info = await svc._resolve_experiment(fake_db, uuid4(), "openai/gpt-4o")
	assert resolved == "anthropic/claude-3-5-sonnet"
	assert info is not None
	assert info["experiment_id"] == str(exp.id)
	assert info["variant_model"] == "anthropic/claude-3-5-sonnet"
	assert info["original_model"] == "openai/gpt-4o"


@pytest.mark.asyncio
async def test_policy_blocks_variant_not_allowed(fake_redis, monkeypatch):
	"""When _resolve_experiment routes to variant not in allowed_models, policy blocks with 403."""
	from fastapi import BackgroundTasks

	async def _resolve_claude(*a, **kw):
		return "anthropic/claude-3-5-sonnet", {
			"experiment_id": str(uuid4()),
			"variant_model": "anthropic/claude-3-5-sonnet",
			"original_model": "openai/gpt-4o",
		}

	monkeypatch.setattr(llm_service_module.LLMService, "_resolve_experiment", _resolve_claude)
	_patch_llm_common(monkeypatch, policy_allowed_models=["openai/gpt-4o"])

	async def _keys(*a, **kw):
		return [(None, "sk-fake")]
	monkeypatch.setattr(llm_service_module.llm_service, "_select_provider_keys", _keys)

	async def _acompletion(**kw):
		r = MagicMock()
		r.choices = [MagicMock(message=MagicMock(content="hi"))]
		r.usage = MagicMock(prompt_tokens=1, completion_tokens=1)
		return r
	monkeypatch.setattr(llm_service_module, "acompletion", _acompletion)

	req = llm_service_module.ChatCompletionRequest(
		model="openai/gpt-4o",
		messages=[{"role": "user", "content": "hi"}],
		stream=False,
	)

	user = SimpleNamespace(id=uuid4(), org_id=uuid4(), budget_daily_usd=None)
	api_key = SimpleNamespace(id=uuid4())

	svc = llm_service_module.llm_service
	resp = await svc.chat_completion(
		request=req,
		db=MagicMock(),
		redis=fake_redis,
		user=user,
		api_key=api_key,
		request_id=uuid4(),
		background_tasks=BackgroundTasks(),
	)

	assert resp.status_code == 403


def test_experiments_require_auth(client):
	"""Experiments list returns 401 without auth."""
	resp = client.get("/api/v1/experiments")
	assert resp.status_code == 401


def test_experiments_create_requires_admin(client, monkeypatch):
	"""Experiments create returns 403 for non-admin."""
	user = SimpleNamespace(
		id=uuid4(), org_id=uuid4(), email="u@t.com", role="developer", is_active=True
	)

	async def fake_user():
		return user

	try:
		app.dependency_overrides[get_current_user_from_jwt] = fake_user
		resp = client.post(
			"/api/v1/experiments",
			json={
				"name": "X",
				"target_model": "openai/gpt-4o",
				"variants": [{"model": "openai/gpt-4o", "traffic_weight": 50}],
			},
			headers={"Authorization": "Bearer x"},
		)
		assert resp.status_code == 403
	finally:
		app.dependency_overrides.pop(get_current_user_from_jwt, None)


def test_is_model_on_allowlist():
	"""Empty allowlist allows any model; non-empty requires exact match."""
	assert policy_service.is_model_on_allowlist("any/model", PolicyConfig(allowed_models=[])) is True
	assert policy_service.is_model_on_allowlist(
		"openai/gpt-4o", PolicyConfig(allowed_models=["openai/gpt-4o"])
	)
	assert not policy_service.is_model_on_allowlist(
		"anthropic/claude-3",
		PolicyConfig(allowed_models=["openai/gpt-4o"]),
	)


def test_experiments_create_rejects_models_not_on_allowlist(client, monkeypatch):
	"""When org policy has an allowlist, variant models must be listed."""
	async def fake_load(org_id, db, redis):  # noqa: ARG001
		return PolicyConfig(allowed_models=["openai/gpt-4o"])

	monkeypatch.setattr("app.routes.experiments.policy_store.load", fake_load)

	user = SimpleNamespace(
		id=uuid4(), org_id=uuid4(), email="a@t.com", role="admin", is_active=True
	)

	async def fake_user():
		return user

	app.dependency_overrides[get_current_user_from_jwt] = fake_user
	try:
		resp = client.post(
			"/api/v1/experiments",
			json={
				"name": "X",
				"target_model": "openai/gpt-4o",
				"variants": [{"model": "anthropic/claude-3", "traffic_weight": 100}],
			},
			headers={"Authorization": "Bearer test"},
		)
		assert resp.status_code == 400
		assert "allowlist" in resp.json()["detail"].lower()
	finally:
		app.dependency_overrides.pop(get_current_user_from_jwt, None)


def test_experiments_create_rejects_target_not_on_allowlist(client, monkeypatch):
	async def fake_load(org_id, db, redis):  # noqa: ARG001
		return PolicyConfig(allowed_models=["openai/gpt-4o"])

	monkeypatch.setattr("app.routes.experiments.policy_store.load", fake_load)

	user = SimpleNamespace(
		id=uuid4(), org_id=uuid4(), email="a@t.com", role="admin", is_active=True
	)

	async def fake_user():
		return user

	app.dependency_overrides[get_current_user_from_jwt] = fake_user
	try:
		resp = client.post(
			"/api/v1/experiments",
			json={
				"name": "X",
				"target_model": "anthropic/claude-3",
				"variants": [{"model": "openai/gpt-4o", "traffic_weight": 100}],
			},
			headers={"Authorization": "Bearer test"},
		)
		assert resp.status_code == 400
		assert "allowlist" in resp.json()["detail"].lower()
	finally:
		app.dependency_overrides.pop(get_current_user_from_jwt, None)
