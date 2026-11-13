"""Quality signal for ``cap:NAME`` routing: feedback may reorder the authorized set, never widen it.

The signal is opt-in (``routing_quality_signal``). The guarantees these tests pin:

* off (the default) is exactly today's rule: cheapest, then lowest risk, then model id;
* on, the choice is always inside the authorized set, however good an unauthorized model's feedback is;
* too little feedback never decides anything, and small differences are ties that cost and risk settle.
"""

from __future__ import annotations

import dataclasses
import uuid

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.services.ab_testing import MIN_SAMPLES_FLOOR, smoothed_rate
from app.services.data_class import DATA_CLASSES
from app.services.routing_service import (
	_COST_RANK,
	_RISK_RANK,
	CAPABILITY_PREFIX,
	Candidate,
	authorize,
	choose_route,
	decide,
	quality_score,
)
from tests.test_routing_core import allow_all, candidate, candidates_st, run

CAP = "CODE_GENERATION"
GOOD, BAD = (100, 90.0), (100, 30.0)  # a 90% and a 30% satisfaction rate over 100 ratings


def capable(model_id, quality=None, **overrides):
	return candidate(model_id, capabilities=(CAP,), quality=quality, **overrides)


def pick(candidates, *, use_quality, requested=f"{CAPABILITY_PREFIX}{CAP}", **kwargs):
	route = choose_route(run(candidates, **kwargs), requested, use_quality=use_quality)
	return None if route is None else route.candidate.model_id


def reference_choice(authorized, capability):
	"""The rule as it was before the quality signal existed."""
	matching = [c for c in authorized if capability in c.capabilities]
	if not matching:
		return None
	return min(matching, key=lambda c: (_COST_RANK[c.cost_tier], _RISK_RANK[c.risk], c.model_id)).model_id


# ── the score ────────────────────────────────────────────────────────────────

def test_smoothed_rate_is_the_beta_posterior_mean():
	assert smoothed_rate(0, 0) == 0.5  # no data: the prior, not zero and not one
	assert smoothed_rate(20, 20) == pytest.approx(21 / 22)  # a perfect small sample is pulled toward the middle
	assert smoothed_rate(1000, 900) == pytest.approx(901 / 1002)


def test_score_needs_enough_ratings():
	assert quality_score(capable("a/x", (MIN_SAMPLES_FLOOR - 1, float(MIN_SAMPLES_FLOOR - 1)))) is None
	assert quality_score(capable("a/x", (MIN_SAMPLES_FLOOR, float(MIN_SAMPLES_FLOOR)))) == pytest.approx(smoothed_rate(20, 20))
	assert quality_score(capable("a/x", None)) is None


@pytest.mark.parametrize("bad", [(10, 11.0), (10, -1.0), (-1, 0.0), (50, float("nan")), (50, float("inf"))])
def test_a_corrupt_count_is_no_signal_not_a_crash(bad):
	assert quality_score(capable("a/x", bad)) is None


# ── choosing ─────────────────────────────────────────────────────────────────

def test_off_ignores_feedback_entirely():
	pool = [capable("a/cheap", BAD, cost_tier="low"), capable("a/pricey", GOOD, cost_tier="high")]
	assert pick(pool, use_quality=False) == "a/cheap"


def test_on_prefers_the_better_rated_model_over_the_cheaper_one():
	pool = [capable("a/cheap", BAD, cost_tier="low"), capable("a/pricey", GOOD, cost_tier="high")]
	assert pick(pool, use_quality=True) == "a/pricey"


def test_too_few_ratings_do_not_beat_cost():
	few = (MIN_SAMPLES_FLOOR - 1, float(MIN_SAMPLES_FLOOR - 1))  # perfect, but only 19 ratings
	pool = [capable("a/cheap", None, cost_tier="low"), capable("a/pricey", few, cost_tier="high")]
	assert pick(pool, use_quality=True) == "a/cheap"


def test_a_model_with_bad_feedback_loses_to_one_nobody_has_rated():
	pool = [capable("a/cheap", BAD, cost_tier="low"), capable("a/unrated", None, cost_tier="high")]
	assert pick(pool, use_quality=True) == "a/unrated"  # unrated counts as the prior (50%), better than a known 30%


