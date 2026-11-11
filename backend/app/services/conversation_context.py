"""Which earlier turns of a conversation a given model may see (Phase 4, slice 2). Pure: no I/O, so every rule is testable.

History is data too: a confidential turn must not reach a model cleared only for internal data because the user switched
models mid-conversation. The rules, in order of precedence:

1. **An exchange is atomic.** A user turn and the assistant answer that follows it travel together. The answer was written from
   the question and may quote it, so an exchange has the class of its *most sensitive* turn, and is sent whole or not at all.
2. **Clearance.** An exchange above the model's clearance is withheld (``above_clearance``). An unknown class on a stored
   turn counts as the highest class: never guess toward less sensitive.
3. **Budget.** Of what is cleared, the newest exchanges are kept up to the token budget; older ones are withheld
   (``over_budget``). Exchanges are dropped whole, oldest first, never cut in half.
4. **The new message is not history.** It is always sent. Whether the model may see *it* is the caller's check, made before
   this runs (a refusal, not a silent drop).

The result lists what was sent and what was withheld and why, so the user is told and the audit row can show it.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Final, Protocol

from app.services.data_class import DATA_CLASSES, data_class_rank

ABOVE_CLEARANCE: Final = "above_clearance"
OVER_BUDGET: Final = "over_budget"
_HIGHEST: Final = len(DATA_CLASSES) - 1
_PER_MESSAGE_OVERHEAD: Final = 4


class StoredTurn(Protocol):
	id: uuid.UUID
	seq: int
	role: str
	content: str
	data_class: str


@dataclass(frozen=True)
class Withheld:
	turn_id: uuid.UUID
	seq: int
	reason: str


@dataclass(frozen=True)
class ContextPackage:
	messages: list[dict[str, str]]  # what the model receives: system prompt (if any), cleared history, the new message
	included_ids: tuple[uuid.UUID, ...]
	withheld: tuple[Withheld, ...]
	estimated_tokens: int


def estimate_tokens(text: str) -> int:
	"""A rough, deliberately generous count (about 4 characters a token, rounded up) used only to fit a budget."""
	return -(-len(text) // 4) + _PER_MESSAGE_OVERHEAD


def _rank(data_class: str) -> int:
	try:
		return data_class_rank(data_class)
	except ValueError:
		return _HIGHEST


def _exchanges(turns: list[StoredTurn]) -> list[list[StoredTurn]]:
	"""Group by order: a user turn plus the assistant turn right after it. A lone turn is its own group."""
	groups: list[list[StoredTurn]] = []
	for turn in sorted(turns, key=lambda t: t.seq):
		if turn.role == "assistant" and groups and len(groups[-1]) == 1 and groups[-1][0].role == "user":
			groups[-1].append(turn)
		else:
			groups.append([turn])
	return groups


def build_context(
	turns: list[StoredTurn],
	new_message: str,
	*,
	clearance: int,
	token_budget: int,
	system_prompt: str | None = None,
) -> ContextPackage:
	"""``clearance`` is the model's rank (see ``routing_service.clearance``); ``token_budget`` applies to history only."""
	cleared: list[list[StoredTurn]] = []
	withheld: list[Withheld] = []
	for group in _exchanges(turns):
		if max(_rank(t.data_class) for t in group) > clearance:
			withheld.extend(Withheld(t.id, t.seq, ABOVE_CLEARANCE) for t in group)
		else:
			cleared.append(group)

	kept: list[list[StoredTurn]] = []
	used = 0
	for group in reversed(cleared):  # newest first, so the budget keeps the most recent context
		cost = sum(estimate_tokens(t.content) for t in group)
		if used + cost > token_budget:
			withheld.extend(Withheld(t.id, t.seq, OVER_BUDGET) for t in group)
		else:
			kept.append(group)
			used += cost
	kept.reverse()

	messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}] if system_prompt else []
	included = [t for group in kept for t in group]
	messages.extend({"role": t.role, "content": t.content} for t in included)
	messages.append({"role": "user", "content": new_message})
	total = used + estimate_tokens(new_message) + (estimate_tokens(system_prompt) if system_prompt else 0)
	return ContextPackage(
		messages=messages,
		included_ids=tuple(t.id for t in included),
		withheld=tuple(sorted(withheld, key=lambda w: w.seq)),
		estimated_tokens=total,
	)
