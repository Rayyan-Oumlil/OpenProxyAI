"""Routing decisions inside the chat pipeline (Phase 2, S4b): experiments, fallback header, cache gate, key restriction."""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.config import settings
from app.schemas.chat import ChatCompletionRequest
from app.services import llm_service as llm_module
from app.services.classification_service import Classification
from app.services.llm_service import LLMService
from app.services.policy_service import PolicyConfig, policy_service
from app.services.routing_service import Candidate


def candidate(model_id, **overrides):
	fields = dict(
		model_id=model_id, provider=model_id.split("/", 1)[0], enabled=True, key_id=uuid.uuid4(), key_active=True,
		key_class="confidential", entry_class="confidential", regions=("us",), risk="medium", capabilities=(), cost_tier=None,
	)
	return Candidate(**{**fields, **overrides})


def make_ctx(model, *, mode="enforce", data_class="internal", experiment_from=None, fallback=None, allowed=()):
	request = ChatCompletionRequest(model=model, messages=[{"role": "user", "content": "hi"}])
	return SimpleNamespace(
		request=request,
		requested_model=experiment_from or model,
		experiment_info={"experiment_id": "e1"} if experiment_from else None,
		policy_config=PolicyConfig(routing_mode=mode, allowed_models=list(allowed)),
		classification=Classification(data_class, "default", ()),
		user=SimpleNamespace(org_id=uuid.uuid4()),
		fallback_model=fallback,
		fallback_key_id=None,
		route_key_id=None,
		routing=None,
		routing_notes={},
		provider=model.partition("/")[0] or "unknown",
		model_name=model.partition("/")[2],
	)


@pytest.fixture
def registry(monkeypatch):
	def install(*candidates):
		monkeypatch.setattr(llm_module, "load_candidates", AsyncMock(return_value=list(candidates)))
		db = MagicMock()
		db.get = AsyncMock(return_value=SimpleNamespace(data_region="us"))
		return db

	return install


# ── experiment variants stay inside the authorized set ───────────────────────


async def test_an_unauthorized_experiment_variant_is_dropped_for_the_model_the_caller_asked_for(registry):
	db = registry(candidate("openai/gpt-4o"), candidate("openai/variant", entry_class="public"))
	ctx = make_ctx("openai/variant", experiment_from="openai/gpt-4o", data_class="confidential")

	await LLMService()._decide_route(ctx, db)

	assert ctx.request.model == "openai/gpt-4o" and ctx.experiment_info is None
	assert ctx.routing.model == "openai/gpt-4o" and not ctx.routing.blocked
	assert "variant openai/variant" in ctx.routing_notes["experiment_skipped"]
	assert (ctx.provider, ctx.model_name) == ("openai", "gpt-4o")


async def test_an_authorized_variant_keeps_running(registry):
	db = registry(candidate("openai/gpt-4o"), candidate("openai/variant"))
	ctx = make_ctx("openai/variant", experiment_from="openai/gpt-4o")

	await LLMService()._decide_route(ctx, db)

	assert ctx.request.model == "openai/variant" and ctx.experiment_info is not None and "experiment_skipped" not in ctx.routing_notes


async def test_when_neither_the_variant_nor_the_original_is_authorized_the_request_is_blocked(registry):
	db = registry(candidate("openai/gpt-4o", entry_class="public"), candidate("openai/variant", entry_class="public"))
	ctx = make_ctx("openai/variant", experiment_from="openai/gpt-4o", data_class="confidential")

	await LLMService()._decide_route(ctx, db)

	assert ctx.routing.blocked and ctx.request.model == "openai/variant"  # nothing was swapped


async def test_log_only_never_touches_the_request_or_the_experiment(registry):
	db = registry(candidate("openai/variant", entry_class="public"))
	ctx = make_ctx("openai/variant", mode="log_only", experiment_from="openai/gpt-4o", data_class="confidential")

	await LLMService()._decide_route(ctx, db)

	assert ctx.request.model == "openai/variant" and ctx.experiment_info is not None
	assert ctx.routing.model is None and not ctx.routing.blocked and ctx.route_key_id is None


# ── fallback header ──────────────────────────────────────────────────────────