def test_small_differences_are_ties_and_cost_decides():
	close_a, close_b = (1000, 810.0), (1000, 800.0)  # 81% vs 80%: inside the 5-point margin
	pool = [capable("a/cheap", close_b, cost_tier="low"), capable("a/pricey", close_a, cost_tier="high")]
	assert pick(pool, use_quality=True) == "a/cheap"


def test_the_reason_says_when_feedback_decided():
	pool = [capable("a/cheap", BAD, cost_tier="low"), capable("a/pricey", GOOD, cost_tier="high")]
	args = dict(mode="enforce", data_class="internal", org_region="us", max_risk="high", allows_model=allow_all, requested=f"{CAPABILITY_PREFIX}{CAP}")
	assert decide(pool, quality_signal="feedback", **args).reason == "capability_quality"
	assert decide(pool, quality_signal="off", **args).reason == "capability"
	agreeing = [capable("a/cheap", GOOD, cost_tier="low"), capable("a/pricey", BAD, cost_tier="high")]
	assert decide(agreeing, quality_signal="feedback", **args).reason == "capability"  # feedback agreed with the default


def test_an_exact_model_request_is_not_affected():
	pool = [capable("a/cheap", BAD, cost_tier="low"), capable("a/pricey", GOOD, cost_tier="high")]
	assert pick(pool, use_quality=True, requested="a/cheap") == "a/cheap"


def test_an_unauthorized_model_with_perfect_feedback_is_never_chosen():
	pool = [
		capable("a/cleared", BAD, cost_tier="low", entry_class="public", key_class="public"),
		capable("a/star", (10_000, 10_000.0), cost_tier="high", entry_class="secret", key_class="secret"),
	]
	assert pick(pool, use_quality=True, data_class="secret") == "a/star"  # only the secret-cleared one may serve secret
	assert pick(pool, use_quality=True, data_class="public") == "a/star"  # both authorized: feedback prefers it
	star_off = dataclasses.replace(pool[1], enabled=False)
	assert pick([pool[0], star_off], use_quality=True, data_class="public") == "a/cleared"  # disabled: out, whatever its score


# ── properties ───────────────────────────────────────────────────────────────

quality_st = st.one_of(
	st.none(),
	st.integers(0, 500).flatmap(lambda n: st.tuples(st.just(n), st.integers(0, n).map(float))),
)
rated_candidates = candidates_st.flatmap(lambda c: quality_st.map(lambda q: dataclasses.replace(c, quality=q)))
rated_pools = st.lists(rated_candidates, max_size=12, unique_by=lambda c: c.model_id)
SETTINGS = settings(max_examples=300, deadline=None)


@SETTINGS
@given(pool=rated_pools, data_class=st.sampled_from(DATA_CLASSES), region=st.sampled_from(("us", "eu", "ap", "global")), cap=st.sampled_from(("CODE_GENERATION", "VISION", "SUMMARIZATION")))
def test_property_the_signal_only_reorders_inside_the_authorized_set(pool, data_class, region, cap):
	authorization = run(pool, data_class=data_class, region=region)
	with_signal = choose_route(authorization, f"{CAPABILITY_PREFIX}{cap}", use_quality=True)
	without = choose_route(authorization, f"{CAPABILITY_PREFIX}{cap}", use_quality=False)
	authorized_ids = {c.model_id for c in authorization.authorized}
	capable_ids = {c.model_id for c in authorization.authorized if cap in c.capabilities}
	# Same availability: the signal neither finds a route where there was none nor loses one.
	assert (with_signal is None) == (without is None)
	if with_signal is not None:
		assert with_signal.candidate.model_id in authorized_ids
		assert with_signal.candidate.model_id in capable_ids
		assert with_signal.candidate.model_id not in authorization.excluded
		assert with_signal.reason in {"capability", "capability_quality"}


@SETTINGS
@given(pool=rated_pools, data_class=st.sampled_from(DATA_CLASSES), cap=st.sampled_from(("CODE_GENERATION", "VISION", "SUMMARIZATION")))
def test_property_off_is_exactly_the_old_rule(pool, data_class, cap):
	authorization = run(pool, data_class=data_class)
	route = choose_route(authorization, f"{CAPABILITY_PREFIX}{cap}", use_quality=False)
	expected = reference_choice(authorization.authorized, cap)
	assert (None if route is None else route.candidate.model_id) == expected
	assert route is None or route.reason == "capability"


