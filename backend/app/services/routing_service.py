"""Routing core: which models may serve a request of a given sensitivity, and which one is chosen.

Pure logic plus one loader. Nothing here calls a provider. The invariants the request path relies on:

* a model is authorized only if it passes every rule below, in the order of ``EXCLUSION_ORDER``;
* the chosen model is always inside the authorized set, and an unauthorized model is refused, never swapped for another;
* every exclusion carries a reason;
* the optional quality signal (``routing_quality_signal``) only reorders candidates inside the authorized set, it never adds one.

A model's clearance is the lower of its own data class and its provider key's, because a key's class can be lowered after
the model was registered. ``global`` in a model's regions means "any region", as it does for provider keys.
"""

from __future__ import annotations

import math
import time
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.llm_provider_key import LLMProviderKey
from app.models.model_registry import ModelRegistryEntry
from app.models.request_log import RequestLog
from app.models.request_score import RequestScore
from app.services.ab_testing import MIN_SAMPLES_FLOOR, smoothed_rate
from app.services.data_class import data_class_rank
from app.services.refusal_explanations import explain_routing

ROUTING_MODES: Final = ("off", "log_only", "enforce")
QUALITY_SIGNALS: Final = ("off", "feedback")
RISK_LEVELS: Final = ("low", "medium", "high")
CAPABILITY_PREFIX: Final = "cap:"
MAX_EXCLUDED_IN_METADATA: Final = 20

EXCLUSION_ORDER: Final = ("disabled", "no_key", "key_inactive", "class_too_low", "region", "risk", "not_allowed_by_policy")

# Quality signal (opt-in): a model's observed satisfaction rate, from "thumbs" feedback on its requests.
QUALITY_SCORE_NAME: Final = "thumbs"
QUALITY_WINDOW_DAYS: Final = 30
QUALITY_MIN_SAMPLES: Final = MIN_SAMPLES_FLOOR  # fewer ratings than this never decide anything (same floor as adaptive A/B)
QUALITY_MARGIN: Final = 0.05  # a model within 5 points of the best-rated one is tied with it, so cost and risk decide
QUALITY_CACHE_SECONDS: Final = 60
_PRIOR_RATE = 0.5  # what a model with too few ratings counts as: no better and no worse than the prior

_RISK_RANK = {name: index for index, name in enumerate(RISK_LEVELS)}
_COST_RANK = {"low": 0, None: 1, "medium": 1, "high": 2}


@dataclass(frozen=True)
class Candidate:
	"""A registry entry joined with the provider key that serves it."""

	model_id: str
	provider: str
	enabled: bool
	key_id: uuid.UUID | None
	key_active: bool
	key_class: str | None
	entry_class: str
	regions: tuple[str, ...]
	risk: str
	capabilities: tuple[str, ...] = ()
	cost_tier: str | None = None
	# Feedback on this model's recent requests as (ratings, sum of ratings in 0..1). Only loaded when the org turns the
	# quality signal on; None means no signal.
	quality: tuple[int, float] | None = None


@dataclass(frozen=True)
class Authorization:
	authorized: tuple[Candidate, ...]  # ordered by model id
	excluded: dict[str, str]  # model id -> reason (one of EXCLUSION_ORDER)


@dataclass(frozen=True)
class Route:
	candidate: Candidate
	reason: str  # "exact", "capability", or "capability_quality" (feedback picked a different model than cost would)


@dataclass(frozen=True)
class RoutingDecision:
	mode: str
	data_class: str
	requested: str
	model: str | None
	key_id: uuid.UUID | None
	reason: str
	authorized: tuple[str, ...]
	excluded: dict[str, str]

	@property
	def explanation(self) -> str | None:
		"""One plain sentence for the caller when no model was authorized; None when one was."""
		return explain_routing(self.reason, self.data_class, self.requested) if self.model is None else None

	@property
	def blocked(self) -> bool:
		"""Only enforce mode refuses a request; log_only reports the same decision and lets it through."""
		return self.mode == "enforce" and self.model is None

	def as_metadata(self) -> dict:
		"""For the audit row: model names and reasons, never keys, endpoints or text."""
		excluded = dict(sorted(self.excluded.items())[:MAX_EXCLUDED_IN_METADATA])
		metadata = {
			"mode": self.mode,
			"data_class": self.data_class,
			"requested": self.requested,
			"model": self.model,
			"reason": self.reason,
			"authorized": list(self.authorized),
			"excluded": excluded,
		}
		if self.explanation is not None:
			metadata["explanation"] = self.explanation
		return metadata


