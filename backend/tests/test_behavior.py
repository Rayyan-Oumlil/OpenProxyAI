"""Behaviour settings: parsing, the ceiling rule, and the mapping to provider parameters."""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.services import behavior as bh
from app.services.behavior import Behavior, InvalidBehavior

ALL_PARAMS = frozenset({"temperature", "reasoning_effort", "max_tokens", "top_p"})

levels = st.sampled_from(bh.CREATIVITY)
lengths = st.sampled_from(bh.LENGTH)
maybe = lambda s: st.one_of(st.none(), s)  # noqa: E731
behaviors = st.builds(Behavior, creativity=maybe(levels), reasoning_depth=maybe(levels), max_response_length=maybe(lengths), citations=maybe(st.booleans()))
ceilings = st.builds(Behavior, creativity=maybe(levels), reasoning_depth=maybe(levels), max_response_length=maybe(lengths))


# ── parsing ─────────────────────────────────────────────────────────────────

def test_header_parses_pairs_with_either_separator():
	parsed = bh.parse_header("creativity=low; reasoning_depth=HIGH, citations=true,max_response_length=short")
	assert parsed == Behavior(creativity="low", reasoning_depth="high", citations=True, max_response_length="short")


@pytest.mark.parametrize("value", [None, "", "   "])
def test_absent_header_is_empty(value):
	assert bh.parse_header(value) == Behavior()


@pytest.mark.parametrize("value", ["creativity=wild", "tone=low", "creativity", "citations=maybe", "creativity=low;creativity=high", "max_response_length=low"])
def test_bad_header_is_an_error_not_a_guess(value):
	with pytest.raises(InvalidBehavior):
		bh.parse_header(value)


def test_body_mapping_is_strict():
	assert bh.from_mapping({"creativity": "medium", "citations": False}) == Behavior(creativity="medium", citations=False)
	for bad in ({"creativity": 3}, {"citations": "yes"}, {"unknown": 1}, "low", ["low"]):
		with pytest.raises(InvalidBehavior):
			bh.from_mapping(bad)


def test_stored_settings_drop_invalid_entries_instead_of_failing():
	assert bh.from_stored({"creativity": "low", "reasoning_depth": "extreme", "bogus": 1}) == Behavior(creativity="low")
	assert bh.from_stored("garbage") == Behavior()
	assert bh.from_stored(None) == Behavior()


# ── the ceiling rule ────────────────────────────────────────────────────────

def test_request_above_the_ceiling_is_clamped_and_reported():
	resolved = bh.resolve(Behavior(creativity="high", reasoning_depth="low"), Behavior(), Behavior(creativity="medium", reasoning_depth="high"))
	assert resolved.effective.creativity == "medium"
	assert resolved.effective.reasoning_depth == "low"
	assert resolved.clamped == ("creativity",)


def test_default_applies_only_when_the_caller_said_nothing():
	resolved = bh.resolve(Behavior(creativity="low"), Behavior(creativity="high", citations=True), Behavior())
	assert resolved.effective.creativity == "low"
	assert resolved.effective.citations is True


@settings(max_examples=300)
@given(requested=behaviors, defaults=behaviors, ceiling=ceilings)
def test_effective_never_exceeds_the_ceiling(requested, defaults, ceiling):
	effective = bh.resolve(requested, defaults, ceiling).effective
	for key, scale in bh.SCALES.items():
		value, cap = getattr(effective, key), getattr(ceiling, key)
		if value is not None and cap is not None:
			assert scale.index(value) <= scale.index(cap)


@settings(max_examples=300)
@given(requested=behaviors, defaults=behaviors)
def test_without_a_ceiling_the_request_is_taken_as_is(requested, defaults):
	resolved = bh.resolve(requested, defaults, Behavior())
	assert resolved.clamped == ()
	for key in bh.KEYS:
		expected = getattr(requested, key) if getattr(requested, key) is not None else getattr(defaults, key)
		assert getattr(resolved.effective, key) == expected


@settings(max_examples=200)
@given(requested=behaviors, defaults=behaviors, ceiling=ceilings)
def test_the_ceiling_only_lowers_never_raises(requested, defaults, ceiling):
	baseline = bh.resolve(requested, defaults, Behavior()).effective
	effective = bh.resolve(requested, defaults, ceiling).effective
	for key, scale in bh.SCALES.items():
		before, after = getattr(baseline, key), getattr(effective, key)
		if before is None:
			assert after is None
		else:
			assert scale.index(after) <= scale.index(before)


# ── mapping to provider parameters ──────────────────────────────────────────

def _plan(effective=None, ceiling=None, explicit=None, supported=ALL_PARAMS):
	resolved = bh.resolve(effective or Behavior(), Behavior(), ceiling or Behavior())
	return bh.plan_params(resolved=resolved, explicit=explicit or {}, supported=supported)


def test_settings_become_provider_parameters():
	plan = _plan(Behavior(creativity="low", reasoning_depth="high", max_response_length="short"))
	assert plan.params == {"temperature": bh.TEMPERATURE["low"], "reasoning_effort": "high", "max_tokens": bh.MAX_TOKENS["short"]}
	assert plan.ignored == ()