async def test_an_authorized_fallback_is_kept_with_its_own_key(registry):
	primary, backup = candidate("openai/gpt-4o"), candidate("openai/gpt-4o-mini")
	db = registry(primary, backup)
	ctx = make_ctx("openai/gpt-4o", fallback="openai/gpt-4o-mini")

	await LLMService()._decide_route(ctx, db)

	assert (ctx.route_key_id, ctx.fallback_model, ctx.fallback_key_id) == (primary.key_id, "openai/gpt-4o-mini", backup.key_id)


@pytest.mark.parametrize(
	"fallback_candidate,reason",
	[(None, "not_in_registry"), (candidate("openai/backup", entry_class="public"), "not_authorized:class_too_low")],
)
async def test_an_unauthorized_fallback_is_dropped_and_the_reason_recorded(registry, fallback_candidate, reason):
	db = registry(*[c for c in (candidate("openai/gpt-4o"), fallback_candidate) if c])
	ctx = make_ctx("openai/gpt-4o", fallback="openai/backup", data_class="confidential")

	await LLMService()._decide_route(ctx, db)

	assert ctx.fallback_model is None and ctx.fallback_key_id is None
	assert ctx.routing_notes["fallback_model_refused"] == reason


# ── capability requests ──────────────────────────────────────────────────────


async def test_a_capability_request_becomes_a_concrete_model_with_its_key(registry):
	chosen = candidate("openai/gpt-4o-mini", capabilities=("VISION",), cost_tier="low")
	db = registry(chosen, candidate("openai/gpt-4o", capabilities=("VISION",), cost_tier="high"))
	ctx = make_ctx("cap:VISION")

	await LLMService()._decide_route(ctx, db)

	assert ctx.request.model == "openai/gpt-4o-mini" and (ctx.provider, ctx.model_name) == ("openai", "gpt-4o-mini")
	assert ctx.route_key_id == chosen.key_id


def test_the_policy_allowlist_does_not_reject_the_literal_cap_name_only_when_routing_enforces():
	allowlist = ["openai/gpt-4o"]
	enforcing = PolicyConfig(routing_mode="enforce", allowed_models=allowlist)
	assert policy_service.is_model_on_allowlist("cap:VISION", enforcing) is True
	assert policy_service.is_model_on_allowlist("openai/other", enforcing) is False  # concrete models still need the list
	assert policy_service.is_model_on_allowlist("cap:VISION", PolicyConfig(routing_mode="log_only", allowed_models=allowlist)) is False


# ── semantic cache gate ──────────────────────────────────────────────────────


@pytest.mark.parametrize(
	"mode,data_class,expected",
	[("off", "secret", True), ("log_only", "secret", True), ("enforce", "public", True), ("enforce", "internal", True),
	 ("enforce", "confidential", False), ("enforce", "secret", False)],
)
def test_semantic_cache_is_skipped_for_requests_above_the_embedding_endpoints_clearance(mode, data_class, expected):
	ctx = SimpleNamespace(
		routing=None if mode == "off" else SimpleNamespace(mode=mode),
		classification=Classification(data_class, "default", ()),
	)
	assert LLMService._semantic_cache_allowed(ctx) is expected


def test_the_operator_can_raise_the_embedding_endpoints_clearance(monkeypatch):
	monkeypatch.setattr(settings, "SEMANTIC_CACHE_MAX_DATA_CLASS", "confidential")
	ctx = SimpleNamespace(routing=SimpleNamespace(mode="enforce"), classification=Classification("confidential", "default", ()))
	assert LLMService._semantic_cache_allowed(ctx) is True


# ── the registry key is the only key ─────────────────────────────────────────


async def test_with_a_registry_key_there_is_no_fallback_to_an_environment_key(monkeypatch):
	monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-gateway-env-key")
	monkeypatch.setattr(settings, "SHARED_KEY_REGIONS", "us,global")
	db = MagicMock()
	db.get = AsyncMock(return_value=None)
	db.scalars = AsyncMock(return_value=iter([]))  # the registry key is gone, inactive or in another region

	with pytest.raises(HTTPException) as exc:
		await LLMService()._select_provider_keys(db, uuid.uuid4(), "openai", only_key_id=uuid.uuid4())

	assert exc.value.status_code == 503 and exc.value.detail["error"] == "no_provider_key"

	# Without the restriction the same situation falls back to the environment key, as before.
	db.scalars = AsyncMock(return_value=iter([]))
	[env_candidate] = await LLMService()._select_provider_keys(db, uuid.uuid4(), "openai")
	assert env_candidate.api_key == "sk-gateway-env-key"
