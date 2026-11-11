"""The embeddings pipeline end to end (policy, class, routing, limits, key choice, call, audit), with the provider faked.

These pin the behaviour that the shared modality pipeline (Phase 5, slice 1) must keep: they were written against the
original hand-written handler and run unchanged against the refactor.
"""

from __future__ import annotations

import json
import uuid
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import BackgroundTasks, HTTPException

from app.schemas.chat import EmbeddingRequest
from app.services import llm_service as llm_module
from app.services import rate_limiter
from app.services.llm_service import ProviderKeyCandidate, llm_service
from app.services.modalities import EMBEDDINGS
from app.services.modality_pipeline import run_modality
from app.services.policy_service import PolicyConfig, policy_store
from app.services.routing_service import Candidate

ORG, USER, KEY = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
MODEL = "openai/text-embedding-3-small"


def entry(model_id=MODEL, level="internal", key_id=None):
	return Candidate(
		model_id=model_id, provider=model_id.split("/")[0], enabled=True, key_id=key_id or uuid.uuid4(), key_active=True,
		key_class=level, entry_class=level, regions=("us",), risk="low",
	)


@pytest.fixture
def world(monkeypatch):
	seen = SimpleNamespace(calls=[], key_requests=[], limit_checks=[], policy=PolicyConfig(), registry=[], limited=False, reply=None, error=None, key_error=None)

	async def aembedding(**kwargs):
		seen.calls.append(kwargs)
		if seen.error:
			raise seen.error
		return seen.reply or {"object": "list", "data": [{"object": "embedding", "index": 0, "embedding": [0.1, 0.2]}], "model": "m", "usage": {"prompt_tokens": 7, "total_tokens": 7}}

	async def select_keys(db, org_id, provider, model=None, redis=None, max_attempts=None, only_key_id=None):
		seen.key_requests.append({"provider": provider, "model": model, "only_key_id": only_key_id})
		if seen.key_error:
			raise seen.key_error
		return [ProviderKeyCandidate(KEY, "sk-test", None)]

	async def load(org_id, db, redis):
		return seen.policy

	async def routing_inputs(db, org_id):
		return list(seen.registry), "us"

	async def check_limits(**kwargs):
		seen.limit_checks.append(kwargs)
		if seen.limited:
			return (False, {"X-RateLimit-Remaining": "0"}, "rpm", "too many", 5)
		return (True, {"X-RateLimit-Remaining": "9"}, None, None, None)

	monkeypatch.setattr(llm_module, "aembedding", aembedding)
	monkeypatch.setattr(llm_module.settings, "DEBUG", False)  # the production behaviour: provider error text is not shown to clients
	monkeypatch.setattr(llm_service, "_select_provider_keys", select_keys)
	monkeypatch.setattr(llm_service, "routing_inputs", routing_inputs)
	monkeypatch.setattr(policy_store, "load", load)
	monkeypatch.setattr(rate_limiter.rate_limiter_service, "check_limits", check_limits)
	monkeypatch.setattr(llm_module.cost_tracker_service, "calculate_cost_usd", lambda _r: Decimal("0.000123"))
	return seen


async def call(world, *, model=MODEL, input="hello world", headers=None):
	"""Runs the endpoint and returns (response or HTTPException, the audit rows it scheduled)."""
	tasks = BackgroundTasks()
	logged = []
	http_request = SimpleNamespace(headers=headers or {}, state=SimpleNamespace(), client=SimpleNamespace(host="1.2.3.4"))
	user = SimpleNamespace(id=USER, org_id=ORG, budget_daily_usd=None)
	api_key = SimpleNamespace(id=uuid.uuid4(), team_id=None)

	async def fake_log(**kwargs):
		logged.append(kwargs)

	import app.services.llm_service as module
	original = module.log_request
	module.log_request = fake_log
	try:
		try:
			result = await run_modality(
				EMBEDDINGS, EmbeddingRequest(model=model, input=input), db=MagicMock(), redis=MagicMock(), user=user, api_key=api_key,
				request_id=uuid.uuid4(), background_tasks=tasks, http_request=http_request,
			)
		except HTTPException as exc:
			result = exc
		for task in tasks.tasks:
			await task.func(**task.kwargs) if task.func is not original else await fake_log(**task.kwargs)
		await _drain_detached()
	finally:
		module.log_request = original
	return result, logged


async def _drain_detached():
	import asyncio

	pending = list(llm_module._DETACHED_TASKS)
	if pending:
		await asyncio.gather(*pending, return_exceptions=True)


def body(response):
	return json.loads(response.body)


async def test_a_successful_call_returns_the_provider_body_with_gateway_headers_and_one_audit_row(world):
	response, logged = await call(world)
	assert response.status_code == 200 and body(response)["data"][0]["embedding"] == [0.1, 0.2]
	assert response.headers["x-openproxyai-provider"] == "openai" and response.headers["x-openproxyai-model"] == MODEL
	assert response.headers["x-openproxyai-cost-usd"] == "0.000123" and response.headers["x-openproxyai-gateway-error"] == "false"
	assert response.headers["x-ratelimit-remaining"] == "9" and response.headers["x-openproxyai-data-class"] == "internal"
	sent = world.calls[0]
	assert (sent["model"], sent["input"], sent["api_key"], sent["encoding_format"]) == (MODEL, "hello world", "sk-test", "float")
	assert len(logged) == 1
	row = logged[0]
	assert (row["status_code"], row["prompt_tokens"], row["completion_tokens"], row["provider_key_id"], row["model"]) == (200, 7, 0, KEY, MODEL)
	assert row["request_metadata"]["data_class"]["class"] == "internal"


