"""The playground compare endpoint obeys the same data-class routing as chat: it must not be a way around it."""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from app.dependencies import get_current_user_from_jwt, get_db, get_redis
from app.main import app
from app.routes import playground as pg  # noqa: F401  (imported so the route is registered)
from app.services import model_runner as mr
from app.services.llm_service import llm_service
from app.services import policy_service as ps
from app.services import rate_limiter
from app.services.llm_service import ProviderKeyCandidate
from app.services.policy_service import PolicyConfig
from app.services.routing_service import Candidate
from tests.test_playground import FakeDB, FakeRedis

SSN_TEXT = "My SSN is 123-45-6789, summarize this."
MODELS = ["openai/gpt-4o", "anthropic/claude-3-5-sonnet"]


def candidate(model_id, *, entry_class="confidential", key_class="confidential", key_id=None):
	return Candidate(
		model_id=model_id, provider=model_id.split("/")[0], enabled=True, key_id=key_id or uuid.uuid4(), key_active=True,
		key_class=key_class, entry_class=entry_class, regions=("us",), risk="medium",
	)


@pytest.fixture
def harness(client, monkeypatch):
	"""Wire the endpoint with fakes and record what it does: which keys were chosen and which models were really called."""
	seen = SimpleNamespace(selected=[], called=[], logs=[], order=[])

	async def fake_acompletion(**kwargs):
		seen.called.append(kwargs)
		seen.order.append(("call", kwargs["model"]))
		return SimpleNamespace(
			model=kwargs["model"], choices=[SimpleNamespace(message=SimpleNamespace(content="answer"))],
			usage=SimpleNamespace(prompt_tokens=3, completion_tokens=2),
		)

	async def fake_select_key(db, org_id, provider, model=None, only_key_id=None):
		seen.selected.append((provider, only_key_id))
		seen.order.append(("select", provider))
		return ProviderKeyCandidate(only_key_id, f"sk-{provider}", None)

	async def noop_log(*args, **kwargs):
		seen.logs.append(kwargs)

	def as_keys(fn):
		"""The runner asks for a list of keys and takes the first; the fakes below return one."""
		async def wrapper(db, org_id, provider, model=None, redis=None, max_attempts=None, only_key_id=None):
			return [await fn(db, org_id, provider, model=model, only_key_id=only_key_id)]
		return wrapper

	seen.as_keys = as_keys

	def configure(*, mode="off", registry=(), region="us"):
		user = SimpleNamespace(id=uuid.uuid4(), org_id=uuid.uuid4(), role="admin", is_active=True, budget_daily_usd=None)

		async def fake_user():
			return user

		async def fake_db():
			yield FakeDB()

		async def fake_redis():
			return FakeRedis()

		async def fake_limits(*a, **k):
			return (True, {}, None, None, None)

		async def fake_policy(*a, **k):
			return PolicyConfig(routing_mode=mode)

		async def fake_inputs(db, org_id):
			return list(registry), region

		monkeypatch.setattr(mr.cost_tracker_service, "calculate_cost_usd", lambda _response: 0)  # not what is under test
		monkeypatch.setattr(mr, "acompletion", fake_acompletion)
		monkeypatch.setattr(llm_service, "_select_provider_keys", as_keys(fake_select_key))
		monkeypatch.setattr(mr, "log_request", noop_log)
		monkeypatch.setattr(llm_service, "routing_inputs", fake_inputs)
		monkeypatch.setattr(rate_limiter.rate_limiter_service, "check_limits", fake_limits)
		monkeypatch.setattr(ps.policy_store, "load", fake_policy)
		app.dependency_overrides[get_current_user_from_jwt] = fake_user
		app.dependency_overrides[get_db] = fake_db
		app.dependency_overrides[get_redis] = fake_redis

	def compare(content="hello", models=MODELS):
		return client.post(
			"/api/v1/playground/compare", headers={"Authorization": "Bearer x"},
			json={"models": models, "messages": [{"role": "user", "content": content}]},
		)

	seen.configure, seen.compare = configure, compare
	return seen


