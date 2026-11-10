"""Adaptive A/B statistics (Phase 3, slice 5): when to shift traffic and when to stop."""

from __future__ import annotations

import random

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.services.ab_testing import MIN_SAMPLES_FLOOR, VariantStats, allocate, decide, probability_best

DRAWS = 2000  # enough for the tests; production uses more


def stats(*pairs):
	return [VariantStats(f"v{i}", n, total) for i, (n, total) in enumerate(pairs)]


def run(stats_list, **overrides):
	args = {"min_samples": 30, "delta": 0.01, "floor": 5, "seed": 1, "draws": DRAWS} | overrides
	return decide(stats_list, **args)


# ── the posterior ────────────────────────────────────────────────────────────


def test_the_chances_of_being_best_sum_to_one_and_favour_the_clearly_better_variant():
	chances = probability_best(stats((100, 70), (100, 50)), seed=7, draws=DRAWS)
	assert sum(chances.values()) == pytest.approx(1.0) and chances["v0"] > 0.95


def test_identical_data_gives_an_even_split():
	chances = probability_best(stats((100, 50), (100, 50)), seed=7, draws=4000)
	assert chances["v0"] == pytest.approx(0.5, abs=0.05)


def test_the_same_seed_gives_the_same_answer_so_a_decision_can_be_reproduced():
	a = probability_best(stats((40, 25), (40, 20)), seed=99, draws=DRAWS)
	assert a == probability_best(stats((40, 25), (40, 20)), seed=99, draws=DRAWS)


def test_with_no_data_every_variant_is_equally_likely():
	chances = probability_best(stats((0, 0), (0, 0), (0, 0)), seed=3, draws=6000)
	assert all(p == pytest.approx(1 / 3, abs=0.05) for p in chances.values())


def test_impossible_statistics_are_refused():
	for n, total in ((10, 11), (10, -1), (-1, 0), (10, float("nan"))):
		with pytest.raises(ValueError):
			VariantStats("v", n, total)


# ── the traffic split ────────────────────────────────────────────────────────


def test_weights_are_whole_numbers_that_sum_to_100_and_respect_the_floor():
	weights = allocate({"a": 0.999, "b": 0.001}, floor=5)
	assert weights == {"a": 95, "b": 5}
	assert sum(allocate({"a": 0.5, "b": 0.3, "c": 0.2}, floor=5).values()) == 100


def test_the_floor_cannot_exceed_the_whole():
	with pytest.raises(ValueError, match="exceeds 100"):
		allocate({"a": 0.5, "b": 0.5}, floor=51)


@settings(max_examples=200, deadline=None)
@given(raw=st.lists(st.floats(min_value=0.0001, max_value=1.0), min_size=2, max_size=6), floor=st.integers(1, 15))
def test_for_any_chances_the_weights_are_whole_numbers_summing_to_100_each_at_least_the_floor(raw, floor):
	total = sum(raw)
	chances = {f"v{i}": value / total for i, value in enumerate(raw)}
	weights = allocate(chances, floor)
	assert sum(weights.values()) == 100 and all(isinstance(w, int) and w >= floor for w in weights.values())
	for a in chances:  # monotone: a strictly likelier variant never gets a smaller share (equal chances may split the odd point)
		for b in chances:
			if chances[a] > chances[b]:
				assert weights[a] >= weights[b]


def test_traffic_follows_the_chance_of_being_best_once_there_is_enough_data():
	decision = run(stats((60, 42), (60, 30)))
	assert decision.ready and decision.weights is not None
	assert decision.weights["v0"] > 50 > decision.weights["v1"] >= 5


# ── not enough data ──────────────────────────────────────────────────────────


def test_weights_are_left_alone_until_every_variant_has_enough_observations():
	decision = run(stats((200, 190), (29, 5)))  # a landslide, but one variant has 29 of the 30 needed
	assert (decision.ready, decision.weights, decision.winner) == (False, None, None)


