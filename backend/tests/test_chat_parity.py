"""Chat must keep the guarantees the shared pipeline gives every other endpoint (Phase 5).

Chat has its own orchestration (cache, experiments, templates, streaming, tool taint), so it is not run through ``run_modality``.
What stops the two from drifting is this file: the same questions ``test_modalities_pipeline`` asks of every modality, asked of chat.
A guarantee added to one and not the other shows up here.
"""

from __future__ import annotations

import json
import uuid
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import BackgroundTasks, HTTPException

from app.schemas.chat import ChatCompletionRequest, Message
from app.services import llm_service as llm_module
from app.services import rate_limiter
from app.services.llm_service import ProviderKeyCandidate, llm_service
from app.services.policy_service import PolicyConfig, policy_store
from tests.test_embeddings_pipeline import entry

ORG, USER, KEY = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
MODEL = "openai/gpt-4o"


class Reply:
	choices = [SimpleNamespace(message=SimpleNamespace(content="the reply", role="assistant"), index=0, finish_reason="stop")]
	usage = {"prompt_tokens": 12, "completion_tokens": 5, "total_tokens": 17}

	def model_dump(self, **_k):
		return {"id": "c1", "object": "chat.completion", "model": MODEL, "choices": [{"index": 0, "message": {"role": "assistant", "content": "the reply"}, "finish_reason": "stop"}], "usage": self.usage}


@pytest.fixture
def case(monkeypatch):
	seen = SimpleNamespace(calls=[], key_requests=[], limit_checks=[], policy=PolicyConfig(), registry=[], limited=False, error=None)

	async def provider(**kwargs):
		seen.calls.append(kwargs)
		if seen.error:
			raise seen.error
		return Reply()

	async def select_keys(db, org_id, provider_name, model=None, redis=None, max_attempts=None, only_key_id=None):
		seen.key_requests.append(only_key_id)
		return [ProviderKeyCandidate(KEY, "sk-test", None)]

	async def load(org_id, db, redis):
		return seen.policy

	async def routing_inputs(db, org_id):
		return list(seen.registry), "us"

	async def check_limits(**kwargs):
		seen.limit_checks.append(kwargs)
		return (False, {}, "rpm", "slow down", 3) if seen.limited else (True, {}, None, None, None)

	async def no_experiment(db, org_id, model):
		return model, None

	async def no_taint(ctx, db):
		return None

	async def no_cache(*_a, **_k):
		return None, None

	monkeypatch.setattr(llm_module, "acompletion", provider)
	monkeypatch.setattr(llm_module.settings, "DEBUG", False)
	monkeypatch.setattr(llm_service, "_select_provider_keys", select_keys)
	monkeypatch.setattr(llm_service, "routing_inputs", routing_inputs)
	monkeypatch.setattr(llm_service, "_resolve_experiment", no_experiment)
	monkeypatch.setattr(llm_service, "_apply_tool_taint", no_taint)
	monkeypatch.setattr(llm_module.cache_service, "get", no_cache)
	monkeypatch.setattr(llm_module.cache_service, "is_enabled", lambda: False)
	monkeypatch.setattr(policy_store, "load", load)
	monkeypatch.setattr(rate_limiter.rate_limiter_service, "check_limits", check_limits)
	monkeypatch.setattr(llm_module.cost_tracker_service, "calculate_cost_usd", lambda _r, call_type=None: Decimal("0.001"))
	return seen


async def send(case, *, text="the answer", model=MODEL, headers=None):
	logged = []

	async def fake_log(**kwargs):
		logged.append(kwargs)

	tasks, original = BackgroundTasks(), llm_module.log_request
	llm_module.log_request = fake_log
	user, api_key = SimpleNamespace(id=USER, org_id=ORG, budget_daily_usd=None), SimpleNamespace(id=uuid.uuid4(), team_id=None)
	try:
		try:
			result = await llm_service.chat_completion(
				ChatCompletionRequest(model=model, messages=[Message(role="user", content=text)]), MagicMock(), MagicMock(), user, api_key, uuid.uuid4(), tasks,
				SimpleNamespace(headers=headers or {}, state=SimpleNamespace(), client=SimpleNamespace(host="1.2.3.4")),
			)
		except HTTPException as exc:
			result = exc
		for task in tasks.tasks:
			await fake_log(**task.kwargs)
		import asyncio
		if llm_module._DETACHED_TASKS:
			await asyncio.gather(*list(llm_module._DETACHED_TASKS), return_exceptions=True)
	finally:
		llm_module.log_request = original
	return result, logged