@SETTINGS
@given(pool=rated_pools, data_class=st.sampled_from(DATA_CLASSES), cap=st.sampled_from(("CODE_GENERATION", "VISION", "SUMMARIZATION")))
def test_property_the_authorized_set_is_the_same_with_the_signal_on(pool, data_class, cap):
	args = dict(mode="enforce", data_class=data_class, org_region="us", max_risk="high", allows_model=allow_all, requested=f"{CAPABILITY_PREFIX}{cap}")
	on = decide(pool, quality_signal="feedback", **args)
	off = decide(pool, quality_signal="off", **args)
	assert on.authorized == off.authorized and on.excluded == off.excluded
	assert (on.model is None) == (off.model is None)


@SETTINGS
@given(pool=rated_pools, cap=st.sampled_from(("CODE_GENERATION", "VISION", "SUMMARIZATION")))
def test_property_an_excluded_model_is_never_rescued_by_feedback(pool, cap):
	boosted = [dataclasses.replace(c, quality=(10_000, 10_000.0)) if not c.enabled else c for c in pool]  # disabled models get perfect feedback
	authorization = authorize(boosted, data_class="public", org_region="us", max_risk="high", allows_model=allow_all)
	route = choose_route(authorization, f"{CAPABILITY_PREFIX}{cap}", use_quality=True)
	disabled = {c.model_id for c in boosted if not c.enabled}
	assert route is None or route.candidate.model_id not in disabled


@SETTINGS
@given(pool=rated_pools, data_class=st.sampled_from(DATA_CLASSES), region=st.sampled_from(("us", "eu", "ap", "global")), max_risk=st.sampled_from(("low", "medium", "high")))
def test_property_feedback_never_changes_who_is_authorized(pool, data_class, region, max_risk):
	"""Authorization does not look at feedback at all: stripping it, or making it perfect, gives the same set and reasons."""
	args = dict(data_class=data_class, region=region, max_risk=max_risk)
	baseline = run(pool, **args)
	for quality in (None, (10_000, 10_000.0), (10_000, 0.0)):
		changed = run([dataclasses.replace(c, quality=quality) for c in pool], **args)
		assert changed.excluded == baseline.excluded
		assert [c.model_id for c in changed.authorized] == [c.model_id for c in baseline.authorized]


def test_candidate_default_has_no_quality():
	assert Candidate(
		model_id="a/x", provider="a", enabled=True, key_id=uuid.uuid4(), key_active=True, key_class="public", entry_class="public",
		regions=("us",), risk="low",
	).quality is None


# ── the policy setting ───────────────────────────────────────────────────────

def test_the_setting_defaults_off_and_round_trips():
	from app.services.policy_service import PolicyConfig

	assert PolicyConfig().routing_quality_signal == "off"
	assert PolicyConfig.from_dict(PolicyConfig(routing_quality_signal="feedback").to_dict()).routing_quality_signal == "feedback"
	assert PolicyConfig.from_dict({}).routing_quality_signal == "off"  # stored policies from before the setting existed
	assert PolicyConfig.from_dict({"routing_quality_signal": "always"}).routing_quality_signal == "off"  # hand-edited junk never turns it on


def test_the_api_accepts_only_known_values_and_never_null():
	from pydantic import ValidationError

	from app.schemas.policy import PolicyConfigRequest

	assert PolicyConfigRequest(routing_quality_signal="feedback").routing_quality_signal == "feedback"
	for bad in ("always", None, True):
		with pytest.raises(ValidationError):
			PolicyConfigRequest(routing_quality_signal=bad)
	assert "routing_quality_signal" not in PolicyConfigRequest().model_dump(exclude_unset=True)  # omitted means unchanged


def test_route_decision_follows_the_org_setting():
	from app.services.llm_service import route_decision
	from app.services.policy_service import PolicyConfig

	pool = [capable("a/cheap", BAD, cost_tier="low"), capable("a/pricey", GOOD, cost_tier="high")]
	requested = f"{CAPABILITY_PREFIX}{CAP}"
	off = route_decision(pool, "us", PolicyConfig(routing_mode="enforce"), "internal", requested)
	on = route_decision(pool, "us", PolicyConfig(routing_mode="enforce", routing_quality_signal="feedback"), "internal", requested)
	assert (off.model, off.reason) == ("a/cheap", "capability")
	assert (on.model, on.reason) == ("a/pricey", "capability_quality")
	assert on.authorized == off.authorized
	assert on.as_metadata()["reason"] == "capability_quality"
