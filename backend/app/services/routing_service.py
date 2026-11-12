"""Routing core: which models may serve a request of a given sensitivity, and which one is chosen.

Pure logic plus one loader. Nothing here calls a provider. The invariants the request path relies on:

* a model is authorized only if it passes every rule below, in the order of ``EXCLUSION_ORDER``;
* the chosen model is always inside the authorized set, and an unauthorized model is refused, never swapped for another;
* every exclusion carries a reason.

A model's clearance is the lower of its own data class and its provider key's, because a key's class can be lowered after
the model was registered. ``global`` in a model's regions means "any region", as it does for provider keys.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.llm_provider_key import LLMProviderKey
from app.models.model_registry import ModelRegistryEntry
from app.services.data_class import data_class_rank
from app.services.refusal_explanations import explain_routing

ROUTING_MODES: Final = ("off", "log_only", "enforce")
RISK_LEVELS: Final = ("low", "medium", "high")
CAPABILITY_PREFIX: Final = "cap:"
MAX_EXCLUDED_IN_METADATA: Final = 20

EXCLUSION_ORDER: Final = ("disabled", "no_key", "key_inactive", "class_too_low", "region", "risk", "not_allowed_by_policy")

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


@dataclass(frozen=True)
class Authorization:
	authorized: tuple[Candidate, ...]  # ordered by model id
	excluded: dict[str, str]  # model id -> reason (one of EXCLUSION_ORDER)


@dataclass(frozen=True)
class Route:
	candidate: Candidate
	reason: str  # "exact" or "capability"


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


def choose_route(authorization: Authorization, requested: str) -> Route | None:
	"""The model to use for ``requested`` ("provider/name" or "cap:CAPABILITY"), or None. Never a substitute."""
	if requested.startswith(CAPABILITY_PREFIX):
		capability = requested[len(CAPABILITY_PREFIX):]
		matching = [c for c in authorization.authorized if capability in c.capabilities]
		if not matching:
			return None
		best = min(matching, key=lambda c: (_COST_RANK[c.cost_tier], _RISK_RANK[c.risk], c.model_id))
		return Route(best, "capability")
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
) -> RoutingDecision | None:
	"""The routing decision for one request, or None when routing is off for the org."""
	if mode == "off":
		return None
	if mode not in ROUTING_MODES:
		raise ValueError(f"unknown routing mode: {mode!r}")
	authorization = authorize(candidates, data_class=data_class, org_region=org_region, max_risk=max_risk, allows_model=allows_model)
	route = choose_route(authorization, requested)
	if route is not None:
		model, key_id, reason = route.candidate.model_id, route.candidate.key_id, "authorized" if route.reason == "exact" else "capability"
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


async def load_candidates(db: AsyncSession, org_id: uuid.UUID) -> list[Candidate]:
	"""The org's registry joined with the keys that serve it. The session must already be scoped to the org (RLS)."""
	rows = await db.execute(
		select(ModelRegistryEntry, LLMProviderKey)
		.outerjoin(LLMProviderKey, ModelRegistryEntry.provider_key_id == LLMProviderKey.id)
		.where(ModelRegistryEntry.org_id == org_id)
	)
	return [
		Candidate(
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