def may_leave_registry(mode: str, data_class: str, ceiling: str) -> bool:
	"""May request content go to a destination the model registry does not govern?

	Such destinations are things the operator configures: the semantic cache's embedding endpoint and the evaluation
	hook or judge model. Only an enforcing org withholds content, and only above the operator's ceiling.
	"""
	return mode != "enforce" or data_class_rank(data_class) <= data_class_rank(ceiling)


def clearance(candidate: Candidate) -> int:
	"""The highest data class the model may receive, as a rank: the lower of its own and its key's."""
	return min(data_class_rank(candidate.entry_class), data_class_rank(candidate.key_class or "public"))


def _exclusion(candidate: Candidate, *, data_class: str, org_region: str, max_risk: str, allows_model: Callable[[str], bool]) -> str | None:
	if not candidate.enabled:
		return "disabled"
	if candidate.key_id is None:
		return "no_key"
	if not candidate.key_active:
		return "key_inactive"
	if clearance(candidate) < data_class_rank(data_class):
		return "class_too_low"
	if org_region not in candidate.regions and "global" not in candidate.regions:
		return "region"
	if _RISK_RANK[candidate.risk] > _RISK_RANK[max_risk]:
		return "risk"
	if not allows_model(candidate.model_id):
		return "not_allowed_by_policy"
	return None


def authorize(
	candidates: Sequence[Candidate], *, data_class: str, org_region: str, max_risk: str, allows_model: Callable[[str], bool]
) -> Authorization:
	authorized: list[Candidate] = []
	excluded: dict[str, str] = {}
	for candidate in candidates:
		reason = _exclusion(candidate, data_class=data_class, org_region=org_region, max_risk=max_risk, allows_model=allows_model)
		if reason is None:
			authorized.append(candidate)
		else:
			excluded[candidate.model_id] = reason
	return Authorization(tuple(sorted(authorized, key=lambda c: c.model_id)), excluded)


def quality_score(candidate: Candidate) -> float | None:
	"""The candidate's smoothed satisfaction rate, or None when there is too little (or malformed) feedback to use."""
	if candidate.quality is None:
		return None
	n, total = candidate.quality
	if n < QUALITY_MIN_SAMPLES or not math.isfinite(total) or not 0 <= total <= n:
		return None
	return smoothed_rate(n, total)


def _effective_score(candidate: Candidate) -> float:
	score = quality_score(candidate)
	return _PRIOR_RATE if score is None else score


def _by_cost(candidate: Candidate) -> tuple:
	return (_COST_RANK[candidate.cost_tier], _RISK_RANK[candidate.risk], candidate.model_id)


def choose_route(authorization: Authorization, requested: str, *, use_quality: bool = False) -> Route | None:
	"""The model to use for ``requested`` ("provider/name" or "cap:CAPABILITY"), or None. Never a substitute.

	With ``use_quality`` a ``cap:`` request prefers the model with the better feedback (then cost, risk, id). It chooses among
	the authorized models only, so it can change which one is picked, never whether one is.
	"""
	if requested.startswith(CAPABILITY_PREFIX):
		capability = requested[len(CAPABILITY_PREFIX):]
		matching = [c for c in authorization.authorized if capability in c.capabilities]
		if not matching:
			return None
		cheapest = min(matching, key=_by_cost)
		if not use_quality:
			return Route(cheapest, "capability")
		top = max(_effective_score(c) for c in matching)
		contenders = [c for c in matching if _effective_score(c) >= top - QUALITY_MARGIN - 1e-9]  # the best and anything tied with it
		best = min(contenders, key=_by_cost)
		return Route(best, "capability" if best is cheapest else "capability_quality")
	for candidate in authorization.authorized:
		if candidate.model_id == requested:
			return Route(candidate, "exact")
	return None