def test_an_unsupported_parameter_is_ignored_and_reported_never_sent():
	plan = _plan(Behavior(creativity="low", reasoning_depth="high", max_response_length="long"), supported=frozenset({"max_tokens"}))
	assert plan.params == {"max_tokens": bh.MAX_TOKENS["long"]}
	assert {i["param"] for i in plan.ignored} == {"temperature", "reasoning_effort"}
	assert all(i["reason"] for i in plan.ignored)


def test_unknown_capabilities_means_nothing_is_sent():
	plan = _plan(Behavior(creativity="low", max_response_length="short"), supported=None)
	assert plan.params == {}
	assert {i["param"] for i in plan.ignored} == {"temperature", "max_tokens"}


def test_no_behaviour_and_no_ceiling_leaves_the_callers_parameters_alone():
	explicit = {"temperature": 1.7, "max_tokens": 99999, "reasoning_effort": "minimal", "top_p": 0.3}
	plan = _plan(explicit=explicit)
	assert plan.params == {} and plan.ignored == () and plan.clamped == ()


def test_an_explicit_parameter_wins_over_a_behaviour_setting():
	plan = _plan(Behavior(creativity="low"), explicit={"temperature": 0.9})
	assert "temperature" not in plan.params  # the caller's 0.9 is already in the call and is left as it is


def test_a_ceiling_clamps_an_explicit_parameter_that_goes_beyond_it():
	plan = _plan(ceiling=Behavior(creativity="low", max_response_length="short"), explicit={"temperature": 1.5, "max_tokens": 5000})
	assert plan.params == {"temperature": bh.TEMPERATURE["low"], "max_tokens": bh.MAX_TOKENS["short"]}
	assert {c["param"] for c in plan.clamped} == {"temperature", "max_tokens"}


def test_an_explicit_parameter_inside_the_ceiling_is_untouched():
	plan = _plan(ceiling=Behavior(creativity="high", max_response_length="long"), explicit={"temperature": 0.1, "max_tokens": 10})
	assert plan.params == {} and plan.clamped == ()


def test_an_unknown_explicit_reasoning_effort_cannot_slip_past_a_ceiling():
	plan = _plan(ceiling=Behavior(reasoning_depth="low"), explicit={"reasoning_effort": "ultra"})
	assert plan.params == {"reasoning_effort": "low"}


@settings(max_examples=300)
@given(
	effective=behaviors, ceiling=ceilings,
	explicit=st.fixed_dictionaries({}, optional={
		"temperature": st.floats(min_value=0, max_value=2), "max_tokens": st.integers(1, 32000),
		"reasoning_effort": st.sampled_from(["minimal", "low", "medium", "high", "ultra"]),
	}),
	supported=st.sets(st.sampled_from(sorted(ALL_PARAMS))).map(frozenset) | st.none(),
)
def test_what_is_sent_never_exceeds_the_ceiling_and_never_uses_an_unsupported_parameter(effective, ceiling, explicit, supported):
	plan = _plan(effective, ceiling, explicit, supported)
	final = {**explicit, **plan.params}
	caps = {"temperature": ceiling.creativity and bh.TEMPERATURE[ceiling.creativity], "max_tokens": ceiling.max_response_length and bh.MAX_TOKENS[ceiling.max_response_length]}
	for name, cap in caps.items():
		if cap is not None and name in final:
			assert final[name] <= cap
	if ceiling.reasoning_depth and "reasoning_effort" in final:
		rank = ("minimal", *bh.REASONING)
		assert final["reasoning_effort"] in rank and rank.index(final["reasoning_effort"]) <= rank.index(ceiling.reasoning_depth)
	derived_only = set(plan.params) - {c["param"] for c in plan.clamped}
	for name in derived_only:
		assert supported is not None and name in supported


# ── citations ───────────────────────────────────────────────────────────────

def test_citation_instruction_goes_after_the_leading_system_messages():
	messages = [{"role": "system", "content": "be brief"}, {"role": "user", "content": "hi"}]
	out = bh.with_citation_instruction(messages)
	assert [m["role"] for m in out] == ["system", "system", "user"]
	assert out[1]["content"] == bh.CITATION_INSTRUCTION
	assert messages == [{"role": "system", "content": "be brief"}, {"role": "user", "content": "hi"}]  # the input is not mutated


def test_citation_instruction_is_added_to_a_conversation_without_a_system_prompt():
	out = bh.with_citation_instruction([{"role": "user", "content": "hi"}])
	assert out[0] == {"role": "system", "content": bh.CITATION_INSTRUCTION}


def test_system_prompt_gets_the_instruction_appended():
	assert bh.citation_system_prompt(None) == bh.CITATION_INSTRUCTION
	assert bh.citation_system_prompt("be brief") == f"be brief\n\n{bh.CITATION_INSTRUCTION}"


def test_settle_is_none_when_nothing_is_asked_set_or_configured():
	assert bh.settle({}, {}, Behavior()) is None
	assert bh.settle(None, {"citations": True}, Behavior()) is None  # a ceiling holds no citations, so this is still "nothing set"
	assert bh.settle({}, {}, Behavior(citations=False)) is not None
