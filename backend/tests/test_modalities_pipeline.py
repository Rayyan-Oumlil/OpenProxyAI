"""The guarantees every non-chat endpoint shares, proven once per modality (Phase 5).

Each case sends a request through the shared pipeline with the provider faked, and asks the same questions: is what the provider
received exactly what policy allowed, is a refusal a refusal, is the call audited. A new modality is added to ``CASES`` and inherits
the whole suite.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import BackgroundTasks, HTTPException

from app.schemas.modalities import RerankRequest
from app.services import llm_service as llm_module
from app.services import rate_limiter
from app.services.llm_service import ProviderKeyCandidate, llm_service
from app.services.modalities import RERANK
from app.services.modality_pipeline import run_modality
from app.services.policy_service import PolicyConfig, policy_store
from tests.test_embeddings_pipeline import entry

ORG, USER, KEY = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()

RERANK_REPLY = {"id": "r1", "results": [{"index": 1, "relevance_score": 0.9}, {"index": 0, "relevance_score": 0.2}], "meta": {"tokens": {"input_tokens": 21}}}


def rerank_request(model, text):
	return RerankRequest(model=model, query="which is best?", documents=["first doc", text])


# modality, request factory (model, text), provider function on llm_service, provider reply, default model
CASES = [(RERANK, rerank_request, "arerank", RERANK_REPLY, "cohere/rerank-english-v3.0")]


@pytest.fixture(params=CASES, ids=lambda c: c[0].name)
def case(request, monkeypatch):
	modality, make, fn, reply, model = request.param
	seen = SimpleNamespace(calls=[], key_requests=[], limit_checks=[], policy=PolicyConfig(), registry=[], limited=False, error=None, reply=reply)

	async def provider(**kwargs):
		seen.calls.append(kwargs)
		if seen.error:
			raise seen.error
		return seen.reply

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

	monkeypatch.setattr(llm_module, fn, provider)
	monkeypatch.setattr(llm_module.settings, "DEBUG", False)
	monkeypatch.setattr(llm_service, "_select_provider_keys", select_keys)
	monkeypatch.setattr(llm_service, "routing_inputs", routing_inputs)
	monkeypatch.setattr(policy_store, "load", load)
	monkeypatch.setattr(rate_limiter.rate_limiter_service, "check_limits", check_limits)
	monkeypatch.setattr(llm_module.cost_tracker_service, "calculate_cost_usd", lambda _r: Decimal("0.001"))
	seen.modality, seen.make, seen.model = modality, make, model
	return seen


async def send(case, *, text="the answer", model=None, headers=None):
	logged = []

	async def fake_log(**kwargs):
		logged.append(kwargs)

	tasks, original = BackgroundTasks(), llm_module.log_request
	llm_module.log_request = fake_log
	user, api_key = SimpleNamespace(id=USER, org_id=ORG, budget_daily_usd=None), SimpleNamespace(id=uuid.uuid4(), team_id=None)
	try:
		try:
			result = await run_modality(
				case.modality, case.make(model or case.model, text), db=MagicMock(), redis=MagicMock(), user=user, api_key=api_key, request_id=uuid.uuid4(),
				background_tasks=tasks, http_request=SimpleNamespace(headers=headers or {}, state=SimpleNamespace(), client=SimpleNamespace(host="1.2.3.4")),
			)
		except HTTPException as exc:
			result = exc
		for task in tasks.tasks:
			await fake_log(**task.kwargs)
		if llm_module._DETACHED_TASKS:
			await asyncio.gather(*list(llm_module._DETACHED_TASKS), return_exceptions=True)
	finally:
		llm_module.log_request = original
	return result, logged


async def test_a_successful_call_reaches_the_provider_with_the_key_and_is_audited(case):
	response, logged = await send(case)
	assert response.status_code == 200 and response.headers["x-openproxyai-model"] == case.model
	assert case.calls[0]["api_key"] == "sk-test" and case.calls[0]["model"] == case.model
	assert [row["status_code"] for row in logged] == [200] and logged[0]["provider_key_id"] == KEY and logged[0]["prompt_tokens"] > 0


async def test_a_policy_block_is_a_446_and_the_provider_never_sees_the_text(case):
	case.policy = PolicyConfig(enforcement_mode="enforce", blocked_keywords=["forbidden"])
	response, logged = await send(case, text="this is forbidden")
	assert response.status_code == 446 and case.calls == [] and [row["status_code"] for row in logged] == [446]


async def test_every_part_of_the_request_is_scanned_not_just_the_first_field(case):
	"""A marker in a later field (a document, not the query) is found: the whole request is one text to policy."""
	case.policy = PolicyConfig(enforcement_mode="enforce", blocked_keywords=["hidden-marker"])
	response, _ = await send(case, text="a document carrying hidden-marker")
	assert response.status_code == 446 and case.calls == []


async def test_pii_anywhere_in_the_request_raises_its_class(case):
	response, logged = await send(case, text="ssn 123-45-6789")
	assert response.headers["x-openproxyai-data-class"] == "confidential" and logged[0]["request_metadata"]["data_class"]["entities"]


async def test_enforced_routing_refuses_an_unregistered_model_and_a_model_not_cleared_for_the_data_class(case):
	case.policy = PolicyConfig(routing_mode="enforce")
	response, _ = await send(case)
	assert response.status_code == 446 and json.loads(response.body)["route_reason"] == "not_in_registry" and case.calls == []
	case.registry = [entry(case.model, level="internal")]
	response, _ = await send(case, headers={"x-openproxy-data-class": "confidential"})
	assert response.status_code == 446 and case.calls == []
	response, _ = await send(case)
	assert response.status_code == 200 and case.key_requests[-1] == case.registry[0].key_id  # served through its registry key only


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


# -- rerank specifics ------------------------------------------------------------------------------


async def test_rerank_sends_the_query_and_documents_as_given_and_returns_the_ranking(case):
	if case.modality is not RERANK:
		pytest.skip("rerank only")
	request = RerankRequest(model=case.model, query="q", documents=["a", {"text": "b"}], top_n=1, return_documents=False)
	response = await run_modality(
		RERANK, request, db=MagicMock(), redis=MagicMock(), user=SimpleNamespace(id=USER, org_id=ORG, budget_daily_usd=None),
		api_key=SimpleNamespace(id=uuid.uuid4(), team_id=None), request_id=uuid.uuid4(), background_tasks=BackgroundTasks(),
		http_request=SimpleNamespace(headers={}, state=SimpleNamespace(), client=SimpleNamespace(host="x")),
	)
	assert json.loads(response.body)["results"][0]["index"] == 1
	call = case.calls[0]
	assert (call["query"], call["documents"], call["top_n"], call["return_documents"]) == ("q", ["a", "b"], 1, False)


@pytest.mark.parametrize("body", [
	{"query": "q", "documents": []}, {"query": "", "documents": ["a"]}, {"query": "q", "documents": ["a"], "top_n": 0},
	{"query": "q", "documents": [{"nope": "x"}]}, {"query": "q", "documents": ["x" * 50_001]}, {"query": "q", "documents": ["a"] * 1_001},
	{"query": "q", "documents": ["a"], "surprise": 1}, {"query": "x" * 10_001, "documents": ["a"]},
])
def test_rerank_rejects_malformed_or_oversized_requests(body):
	with pytest.raises(ValueError):
		RerankRequest(model="cohere/rerank-english-v3.0", **body)


def test_rerank_accepts_documents_as_text_objects_and_reads_them_as_text():
	request = RerankRequest(model="cohere/x", query="q", documents=["plain", {"text": "wrapped"}])
	assert request.texts() == ["plain", "wrapped"]