def decide(
	candidates: Sequence[Candidate],
	*,
	mode: str,
	data_class: str,
	org_region: str,
	max_risk: str,
	allows_model: Callable[[str], bool],
	requested: str,
	quality_signal: str = "off",
) -> RoutingDecision | None:
	"""The routing decision for one request, or None when routing is off for the org."""
	if mode == "off":
		return None
	if mode not in ROUTING_MODES:
		raise ValueError(f"unknown routing mode: {mode!r}")
	authorization = authorize(candidates, data_class=data_class, org_region=org_region, max_risk=max_risk, allows_model=allows_model)
	route = choose_route(authorization, requested, use_quality=quality_signal == "feedback")
	if route is not None:
		model, key_id, reason = route.candidate.model_id, route.candidate.key_id, "authorized" if route.reason == "exact" else route.reason
	else:
		model, key_id = None, None
		if requested.startswith(CAPABILITY_PREFIX):
			reason = "no_model_with_capability"
		elif requested in authorization.excluded:
			reason = f"not_authorized:{authorization.excluded[requested]}"
		else:
			reason = "not_in_registry"
	return RoutingDecision(
		mode=mode, data_class=data_class, requested=requested, model=model, key_id=key_id, reason=reason,
		authorized=tuple(c.model_id for c in authorization.authorized), excluded=authorization.excluded,
	)


_quality_cache: dict[uuid.UUID, tuple[float, dict[str, tuple[int, float]]]] = {}


def clear_quality_cache() -> None:
	_quality_cache.clear()


async def load_quality(db: AsyncSession, org_id: uuid.UUID) -> dict[str, tuple[int, float]]:
	"""Per model: (ratings, sum) of the org's recent thumbs feedback, joined to the requests it rated.

	Cached for a minute per org: routing asks on every request and feedback moves slowly. Values outside 0..1 are left out
	rather than clipped, so a stray score cannot bend a rate. The session must already be scoped to the org (RLS).
	"""
	now = time.monotonic()
	cached = _quality_cache.get(org_id)
	if cached is not None and cached[0] > now:
		return cached[1]
	cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=QUALITY_WINDOW_DAYS)
	rows = await db.execute(
		select(RequestLog.model, func.count(), func.coalesce(func.sum(RequestScore.value), 0))
		.join(RequestScore, (RequestScore.org_id == RequestLog.org_id) & (RequestScore.request_id == RequestLog.request_id))
		.where(
			RequestLog.org_id == org_id, RequestScore.org_id == org_id, RequestScore.score_name == QUALITY_SCORE_NAME,
			RequestScore.value.between(0, 1), RequestScore.created_at >= cutoff,
		)
		.group_by(RequestLog.model)
	)
	loaded = {model: (int(n), float(total)) for model, n, total in rows.all()}
	_quality_cache[org_id] = (now + QUALITY_CACHE_SECONDS, loaded)
	return loaded


async def load_candidates(db: AsyncSession, org_id: uuid.UUID, *, with_quality: bool = False) -> list[Candidate]:
	"""The org's registry joined with the keys that serve it. The session must already be scoped to the org (RLS).

	``with_quality`` attaches recent feedback to each candidate (one extra, cached query); callers ask for it only when
	the org's ``routing_quality_signal`` is on.
	"""
	quality = await load_quality(db, org_id) if with_quality else {}
	rows = await db.execute(
		select(ModelRegistryEntry, LLMProviderKey)
		.outerjoin(LLMProviderKey, ModelRegistryEntry.provider_key_id == LLMProviderKey.id)
		.where(ModelRegistryEntry.org_id == org_id)
	)
	return [
		Candidate(
			quality=quality.get(entry.model_id),
			model_id=entry.model_id,
			provider=entry.provider,
			enabled=entry.enabled,
			key_id=key.id if key is not None else None,
			key_active=bool(key is not None and key.is_active),
			key_class=key.max_data_class if key is not None else None,
			entry_class=entry.max_data_class,
			regions=tuple(entry.regions),
			risk=entry.risk_rating,
			capabilities=tuple(entry.capabilities or ()),
			cost_tier=entry.cost_tier,
		)
		for entry, key in rows.all()
	]
