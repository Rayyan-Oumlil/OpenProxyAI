"""Tests for response guardrail enforcement in the non-streaming LLM path."""

from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from tests.conftest import FakeDB

from app.services.policy_service import PolicyConfig, PolicyDecision


# ── Helpers ──────────────────────────────────────────────────────────────────


class _FakeMessage:
	"""Mutable message object so we can replace .content for redaction."""

	def __init__(self, content: str) -> None:
		self.content = content
		self.role = "assistant"


class _FakeLiteLLMResponse:
	"""Minimal fake LiteLLM ModelResponse with model_dump() so _to_jsonable works."""

	def __init__(self, content: str) -> None:
		self._message = _FakeMessage(content)
		self.choices = [SimpleNamespace(message=self._message, index=0, finish_reason="stop")]
		self.usage = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
		self.model = "openai/gpt-4o-mini"
		self.id = "chatcmpl_test"
		self.object = "chat.completion"

	def model_dump(self, **kwargs):
		return {
			"id": self.id,
			"object": self.object,
			"model": self.model,
			"choices": [
				{
					"index": 0,
					"message": {
						"role": self._message.role,
						"content": self._message.content,
					},
					"finish_reason": "stop",
				}
			],
			"usage": self.usage,
		}


def _make_litellm_response(content: str) -> _FakeLiteLLMResponse:
	"""Minimal fake LiteLLM response object shaped like ModelResponse."""
	return _FakeLiteLLMResponse(content)


def _make_policy_config(**overrides) -> PolicyConfig:
	"""Build a PolicyConfig with response guardrails enabled by default."""
	cfg = PolicyConfig(
		enforcement_mode="enforce",
		response_guardrails_enabled=True,
		response_pii_redact=False,
	)
	for key, value in overrides.items():
		setattr(cfg, key, value)
	return cfg


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def fake_redis(request):
	"""Re-use the FakeRedis class from conftest (already in scope via conftest.py)."""
	from tests.conftest import FakeRedis
	return FakeRedis()


# ── Tests ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_response_blocked_keyword_enforcement_mode(monkeypatch, fake_redis):
	"""Non-streaming response containing a blocked keyword raises HTTP 446 when enforcement_mode=enforce."""
	from app.services import llm_service as llm_service_module

	BLOCKED_WORD = "badword"
	policy_cfg = _make_policy_config(
		enforcement_mode="enforce",
		response_guardrails_enabled=True,
		blocked_keywords=[BLOCKED_WORD],
	)

	request = llm_service_module.ChatCompletionRequest(
		model="openai/gpt-4o-mini",
		messages=[{"role": "user", "content": "tell me something"}],
		stream=False,
	)
	user = SimpleNamespace(id=uuid4(), org_id=uuid4(), budget_daily_usd=Decimal("50"))
	api_key = SimpleNamespace(id=uuid4())
	fake_llm_response = _make_litellm_response(f"Here is the answer: {BLOCKED_WORD} in it.")

	# ── Patches ──────────────────────────────────────────────────────────────

	async def _fake_load(org_id, db, redis):
		return policy_cfg

	async def _fake_check_limits(**kwargs):
		return (
			True,
			{"X-RateLimit-Requests-Remaining": "59"},
			None,
			None,
			None,
		)

	async def _fake_provider_key(*args, **kwargs):
		return [(None, "sk-fake")]

	async def _fake_acompletion(**kwargs):
		return fake_llm_response

	def _fake_calculate_cost(response):
		return Decimal("0.000010")

	async def _fake_log(**kwargs):
		return None

	monkeypatch.setattr(llm_service_module.policy_store, "load", _fake_load)
	monkeypatch.setattr(llm_service_module.rate_limiter_service, "check_limits", _fake_check_limits)
	monkeypatch.setattr(llm_service_module.llm_service, "_select_provider_keys", _fake_provider_key)
	monkeypatch.setattr(llm_service_module, "acompletion", _fake_acompletion)
	monkeypatch.setattr(llm_service_module.cost_tracker_service, "calculate_cost_usd", _fake_calculate_cost)
	monkeypatch.setattr(llm_service_module, "log_request", _fake_log)

	with pytest.raises(HTTPException) as exc_info:
		await llm_service_module.llm_service.chat_completion(
			request=request,
			db=FakeDB(),
			redis=fake_redis,
			user=user,
			api_key=api_key,
			request_id=uuid4(),
			background_tasks=SimpleNamespace(add_task=lambda *a, **kw: None),
		)

	exc = exc_info.value
	assert exc.status_code == 446
	assert exc.detail["error"]["code"] == "response_policy_violation"


