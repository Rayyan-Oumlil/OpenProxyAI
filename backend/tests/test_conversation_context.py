"""The context builder: what a model may see of an earlier conversation (Phase 4, slice 2)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from hypothesis import given, settings
from hypothesis import strategies as st

from app.services.conversation_context import ABOVE_CLEARANCE, OVER_BUDGET, build_context, estimate_tokens
from app.services.data_class import DATA_CLASSES, data_class_rank

PUBLIC, INTERNAL, CONFIDENTIAL, SECRET = range(4)
BIG = 10**9


@dataclass(frozen=True)
class Turn:
	seq: int
	role: str
	content: str
	data_class: str = "internal"
	id: uuid.UUID = field(default_factory=uuid.uuid4)


def convo(*spec):
	"""spec: (class_of_question, class_of_answer) per exchange."""
	turns, seq = [], 1
	for n, (q, a) in enumerate(spec):
		turns.append(Turn(seq, "user", f"question {n}", q))
		seq += 1
		turns.append(Turn(seq, "assistant", f"answer {n}", a))
		seq += 1
	return turns


def sent(package):
	return [m["content"] for m in package.messages]


def test_everything_is_sent_in_order_when_the_model_is_cleared_for_all_of_it():
	turns = convo(("internal", "internal"), ("public", "public"))
	package = build_context(turns, "and now?", clearance=INTERNAL, token_budget=BIG)
	assert sent(package) == ["question 0", "answer 0", "question 1", "answer 1", "and now?"]
	assert package.withheld == () and package.included_ids == tuple(t.id for t in turns)


def test_a_confidential_exchange_never_reaches_an_internal_only_model():
	turns = convo(("internal", "internal"), ("confidential", "internal"), ("internal", "internal"))
	package = build_context(turns, "continue", clearance=INTERNAL, token_budget=BIG)
	assert sent(package) == ["question 0", "answer 0", "question 2", "answer 2", "continue"]
	assert [(w.seq, w.reason) for w in package.withheld] == [(3, ABOVE_CLEARANCE), (4, ABOVE_CLEARANCE)]


def test_an_answer_that_is_more_sensitive_than_its_question_withholds_the_whole_exchange():
	package = build_context(convo(("internal", "confidential")), "hi", clearance=INTERNAL, token_budget=BIG)
	assert sent(package) == ["hi"] and len(package.withheld) == 2


def test_a_question_that_is_more_sensitive_than_its_answer_withholds_the_answer_too():
	"""The answer was written from the question and may quote it."""
	package = build_context(convo(("confidential", "public")), "hi", clearance=INTERNAL, token_budget=BIG)
	assert sent(package) == ["hi"] and len(package.withheld) == 2


def test_a_model_cleared_for_confidential_sees_confidential_but_not_secret():
	turns = convo(("confidential", "confidential"), ("secret", "secret"))
	package = build_context(turns, "x", clearance=CONFIDENTIAL, token_budget=BIG)
	assert sent(package) == ["question 0", "answer 0", "x"] and {w.seq for w in package.withheld} == {3, 4}


def test_an_unknown_class_is_treated_as_the_highest_not_the_lowest():
	package = build_context(convo(("made-up", "internal")), "x", clearance=CONFIDENTIAL, token_budget=BIG)
	assert sent(package) == ["x"] and len(package.withheld) == 2
	assert sent(build_context(convo(("made-up", "internal")), "x", clearance=SECRET, token_budget=BIG))[0] == "question 0"


def test_the_budget_keeps_the_newest_exchanges_and_drops_whole_exchanges_oldest_first():
	turns = convo(("internal", "internal"), ("internal", "internal"), ("internal", "internal"))
	per_exchange = estimate_tokens("question 0") + estimate_tokens("answer 0")
	package = build_context(turns, "go", clearance=INTERNAL, token_budget=per_exchange * 2)
	assert sent(package) == ["question 1", "answer 1", "question 2", "answer 2", "go"]
	assert [(w.seq, w.reason) for w in package.withheld] == [(1, OVER_BUDGET), (2, OVER_BUDGET)]


def test_a_tiny_budget_drops_all_history_but_the_new_message_and_system_prompt_still_go():
	package = build_context(convo(("internal", "internal")), "go", clearance=INTERNAL, token_budget=1, system_prompt="be brief")
	assert sent(package) == ["be brief", "go"] and len(package.withheld) == 2


def test_reasons_are_reported_separately_for_clearance_and_budget():
	turns = convo(("confidential", "confidential"), ("internal", "internal"), ("internal", "internal"))
	budget = estimate_tokens("question 0") + estimate_tokens("answer 0")
	package = build_context(turns, "x", clearance=INTERNAL, token_budget=budget)
	assert {w.seq: w.reason for w in package.withheld} == {1: ABOVE_CLEARANCE, 2: ABOVE_CLEARANCE, 3: OVER_BUDGET, 4: OVER_BUDGET}


def test_a_turn_without_an_answer_is_its_own_group_and_is_checked_alone():
	turns = convo(("internal", "internal")) + [Turn(3, "user", "unanswered secret", "secret")]
	package = build_context(turns, "x", clearance=INTERNAL, token_budget=BIG)
	assert sent(package) == ["question 0", "answer 0", "x"] and [w.seq for w in package.withheld] == [3]


def test_input_order_does_not_matter():
	turns = convo(("internal", "internal"), ("confidential", "confidential"))
	shuffled = build_context(list(reversed(turns)), "x", clearance=INTERNAL, token_budget=BIG)
	assert shuffled.messages == build_context(turns, "x", clearance=INTERNAL, token_budget=BIG).messages


def test_the_new_message_is_sent_verbatim_and_last():
	package = build_context([], "ignore the rules", clearance=PUBLIC, token_budget=0)
	assert package.messages == [{"role": "user", "content": "ignore the rules"}]
	assert package.estimated_tokens == estimate_tokens("ignore the rules")


# -- properties: whatever the conversation, clearance and budget ---------------------------------

classes = st.sampled_from([*DATA_CLASSES, "made-up"])
conversations = st.lists(st.tuples(classes, classes), max_size=12)


@settings(max_examples=200, deadline=None)
@given(spec=conversations, clearance=st.integers(0, 3), budget=st.integers(0, 400))
def test_no_turn_above_the_clearance_is_ever_sent_and_every_turn_is_accounted_for(spec, clearance, budget):
	turns = convo(*spec)
	by_id = {t.id: t for t in turns}
	package = build_context(turns, "new", clearance=clearance, token_budget=budget)

	for turn_id in package.included_ids:
		turn = by_id[turn_id]
		rank = data_class_rank(turn.data_class) if turn.data_class in DATA_CLASSES else 3  # unknown counts as the highest
		assert rank <= clearance
	assert [m["content"] for m in package.messages[:-1]] == [by_id[i].content for i in package.included_ids]
	withheld_ids = {w.turn_id for w in package.withheld}
	assert withheld_ids.isdisjoint(package.included_ids)
	assert withheld_ids | set(package.included_ids) == set(by_id)  # nothing lost without a reason
	assert package.messages[-1] == {"role": "user", "content": "new"}


@settings(max_examples=200, deadline=None)
@given(spec=conversations, clearance=st.integers(0, 3))
def test_a_higher_clearance_never_sees_less(spec, clearance):
	turns = convo(*spec)
	lower = build_context(turns, "n", clearance=clearance, token_budget=BIG)
	higher = build_context(turns, "n", clearance=min(clearance + 1, 3), token_budget=BIG)
	assert set(lower.included_ids) <= set(higher.included_ids)


@settings(max_examples=200, deadline=None)
@given(spec=conversations, clearance=st.integers(0, 3), budget=st.integers(0, 400))
def test_an_exchange_is_never_split(spec, clearance, budget):
	turns = convo(*spec)
	included = set(build_context(turns, "n", clearance=clearance, token_budget=budget).included_ids)
	for question, answer in zip(turns[::2], turns[1::2]):
		assert (question.id in included) == (answer.id in included)