async def test_a_successful_call_reaches_the_provider_with_the_key_and_is_audited(case):
	response, logged = await send(case)
	assert response.status_code == 200 and response.headers["x-openproxyai-model"] == MODEL
	assert case.calls[0]["api_key"] == "sk-test" and case.calls[0]["model"] == MODEL
	assert [row["status_code"] for row in logged] == [200] and logged[0]["provider_key_id"] == KEY and logged[0]["prompt_tokens"] == 12


async def test_a_policy_block_is_a_446_and_the_provider_never_sees_the_text(case):
	case.policy = PolicyConfig(enforcement_mode="enforce", blocked_keywords=["forbidden"])
	response, logged = await send(case, text="this is forbidden")
	assert response.status_code == 446 and case.calls == [] and [row["status_code"] for row in logged] == [446]


async def test_pii_in_the_request_raises_its_class(case):
	response, logged = await send(case, text="ssn 123-45-6789")
	assert response.headers["x-openproxyai-data-class"] == "confidential" and logged[0]["request_metadata"]["data_class"]["entities"]


async def test_enforced_routing_refuses_an_unregistered_model_and_a_model_not_cleared_for_the_data_class(case):
	case.policy = PolicyConfig(routing_mode="enforce")
	response, _ = await send(case)
	assert response.status_code == 446 and json.loads(response.body)["route_reason"] == "not_in_registry" and case.calls == []
	case.registry = [entry(MODEL, level="internal")]
	response, _ = await send(case, headers={"x-openproxy-data-class": "secret"})
	assert response.status_code == 446 and case.calls == []
	response, _ = await send(case)
	assert response.status_code == 200 and case.key_requests[-1] == case.registry[0].key_id


async def test_rate_limits_apply_and_are_sized_from_the_request(case):
	case.limited = True
	response, logged = await send(case)
	assert response.status_code == 429 and case.calls == [] and [row["status_code"] for row in logged] == [429]
	assert case.limit_checks[0]["request_tokens_estimate"] >= 1


async def test_a_provider_failure_is_a_502_that_does_not_echo_provider_text(case):
	case.error = RuntimeError("boom sk-secret")
	failure, logged = await send(case)
	assert isinstance(failure, HTTPException) and failure.status_code == 502 and "sk-secret" not in json.dumps(failure.detail)
	assert [row["status_code"] for row in logged] == [502]


async def test_a_model_litellm_cannot_price_still_returns_its_answer_and_is_charged_a_flat_fallback_never_zero(case, monkeypatch):
	def unpriced(_response, call_type=None):
		raise ValueError("model not in the price map")

	monkeypatch.setattr(llm_module.cost_tracker_service, "calculate_cost_usd", unpriced)
	monkeypatch.setattr(llm_module.settings, "UNPRICED_CALL_COST_USD", 0.02)
	response, logged = await send(case)
	assert response.status_code == 200 and logged[0]["status_code"] == 200
	assert logged[0]["cost_usd"] == Decimal("0.02") and logged[0]["request_metadata"]["cost_estimated"] is True


async def test_a_streamed_answer_from_a_model_litellm_cannot_price_is_still_audited_and_charged_the_flat_fee(monkeypatch, fake_redis):
	"""The unpriced rule holds for streams too: the pricing error used to escape the stream's close, leaving the spend uncounted."""
	from tests.test_streaming_usage import USAGE_CHUNK, _delta, _start

	def unpriced(_response, call_type=None):
		raise ValueError("model not in the price map")

	response, _, logs, background_tasks = await _start(monkeypatch, fake_redis, [_delta("a"), USAGE_CHUNK])
	monkeypatch.setattr(llm_module.cost_tracker_service, "calculate_cost_usd", unpriced)
	monkeypatch.setattr(llm_module.settings, "UNPRICED_CALL_COST_USD", 0.02)
	[_ async for _ in response.body_iterator]
	await background_tasks()
	assert [r["status_code"] for r in logs] == [200] and logs[0]["cost_usd"] == Decimal("0.02") and logs[0]["request_metadata"]["cost_estimated"] is True
