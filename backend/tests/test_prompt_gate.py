"""The promotion gate's rules (Phase 3, slice 6), as pure functions."""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.schemas.policy import PolicyConfigRequest
from app.services.policy_service import PolicyConfig
from app.services.prompt_gate import MAX_UNSCORED_SHARE, RunSummary, fingerprint, shortfalls

POLICY = PolicyConfig(prompt_promotion_gate=True, prompt_gate_min_pass_rate=0.8, prompt_gate_min_items=10)


def run(status="completed", total=20, scored=20, failed=0, pass_rate=0.9):
	return RunSummary(uuid.uuid4(), status, total, scored, failed, pass_rate, pass_rate)


def test_a_completed_run_that_scored_enough_and_passed_satisfies_the_gate():
	assert shortfalls(run(), POLICY) == []


@pytest.mark.parametrize("status", ["cancelled", "budget_exceeded", "failed", "running", "queued"])
def test_a_run_that_did_not_complete_never_counts(status):
	assert any(status in reason for reason in shortfalls(run(status=status), POLICY))


def test_too_few_scored_items_do_not_count_however_well_they_did():
	reasons = shortfalls(run(total=9, scored=9, pass_rate=1.0), POLICY)
	assert reasons and "only 9 items were scored" in reasons[0]
	assert shortfalls(run(total=10, scored=10, pass_rate=1.0), POLICY) == []


def test_the_pass_rate_must_reach_the_bar_exactly_or_more():
	assert shortfalls(run(pass_rate=0.79), POLICY) and shortfalls(run(pass_rate=0.8), POLICY) == []


def test_a_run_with_nothing_scored_has_no_pass_rate_and_does_not_count():
	reasons = shortfalls(run(total=20, scored=0, failed=20, pass_rate=None), POLICY)
	assert any("n/a" in r for r in reasons)


def test_a_run_where_more_than_a_tenth_could_not_be_scored_does_not_count_even_if_the_rest_passed():
	assert MAX_UNSCORED_SHARE == 0.1
	many_errors = run(total=30, scored=20, failed=10, pass_rate=1.0)  # 33% errored, the scored ones all passed
	assert any("could not be scored" in r for r in shortfalls(many_errors, POLICY))
	assert shortfalls(run(total=30, scored=27, failed=3, pass_rate=1.0), POLICY) == []  # exactly a tenth is allowed


def test_every_shortfall_is_reported_not_just_the_first():
	assert len(shortfalls(run(status="cancelled", total=5, scored=2, failed=3, pass_rate=0.1), POLICY)) == 4


def test_the_thresholds_come_from_the_org_policy():
	strict = PolicyConfig(prompt_promotion_gate=True, prompt_gate_min_pass_rate=0.95, prompt_gate_min_items=50)
	assert shortfalls(run(), strict) and shortfalls(run(total=60, scored=60, pass_rate=0.96), strict) == []


# ── the fingerprint ──────────────────────────────────────────────────────────


def template(system="Be brief.", user="{{q}}"):
	return SimpleNamespace(system_message=system, user_template=user)


def test_any_edit_to_a_prompt_changes_its_fingerprint_and_the_same_content_does_not():
	base = fingerprint(template())
	assert fingerprint(template()) == base
	assert fingerprint(template(system="Be very brief.")) != base
	assert fingerprint(template(user="{{q}}!")) != base
	assert fingerprint(template(system=None)) != base


def test_the_fields_cannot_be_shifted_to_collide():
	"""A naive join would make ('a', 'bc') and ('ab', 'c') the same."""
	assert fingerprint(template("a", "bc")) != fingerprint(template("ab", "c"))


# ── the settings ─────────────────────────────────────────────────────────────


def test_the_gate_is_off_by_default_with_sensible_thresholds_and_survives_a_save():
	config = PolicyConfig()
	assert (config.prompt_promotion_gate, config.prompt_gate_min_pass_rate, config.prompt_gate_min_items) == (False, 0.8, 10)
	again = PolicyConfig.from_dict(PolicyConfig(prompt_promotion_gate=True, prompt_gate_min_pass_rate=0.9, prompt_gate_min_items=25).to_dict())
	assert (again.prompt_promotion_gate, again.prompt_gate_min_pass_rate, again.prompt_gate_min_items) == (True, 0.9, 25)


@pytest.mark.parametrize("stored", [None, "x", -1, 0, 1.5, float("nan"), True])
def test_a_corrupt_stored_threshold_falls_back_to_the_default_never_to_an_easier_gate(stored):
	assert PolicyConfig.from_dict({"prompt_gate_min_pass_rate": stored}).prompt_gate_min_pass_rate == 0.8


@pytest.mark.parametrize("stored", [None, "x", 0, -5, 1.5, True, 1_000_000])
def test_a_corrupt_stored_item_minimum_falls_back_to_the_default(stored):
	assert PolicyConfig.from_dict({"prompt_gate_min_items": stored}).prompt_gate_min_items == 10


@pytest.mark.parametrize("stored", [None, "true", 1, "yes"])
def test_only_a_real_true_turns_the_gate_on(stored):
	assert PolicyConfig.from_dict({"prompt_promotion_gate": stored}).prompt_promotion_gate is False


def test_the_gate_cannot_be_switched_off_by_sending_null():
	"""Null would otherwise be stored as 'not true', silently disabling a control."""
	for field in ("prompt_promotion_gate", "prompt_gate_min_pass_rate", "prompt_gate_min_items"):
		with pytest.raises(ValidationError):
			PolicyConfigRequest.model_validate({field: None})


@pytest.mark.parametrize("body", [{"prompt_gate_min_pass_rate": 0}, {"prompt_gate_min_pass_rate": 1.01}, {"prompt_gate_min_items": 0}])
def test_out_of_range_thresholds_are_refused(body):
	with pytest.raises(ValidationError):
		PolicyConfigRequest.model_validate(body)
