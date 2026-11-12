"""The admission steps chat and every other endpoint share: policy -> classify -> route -> refusals -> rate limit, in that order."""

from __future__ import annotations

import uuid
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.services import rate_limiter, request_gate
from app.services.policy_service import PolicyConfig, PolicyDecision, policy_store
from app.services.routing_service import RoutingDecision
from app.services.stage_timing import StageTimer

ORG, USER = uuid.uuid4(), uuid.uuid4()


class Steps:
	def __init__(self) -> None:
		self.order, self.config = [], PolicyConfig()
		self.allowed, self.blocked_route, self.limited = True, False, False


@pytest.fixture
def steps(monkeypatch):
	s = Steps()

	async def load(org_id, db, redis):
		s.order.append("load")
		return s.config

	async def check_limits(**kwargs):
		s.order.append("rate_limit")
		s.limit_kwargs = kwargs
		return (False, {"X-RL": "1"}, "rpm", "slow", 3) if s.limited else (True, {"X-RL": "1"}, None, None, None)

	monkeypatch.setattr(policy_store, "load", load)
	monkeypatch.setattr(rate_limiter.rate_limiter_service, "check_limits", check_limits)
	return s


def admit_with(s, **over):
	async def evaluate(config):
		s.order.append("evaluate")
		return PolicyDecision(allowed=s.allowed, reason_code=None if s.allowed else "keyword_block", action="allow" if s.allowed else "block")

	async def classify(config):
		s.order.append("classify")
		return SimpleNamespace(data_class="internal")

	async def route(config, classification):
		s.order.append("route")
		return RoutingDecision(mode="enforce", data_class="internal", requested="openai/gpt-4o", model=None if s.blocked_route else "openai/gpt-4o", key_id=None, reason="r", authorized=(), excluded={})

	async def between(config, classification, routing):
		s.order.append("between")
		return Decimal("9")

	args = dict(
		db=None, redis=None, user=SimpleNamespace(id=USER, org_id=ORG, budget_daily_usd=None), model_of=lambda: "openai/gpt-4o", timer=StageTimer(0.0),
		evaluate=evaluate, classify=classify, route=route, between=between, estimate_tokens=7, team_id=None,
	)
	return request_gate.admit(**{**args, **over})


async def test_the_steps_run_in_order_and_the_result_carries_what_each_decided(steps):
	steps.config = PolicyConfig(routing_mode="enforce")
	gate = await admit_with(steps)
	assert steps.order == ["load", "evaluate", "classify", "route", "between", "rate_limit"] and gate.refusal is None
	assert gate.classification.data_class == "internal" and gate.rl_headers["X-OpenProxyAI-Data-Class"] == "internal" and gate.rl_headers["X-RL"] == "1"
	assert steps.limit_kwargs["request_tokens_estimate"] == 7 and steps.limit_kwargs["team_budget_monthly_usd"] == Decimal("9")


async def test_routing_is_skipped_when_it_is_off(steps):
	await admit_with(steps)
	assert "route" not in steps.order


async def test_a_policy_block_is_a_446_refusal_and_the_limits_are_not_spent(steps):
	steps.allowed = False
	gate = await admit_with(steps)
	assert gate.refusal.status_code == 446 and gate.error == "policy_blocked:keyword_block" and "rate_limit" not in steps.order


async def test_a_routing_block_is_refused_before_the_limits(steps):
	steps.config, steps.blocked_route = PolicyConfig(routing_mode="enforce"), True
	gate = await admit_with(steps)
	assert gate.refusal.status_code == 446 and gate.error == "policy_blocked:no_authorized_model" and "rate_limit" not in steps.order


async def test_a_policy_block_wins_over_a_routing_block(steps):
	steps.config, steps.allowed, steps.blocked_route = PolicyConfig(routing_mode="enforce"), False, True
	assert (await admit_with(steps)).error == "policy_blocked:keyword_block"


async def test_a_rate_limit_is_a_429_with_the_headers(steps):
	steps.limited = True
	gate = await admit_with(steps)
	assert gate.refusal.status_code == 429 and gate.error == "rate_limited:rpm" and gate.refusal.headers["x-rl"] == "1" and gate.refusal.headers["x-openproxyai-gateway-error"] == "true"


async def test_a_failing_step_is_not_swallowed(steps):
	async def classify(config):
		raise HTTPException(status_code=400, detail="bad class")

	with pytest.raises(HTTPException):
		await admit_with(steps, classify=classify)
	assert "rate_limit" not in steps.order


async def test_the_between_step_runs_before_a_refusal_so_a_bad_team_beats_a_policy_block(steps):
	steps.allowed = False

	async def between(config, classification, routing):
		raise HTTPException(status_code=404, detail="Team not found")

	with pytest.raises(HTTPException) as caught:
		await admit_with(steps, between=between)
	assert caught.value.status_code == 404


async def test_an_empty_request_is_still_counted_by_the_token_limit(steps):
	await admit_with(steps, estimate_tokens=0)
	assert steps.limit_kwargs["request_tokens_estimate"] == 1


async def test_the_limits_see_the_model_routing_settled_on_not_the_one_asked_for(steps):
	"""A cap:NAME request becomes a concrete model during routing; the per-model limits must apply to that one."""
	steps.config = PolicyConfig(routing_mode="enforce")
	chosen = {"model": "cap:summarize"}

	async def route(config, classification):
		chosen["model"] = "openai/gpt-4o"
		return RoutingDecision(mode="enforce", data_class="internal", requested="cap:summarize", model="openai/gpt-4o", key_id=None, reason="r", authorized=(), excluded={})

	await admit_with(steps, route=route, model_of=lambda: chosen["model"])
	assert steps.limit_kwargs["model"] == "openai/gpt-4o"