def test_a_minimum_below_the_hard_floor_is_raised_to_it():
	assert MIN_SAMPLES_FLOOR == 20
	decision = run(stats((19, 19), (19, 0)), min_samples=1)
	assert decision.winner is None and decision.ready is False


def test_it_never_names_a_winner_below_the_minimum_whatever_the_data():
	for n in range(0, 30):
		assert run(stats((n, n), (n, 0)), min_samples=30).winner is None


# ── stopping ─────────────────────────────────────────────────────────────────


def test_a_clear_winner_is_named_once_enough_data_has_arrived():
	decision = run(stats((80, 64), (80, 40)))
	assert decision.ready and decision.winner == "v0"


def test_a_close_race_is_not_called():
	decision = run(stats((80, 41), (80, 40)))
	assert decision.ready and decision.winner is None and decision.weights is not None


def test_a_stricter_delta_demands_more_certainty():
	data = stats((60, 42), (60, 33))
	assert run(data, delta=0.2).winner == "v0"
	assert run(data, delta=0.001).winner is None


@pytest.mark.parametrize("bad", [0, 1, -0.1, 1.5])
def test_delta_must_be_strictly_between_zero_and_one(bad):
	with pytest.raises(ValueError, match="delta"):
		run(stats((50, 25), (50, 25)), delta=bad)


def test_a_test_needs_two_variants():
	with pytest.raises(ValueError, match="two variants"):
		run(stats((50, 25)))


def test_three_variants_name_the_best_of_them():
	decision = run(stats((80, 40), (80, 66), (80, 38)))
	assert decision.winner == "v1" and sum(decision.weights.values()) == 100


# ── the whole procedure, simulated ───────────────────────────────────────────


def simulate(rates, *, seed, delta=0.01, min_samples=30, batch=10, max_n=200):
	"""Feed observations in batches, deciding after each, exactly as the periodic job would. Returns (winner, n, earliest n)."""
	rng = random.Random(seed)
	n, total = [0] * len(rates), [0] * len(rates)
	while min(n) < max_n:
		for i, rate in enumerate(rates):
			n[i] += batch
			total[i] += sum(rng.random() < rate for _ in range(batch))
		decision = decide(
			[VariantStats(f"v{i}", n[i], total[i]) for i in range(len(rates))],
			min_samples=min_samples, delta=delta, floor=5, seed=seed * 1000 + n[0], draws=DRAWS,
		)
		if decision.winner:
			return decision.winner, n[0]
	return None, n[0]


def test_a_real_difference_is_found_and_never_before_the_minimum():
	"""0.75 against 0.45, 30 simulated tests: the better variant wins, and no test stops below 30 each."""
	outcomes = [simulate([0.75, 0.45], seed=s) for s in range(30)]
	assert all(n >= 30 for winner, n in outcomes if winner)
	assert sum(1 for winner, _ in outcomes if winner == "v0") >= 28
	assert sum(1 for winner, _ in outcomes if winner == "v1") == 0


def test_equal_variants_are_rarely_given_a_winner_at_the_default_delta():
	"""Measured, not hoped. Looking every 10 samples inflates false stops: at delta 0.05 about 40% of equal pairs get a
	'winner'; at the default 0.01 it is about 13% (120 trials, up to 400 samples each). The bound here is looser than that
	because this test runs fewer, shorter trials to stay fast; the seeds are fixed so it is deterministic."""
	false_stops = sum(1 for s in range(30) if simulate([0.5, 0.5], seed=500 + s)[0] is not None)
	assert false_stops <= 9  # of 30


def test_the_default_is_stricter_than_the_textbook_five_percent():
	loose = sum(1 for s in range(30) if simulate([0.5, 0.5], seed=500 + s, delta=0.05)[0] is not None)
	strict = sum(1 for s in range(30) if simulate([0.5, 0.5], seed=500 + s, delta=0.01)[0] is not None)
	assert strict < loose
