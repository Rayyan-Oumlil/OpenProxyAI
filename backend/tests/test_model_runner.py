"""Calling a model from inside the gateway (eval runs, judges): same policy, routing and metering as a client request."""

from __future__ import annotations

import uuid
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services import model_runner as runner
from app.services.llm_service import ProviderKeyCandidate
from app.services.policy_service import PolicyConfig

ORG, USER = uuid.uuid4(), uuid.uuid4()
MESSAGES = [{"role": "user", "content": "What is 2+2?"}]


def completion(text="4", prompt_tokens=7, completion_tokens=2):
	return SimpleNamespace(
		choices=[SimpleNamespace(message=SimpleNamespace(content=text))],
		usage=SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens),
	)


@pytest.fixture
def world(monkeypatch):
	"""The provider, key selection, policy, metering and audit log, all replaced, recording what happens."""
	seen = SimpleNamespace(calls=[], logs=[], key_requests=[])

	async def acompletion(**kwargs):
		seen.calls.append(kwargs)
		if isinstance(seen.reply, Exception):
			raise seen.reply
		return seen.reply

	async def select_keys(db, org_id, provider, model=None, max_attempts=None, only_key_id=None, **_):
		seen.key_requests.append((provider, model, only_key_id))
		if seen.key_error:
			raise seen.key_error
		return [ProviderKeyCandidate(uuid.uuid4(), "sk-test", None, False)]

	async def log_request(**kwargs):
		seen.logs.append(kwargs)

	seen.reply = completion()
	seen.key_error = None
	seen.policy_allows = True
	seen.routing = None
	monkeypatch.setattr(runner, "acompletion", acompletion)
	monkeypatch.setattr(runner.llm_service, "_select_provider_keys", select_keys)
	monkeypatch.setattr(runner, "log_request", log_request)
	monkeypatch.setattr(runner.cost_tracker_service, "calculate_cost_usd", lambda response: Decimal("0.0012"))

	async def evaluate(request, config):
		return SimpleNamespace(allowed=seen.policy_allows, detail="Blocked: keyword", reason_code="blocked_keyword")

	monkeypatch.setattr(runner.policy_service, "evaluate_chat_request", evaluate)
	monkeypatch.setattr(runner, "route_decision", lambda *a, **k: seen.routing)
	monkeypatch.setattr(runner.llm_service, "routing_inputs", AsyncMock(return_value=([], "us")))
	return seen


async def run(world, model="openai/gpt-4o-mini", config=None, **kwargs):
	return await runner.run_prompt(
		db=MagicMock(), redis=MagicMock(), org_id=ORG, user_id=USER, model=model, messages=MESSAGES,
		policy_config=config or PolicyConfig(), source="eval_run", **kwargs,
	)


async def test_a_successful_call_returns_the_answer_its_usage_and_its_cost(world):
	outcome = await run(world)
	assert (outcome.content, outcome.prompt_tokens, outcome.completion_tokens, outcome.cost_usd) == ("4", 7, 2, Decimal("0.0012"))
	assert outcome.error is None and outcome.refused is False and outcome.latency_ms >= 0
	[call] = world.calls
	assert call["model"] == "openai/gpt-4o-mini" and call["messages"] == MESSAGES and call["api_key"] == "sk-test"


async def test_every_call_is_written_to_the_audit_log_tagged_with_its_source(world):
	await run(world, extra_metadata={"eval_run_id": "r1"})
	[log] = world.logs
	assert (log["org_id"], log["user_id"], log["model"], log["status_code"]) == (ORG, USER, "openai/gpt-4o-mini", 200)
	assert log["api_key_id"] is None and log["prompt_tokens"] == 7 and log["cost_usd"] == Decimal("0.0012")
	assert log["request_metadata"]["source"] == "eval_run" and log["request_metadata"]["eval_run_id"] == "r1"


async def test_a_policy_block_is_a_refusal_and_nothing_reaches_the_provider(world):
	world.policy_allows = False
	outcome = await run(world)
	assert outcome.refused is True and "keyword" in outcome.error and outcome.content == ""
	assert world.calls == [] and world.key_requests == []
	assert world.logs[0]["status_code"] == 446  # the same status a blocked client request gets


async def test_a_routing_refusal_is_a_refusal_and_nothing_reaches_the_provider(world):
	world.routing = SimpleNamespace(blocked=True, reason="not_authorized:class_too_low", mode="enforce", key_id=None, as_metadata=lambda: {"model": None})
	outcome = await run(world, config=PolicyConfig(routing_mode="enforce"))
	assert outcome.refused is True and "class_too_low" in outcome.error and world.calls == []


async def test_with_routing_enforced_only_the_registry_key_is_used(world):
	key_id = uuid.uuid4()
	world.routing = SimpleNamespace(blocked=False, reason="authorized", mode="enforce", key_id=key_id, as_metadata=lambda: {"model": "openai/gpt-4o-mini"})
	await run(world, config=PolicyConfig(routing_mode="enforce"))
	assert world.key_requests == [("openai", "gpt-4o-mini", key_id)]


async def test_a_provider_failure_is_reported_not_raised_and_is_logged_as_a_failure(world):
	world.reply = RuntimeError("upstream exploded")
	outcome = await run(world)
	assert outcome.error == "upstream exploded" and outcome.refused is False and outcome.content == ""
	assert world.logs[0]["status_code"] == 502 and world.logs[0]["cost_usd"] == Decimal("0")


async def test_no_usable_provider_key_is_reported_not_raised(world):
	from fastapi import HTTPException

	world.key_error = HTTPException(status_code=503, detail={"error": "no_provider_key", "detail": "No key for this provider"})
	outcome = await run(world)
	assert "No key for this provider" in outcome.error and outcome.refused is False and world.calls == []


async def test_temperature_and_max_tokens_are_passed_only_when_given(world):
	await run(world)
	await run(world, temperature=0.0, max_tokens=50)
	assert "temperature" not in world.calls[0] and "max_tokens" not in world.calls[0]
	assert (world.calls[1]["temperature"], world.calls[1]["max_tokens"]) == (0.0, 50)


async def test_a_failure_to_write_the_audit_log_does_not_lose_the_answer(world, monkeypatch):
	async def broken(**kwargs):
		raise RuntimeError("log database down")

	monkeypatch.setattr(runner, "log_request", broken)
	outcome = await run(world)
	assert outcome.content == "4" and outcome.error is None


async def test_a_malformed_model_name_is_an_error_outcome(world):
	outcome = await run(world, model="gpt-4o-mini")  # no provider prefix
	assert outcome.error and outcome.refused is False and world.calls == []
