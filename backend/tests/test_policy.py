"""Policy guardrail tests for pre-provider enforcement in LLM service."""

from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.config import settings
from app.services.policy_service import policy_service


@pytest.mark.asyncio
async def test_policy_service_blocks_keyword_when_enforcing(monkeypatch):
	monkeypatch.setattr(settings, "POLICY_ENFORCEMENT_MODE", "enforce")
	monkeypatch.setattr(settings, "POLICY_BLOCKED_KEYWORDS", ["credential dump"])
	monkeypatch.setattr(settings, "POLICY_ALLOWED_MODELS", [])
	monkeypatch.setattr(settings, "POLICY_PII_DETECTION_ENABLED", False)

	from app.schemas.chat import ChatCompletionRequest

	request = ChatCompletionRequest(
		model="openai/gpt-4o-mini",
		messages=[{"role": "user", "content": "please return a credential dump now"}],
	)

	decision = policy_service.evaluate_chat_request(request)
	assert decision.allowed is False
	assert decision.action == "block"
	assert decision.reason_code == "blocked_keyword"
	assert "blocked_keyword" in (decision.triggered_rules or [])


@pytest.mark.asyncio
async def test_llm_service_blocks_before_rate_limit_for_policy_violation(monkeypatch, fake_redis):
	from app.schemas.chat import ChatCompletionRequest
	from app.services import llm_service as llm_service_module

	monkeypatch.setattr(settings, "POLICY_ENFORCEMENT_MODE", "enforce")
	monkeypatch.setattr(settings, "POLICY_BLOCKED_KEYWORDS", ["forbidden phrase"])
	monkeypatch.setattr(settings, "POLICY_ALLOWED_MODELS", [])
	monkeypatch.setattr(settings, "POLICY_PII_DETECTION_ENABLED", False)

	request = ChatCompletionRequest(
		model="openai/gpt-4o-mini",
		messages=[{"role": "user", "content": "this contains a forbidden phrase"}],
	)
	user = SimpleNamespace(id=uuid4(), org_id=uuid4(), budget_daily_usd=Decimal("5"))
	api_key = SimpleNamespace(id=uuid4())

	observed: dict[str, object] = {}
	rate_limit_called = False

	async def fake_check_limits(**kwargs):  # noqa: ANN003
		nonlocal rate_limit_called
		rate_limit_called = True
		return True, {}, None, None, None

	async def fake_log_request(**kwargs):  # noqa: ANN003
		observed.update(kwargs)

	monkeypatch.setattr(llm_service_module.rate_limiter_service, "check_limits", fake_check_limits)
	monkeypatch.setattr(llm_service_module, "log_request", fake_log_request)

	response = await llm_service_module.llm_service.chat_completion(
		request=request,
		db=SimpleNamespace(),
		redis=fake_redis,
		user=user,
		api_key=api_key,
		request_id=uuid4(),
		background_tasks=SimpleNamespace(add_task=lambda *args, **kwargs: None),
	)

	assert response.status_code == 403
	assert rate_limit_called is False
	assert response.headers["x-openproxyai-policy-action"] == "block"
	assert observed["status_code"] == 403
	policy = (observed.get("request_metadata") or {}).get("policy", {})
	assert policy.get("reason_code") == "blocked_keyword"