async def test_a_list_input_is_sent_whole(world):
	await call(world, input=["a", "b", "c"])
	assert world.calls[0]["input"] == ["a", "b", "c"]
	assert world.limit_checks[0]["request_tokens_estimate"] >= 1


async def test_a_policy_block_is_a_446_refusal_that_never_reaches_the_provider(world):
	world.policy = PolicyConfig(enforcement_mode="enforce", blocked_keywords=["forbidden"])
	response, logged = await call(world, input="this is forbidden text")
	assert response.status_code == 446 and body(response)["error"] == "policy_violation"
	assert world.calls == [] and [r["status_code"] for r in logged] == [446]
	assert logged[0]["error_message"].startswith("policy_blocked:")


async def test_a_pii_prompt_is_classified_confidential_and_reported(world):
	response, logged = await call(world, input="my ssn is 123-45-6789")
	assert response.status_code == 200
	assert response.headers["x-openproxyai-data-class"] == "confidential"
	assert logged[0]["request_metadata"]["data_class"]["entities"]


async def test_the_data_class_header_can_raise_the_class_and_a_bad_value_is_a_400(world):
	response, _ = await call(world, headers={"x-openproxy-data-class": "secret"})
	assert response.headers["x-openproxyai-data-class"] == "secret"
	failure, logged = await call(world, headers={"x-openproxy-data-class": "nonsense"})
	assert isinstance(failure, HTTPException) and failure.status_code == 400 and failure.detail["error"] == "invalid_data_class"
	assert logged and logged[0]["status_code"] == 400


async def test_enforced_routing_refuses_a_model_not_cleared_for_the_data_class(world):
	world.policy = PolicyConfig(routing_mode="enforce")
	world.registry = [entry(level="internal")]
	response, logged = await call(world, headers={"x-openproxy-data-class": "confidential"})
	assert response.status_code == 446 and body(response)["error"] == "routing_blocked"
	assert body(response)["route_reason"] == "not_authorized:class_too_low"
	assert world.calls == [] and logged[0]["status_code"] == 446 and logged[0]["error_message"] == "policy_blocked:no_authorized_model"
	assert logged[0]["request_metadata"]["routing"]["reason"] == "not_authorized:class_too_low"


async def test_enforced_routing_serves_through_the_registry_key_only(world):
	registry_key = uuid.uuid4()
	world.policy = PolicyConfig(routing_mode="enforce")
	world.registry = [entry(key_id=registry_key)]
	response, _ = await call(world)
	assert response.status_code == 200
	assert world.key_requests[0]["only_key_id"] == registry_key
	assert response.headers["x-openproxyai-route-model"] == MODEL


async def test_log_only_routing_records_the_decision_and_never_restricts_the_key(world):
	world.policy = PolicyConfig(routing_mode="log_only")
	world.registry = []
	response, logged = await call(world)
	assert response.status_code == 200 and world.key_requests[0]["only_key_id"] is None
	assert logged[0]["request_metadata"]["routing"]["mode"] == "log_only"


async def test_a_rate_limited_call_is_a_429_with_its_headers_and_never_reaches_the_provider(world):
	world.limited = True
	response, logged = await call(world)
	assert response.status_code == 429 and body(response)["limit_type"] == "rpm"
	assert response.headers["x-ratelimit-remaining"] == "0" and world.calls == []
	assert [r["status_code"] for r in logged] == [429] and logged[0]["error_message"] == "rate_limited:rpm"


async def test_the_rate_limit_is_checked_for_the_model_and_the_org_policy(world):
	await call(world)
	check = world.limit_checks[0]
	assert check["model"] == MODEL and check["policy_config"] is world.policy and check["org_id"] == str(ORG)


async def test_no_usable_key_is_the_keys_own_error_and_is_audited(world):
	world.key_error = HTTPException(status_code=503, detail={"error": "no_provider_key", "detail": "No provider keys available"})
	failure, logged = await call(world)
	assert isinstance(failure, HTTPException) and failure.status_code == 503
	assert failure.headers["X-RateLimit-Remaining"] == "9"  # the limit headers still travel with the error
	assert [r["status_code"] for r in logged] == [503]


async def test_a_provider_failure_is_a_502_with_a_public_message_and_an_audit_row(world):
	world.error = RuntimeError("upstream exploded sk-secret")
	failure, logged = await call(world)
	assert isinstance(failure, HTTPException) and failure.status_code == 502 and failure.detail["error"] == "provider_error"
	assert "sk-secret" not in json.dumps(failure.detail)
	assert [r["status_code"] for r in logged] == [502] and logged[0]["prompt_tokens"] == 0


async def test_a_provider_timeout_is_a_504(world):
	world.error = TimeoutError("took too long")
	failure, logged = await call(world)
	assert isinstance(failure, HTTPException) and failure.status_code == 504 and failure.detail["error"] == "provider_timeout"
	assert [r["status_code"] for r in logged] == [504]


async def test_a_model_without_a_provider_is_a_400_before_anything_else_happens(world):
	failure, _ = await call(world, model="no-slash")
	assert isinstance(failure, HTTPException) and failure.status_code == 400 and world.calls == [] and world.limit_checks == []