def test_with_routing_off_every_model_is_called_with_the_normal_key_choice(harness):
	harness.configure(mode="off")
	response = harness.compare(SSN_TEXT)
	assert response.status_code == 200
	assert [r["error"] for r in response.json()["results"]] == [None, None]
	assert [only for _, only in harness.selected] == [None, None]  # no registry key forced
	assert {log["request_metadata"]["data_class"]["class"] for log in harness.logs} == {"confidential"}  # classified, even when off


def test_enforced_a_model_not_cleared_for_the_prompt_is_never_called_and_says_why(harness):
	cleared, not_cleared = candidate("openai/gpt-4o"), candidate("anthropic/claude-3-5-sonnet", entry_class="internal")
	harness.configure(mode="enforce", registry=[cleared, not_cleared])

	response = harness.compare(SSN_TEXT)  # SSN text is confidential

	results = {r["model"]: r for r in response.json()["results"]}
	assert results["openai/gpt-4o"]["error"] is None and results["openai/gpt-4o"]["content"] == "answer"
	assert results["anthropic/claude-3-5-sonnet"]["error"] == "Not authorized for confidential data: not_authorized:class_too_low"
	assert [kwargs["model"] for kwargs in harness.called] == ["openai/gpt-4o"]  # the other one never reached a provider
	refused = next(log for log in harness.logs if log["model"] == "anthropic/claude-3-5-sonnet")
	assert refused["status_code"] == 446 and refused["request_metadata"]["routing"]["reason"] == "not_authorized:class_too_low"


def test_enforced_each_model_is_served_only_by_its_registry_key(harness):
	first, second = candidate("openai/gpt-4o"), candidate("anthropic/claude-3-5-sonnet")
	harness.configure(mode="enforce", registry=[first, second])

	harness.compare("plain question")

	assert dict(harness.selected) == {"openai": first.key_id, "anthropic": second.key_id}


def test_a_model_missing_from_the_registry_is_refused_when_enforcing_but_only_noted_when_logging(harness):
	harness.configure(mode="enforce", registry=[candidate("openai/gpt-4o")])
	results = {r["model"]: r for r in harness.compare().json()["results"]}
	assert results["anthropic/claude-3-5-sonnet"]["error"] == "Not authorized for internal data: not_in_registry"
	assert len(harness.called) == 1

	harness.called.clear()
	harness.configure(mode="log_only", registry=[candidate("openai/gpt-4o")])
	results = {r["model"]: r for r in harness.compare().json()["results"]}
	assert all(r["error"] is None for r in results.values()) and len(harness.called) == 2  # log_only never refuses


def test_a_custom_endpoint_is_called_through_the_connection_guard_in_the_playground_too(harness, monkeypatch):
	harness.configure(mode="off")

	async def with_endpoint_key(db, org_id, provider, model=None, only_key_id=None):
		return ProviderKeyCandidate(None, "sk-vllm", "https://8.8.8.8/v1", False)

	monkeypatch.setattr(llm_service, "_select_provider_keys", harness.as_keys(with_endpoint_key))
	harness.compare()

	assert len(harness.called) == 2
	for kwargs in harness.called:
		assert kwargs["api_base"] == "https://8.8.8.8/v1"
		assert type(kwargs["client"]._client._transport).__name__ == "GuardedTransport"


def test_keys_are_chosen_one_after_another_before_any_model_is_called(harness):
	"""The model calls run concurrently, and a database session cannot be shared by concurrent tasks."""
	harness.configure(mode="off")
	harness.compare()
	kinds = [kind for kind, _ in harness.order]
	assert kinds == ["select", "select", "call", "call"]


def test_a_key_that_cannot_be_selected_becomes_that_models_error_not_a_failed_request(harness, monkeypatch):
	from fastapi import HTTPException

	harness.configure(mode="off")

	async def flaky(db, org_id, provider, model=None, only_key_id=None):
		if provider == "anthropic":
			raise HTTPException(status_code=503, detail={"error": "no_provider_key", "detail": "No provider keys available"})
		return ProviderKeyCandidate(None, "sk-ok", None)

	monkeypatch.setattr(llm_service, "_select_provider_keys", harness.as_keys(flaky))
	response = harness.compare()
	assert response.status_code == 200
	results = {r["model"]: r for r in response.json()["results"]}
	assert results["openai/gpt-4o"]["error"] is None and results["anthropic/claude-3-5-sonnet"]["error"] == "No provider keys available"
