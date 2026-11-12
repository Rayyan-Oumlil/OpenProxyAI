"""Adaptive A/B testing (Phase 3, slice 5): shifting traffic toward the better variant and stopping when it is clear.

Each variant's metric is a rate in [0, 1] (a thumbs score is 1 or 0; any score in [0, 1] works). Its posterior is a Beta
distribution; the chance that each variant is the best one is estimated by sampling from those posteriors. Two decisions
follow:

- **Weights.** Once every variant has ``min_samples`` observations, each variant's traffic share follows its chance of being
  best (Thompson-style), but never drops below ``floor`` percent, so a variant that started badly can still recover.
  Before that point the weights are left alone: early data is too noisy to steer by.
- **Stopping.** The test stops, naming a winner, only when every variant has at least ``min_samples`` observations *and* one
  variant's chance of being best is at least ``1 - delta``. It can never stop earlier, however lopsided the early data.

Honest limit: the stopping rule is checked repeatedly as data arrives, and repeated looks make a false stop more likely than
``delta`` alone suggests. ``min_samples`` and a small ``delta`` are what contain that. ``tests/test_ab_testing.py`` measures
the false-stop rate so the defaults are chosen from numbers, not hope.

Pure and deterministic given a seed; no database and no clock.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Final

DRAWS: Final = 10_000
MIN_SAMPLES_FLOOR: Final = 20  # fewer than this never decides anything, whatever the caller asks


@dataclass(frozen=True)
class VariantStats:
	variant_id: str
	n: int  # observations
	total: float  # sum of the metric over them; between 0 and n

	def __post_init__(self) -> None:
		if self.n < 0 or not math.isfinite(self.total) or not 0 <= self.total <= self.n:
			raise ValueError(f"variant {self.variant_id}: total {self.total} is not between 0 and n={self.n}")


@dataclass(frozen=True)
class Decision:
	probability_best: dict[str, float]  # chance each variant is the best; sums to 1
	ready: bool  # every variant has enough observations to act on
	weights: dict[str, int] | None  # new traffic weights (sum 100, each at least the floor), or None to leave them alone
	winner: str | None  # set only when ready and one variant is clearly best


def probability_best(stats: list[VariantStats], seed: int, draws: int = DRAWS) -> dict[str, float]:
	"""Chance each variant has the highest true rate, by sampling the Beta(1 + successes, 1 + failures) posteriors."""
	if not stats:
		return {}
	rng = random.Random(seed)
	wins = [0] * len(stats)
	posteriors = [(1 + s.total, 1 + (s.n - s.total)) for s in stats]
	for _ in range(draws):
		samples = [rng.betavariate(a, b) for a, b in posteriors]
		wins[samples.index(max(samples))] += 1
	return {s.variant_id: wins[i] / draws for i, s in enumerate(stats)}


def smoothed_rate(n: int, total: float) -> float:
	"""The mean of the Beta(1 + total, 1 + n - total) posterior: a rate that a small sample cannot push to 0 or 1.

	No observations gives 0.5 (the prior). Twenty perfect ratings give 21/22, not 1.
	"""
	return (1 + total) / (2 + n)


def allocate(probabilities: dict[str, float], floor: int) -> dict[str, int]:
	"""Integer weights summing to 100: ``floor`` for everyone, the rest in proportion to each chance of being best."""
	count = len(probabilities)
	if count * floor > 100:
		raise ValueError(f"a floor of {floor}% for {count} variants exceeds 100%")
	spare = 100 - count * floor
	exact = {vid: floor + spare * p for vid, p in probabilities.items()}
	weights = {vid: int(value) for vid, value in exact.items()}
	leftover = 100 - sum(weights.values())
	for vid in sorted(exact, key=lambda v: (exact[v] - weights[v], v), reverse=True)[:leftover]:  # largest remainders
		weights[vid] += 1
	return weights


def decide(stats: list[VariantStats], *, min_samples: int, delta: float, floor: int, seed: int, draws: int = DRAWS) -> Decision:
	"""What to do with the traffic split given what has been observed."""
	if len(stats) < 2:
		raise ValueError("an A/B test needs at least two variants")
	if not 0 < delta < 1:
		raise ValueError("delta must be between 0 and 1")
	needed = max(min_samples, MIN_SAMPLES_FLOOR)
	probabilities = probability_best(stats, seed, draws)
	if any(s.n < needed for s in stats):
		return Decision(probabilities, ready=False, weights=None, winner=None)
	leader = max(probabilities, key=lambda v: (probabilities[v], v))
	winner = leader if probabilities[leader] >= 1 - delta else None
	return Decision(probabilities, ready=True, weights=allocate(probabilities, floor), winner=winner)