@pytest.mark.asyncio
async def test_response_pii_redacted_when_response_pii_redact_true(monkeypatch, fake_redis):
	"""Non-streaming response with PII is redacted (not blocked) when response_pii_redact=True."""
	from app.services import llm_service as llm_service_module

	ORIGINAL_CONTENT = "The user email is john@example.com and SSN is 123-45-6789."
	REDACTED_CONTENT = "The user email is [REDACTED] and SSN is [REDACTED]."

	policy_cfg = _make_policy_config(
		enforcement_mode="enforce",
		response_guardrails_enabled=True,
		response_pii_redact=True,
		pii_detection_enabled=True,
	)

	request = llm_service_module.ChatCompletionRequest(
		model="openai/gpt-4o-mini",
		messages=[{"role": "user", "content": "what is my info?"}],
		stream=False,
	)
	user = SimpleNamespace(id=uuid4(), org_id=uuid4(), budget_daily_usd=Decimal("50"))
	api_key = SimpleNamespace(id=uuid4())
	fake_llm_response = _make_litellm_response(ORIGINAL_CONTENT)

	# ── Patches ──────────────────────────────────────────────────────────────

	async def _fake_load(org_id, db, redis):
		return policy_cfg

	async def _fake_check_limits(**kwargs):
		return (True, {"X-RateLimit-Requests-Remaining": "59"}, None, None, None)

	async def _fake_provider_key(*args, **kwargs):
		return [(None, "sk-fake")]

	async def _fake_acompletion(**kwargs):
		return fake_llm_response

	def _fake_calculate_cost(response):
		return Decimal("0.000010")

	async def _fake_log(**kwargs):
		return None

	# Patch evaluate_response on the bound instance — receives (response_text, config)
	def _fake_evaluate_response(response_text, config):
		decision = PolicyDecision(allowed=True)
		decision.redacted_text = REDACTED_CONTENT
		decision.reason_code = "response_pii_detected"
		return decision

	monkeypatch.setattr(llm_service_module.policy_store, "load", _fake_load)
	monkeypatch.setattr(llm_service_module.rate_limiter_service, "check_limits", _fake_check_limits)
	monkeypatch.setattr(llm_service_module.llm_service, "_select_provider_keys", _fake_provider_key)
	monkeypatch.setattr(llm_service_module, "acompletion", _fake_acompletion)
	monkeypatch.setattr(llm_service_module.cost_tracker_service, "calculate_cost_usd", _fake_calculate_cost)
	monkeypatch.setattr(llm_service_module, "log_request", _fake_log)
	monkeypatch.setattr(llm_service_module.policy_service, "evaluate_response", _fake_evaluate_response)

	response = await llm_service_module.llm_service.chat_completion(
		request=request,
		db=FakeDB(),
		redis=fake_redis,
		user=user,
		api_key=api_key,
		request_id=uuid4(),
		background_tasks=SimpleNamespace(add_task=lambda *a, **kw: None),
	)

	assert response.status_code == 200
	import json
	body = json.loads(response.body)
	# The content in the response should be the redacted version
	content_in_response = body["choices"][0]["message"]["content"]
	assert content_in_response == REDACTED_CONTENT


@pytest.mark.asyncio
async def test_response_blocked_keyword_log_only_mode_passes_through(monkeypatch, fake_redis):
	"""Non-streaming response with blocked keyword passes through (no 446) when enforcement_mode=log_only."""
	from app.services import llm_service as llm_service_module

	BLOCKED_WORD = "badword"
	policy_cfg = _make_policy_config(
		enforcement_mode="log_only",
		response_guardrails_enabled=True,
		blocked_keywords=[BLOCKED_WORD],
	)

	request = llm_service_module.ChatCompletionRequest(
		model="openai/gpt-4o-mini",
		messages=[{"role": "user", "content": "tell me something"}],
		stream=False,
	)
	user = SimpleNamespace(id=uuid4(), org_id=uuid4(), budget_daily_usd=Decimal("50"))
	api_key = SimpleNamespace(id=uuid4())
	fake_llm_response = _make_litellm_response(f"Here is the answer: {BLOCKED_WORD} in it.")

	# ── Patches ──────────────────────────────────────────────────────────────

	async def _fake_load(org_id, db, redis):
		return policy_cfg

	async def _fake_check_limits(**kwargs):
		return (True, {"X-RateLimit-Requests-Remaining": "59"}, None, None, None)

	async def _fake_provider_key(*args, **kwargs):
		return [(None, "sk-fake")]

	async def _fake_acompletion(**kwargs):
		return fake_llm_response

	def _fake_calculate_cost(response):
		return Decimal("0.000010")

	async def _fake_log(**kwargs):
		return None

	monkeypatch.setattr(llm_service_module.policy_store, "load", _fake_load)
	monkeypatch.setattr(llm_service_module.rate_limiter_service, "check_limits", _fake_check_limits)
	monkeypatch.setattr(llm_service_module.llm_service, "_select_provider_keys", _fake_provider_key)
	monkeypatch.setattr(llm_service_module, "acompletion", _fake_acompletion)
	monkeypatch.setattr(llm_service_module.cost_tracker_service, "calculate_cost_usd", _fake_calculate_cost)
	monkeypatch.setattr(llm_service_module, "log_request", _fake_log)

	# Should NOT raise — log_only mode lets the response through
	response = await llm_service_module.llm_service.chat_completion(
		request=request,
		db=FakeDB(),
		redis=fake_redis,
		user=user,
		api_key=api_key,
		request_id=uuid4(),
		background_tasks=SimpleNamespace(add_task=lambda *a, **kw: None),
	)

	assert response.status_code == 200
	import json
	body = json.loads(response.body)
	assert body["choices"][0]["message"]["content"] == f"Here is the answer: {BLOCKED_WORD} in it."
