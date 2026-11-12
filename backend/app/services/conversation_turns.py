"""One conversation turn (Phase 4, slice 3): decide what the chosen model may see, call it, store what was said.

The order matters, and each step is a guard:

1. Classify the new message (the org default, raised by detected PII or by the caller's assertion; it can only raise).
2. Find the chosen model's clearance. Only an enforcing org withholds history; ``log_only`` sends everything and records what
   *would* have been withheld, ``off`` is today's behavior.
3. Build the context for that clearance (``conversation_context``), then **classify the package** as the highest of the new
   message and the history actually included. That class goes to the same routing check every request gets, so even a bug in
   the builder cannot send a model data above its clearance: routing refuses it (446) before anything leaves.
3b. Check the rate limit on the package's real size (history, system prompt and message), not just the new message.
4. Call through ``model_runner`` (policy, routing, key choice, metering, audit log; ``source = conversation``).
5. Only on success store the exchange, redacted and capped. The answer takes the class of everything the model saw: it may
   quote any of it, so a later, less-cleared model must not see it either.
6. Record the context package, append-only, whatever the outcome.

The model is the one the caller names. There is no experiment variant swap and no silent fallback to another model: a
conversation's history was filtered for *this* model, so quietly answering with a different one would invalidate the filter.
A failed call returns the error and stores nothing.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation, ConversationContextPackage, ConversationTurn
from app.services import payload_capture
from app.services.classification_service import Classification, classify_text
from app.services.conversation_context import ContextPackage, Withheld, build_context
from app.services.data_class import DATA_CLASSES, data_class_rank
from app.services.llm_service import llm_service
from app.database import org_scoped_session
from app.services.model_runner import CallPlan, RunOutcome, execute_plan, plan_call, stream_plan
from app.services.policy_service import PolicyConfig
from app.services.routing_service import clearance

DEFAULT_CONTEXT_TOKENS = 24_000
_UNCAPPED = len(DATA_CLASSES) - 1  # clearance when nothing is being enforced


@dataclass(frozen=True)
class TurnResult:
	user_turn: ConversationTurn | None = None
	assistant_turn: ConversationTurn | None = None
	package: ConversationContextPackage | None = None
	outcome: RunOutcome | None = None


def _highest(*classes: str) -> str:
	return max(classes, key=data_class_rank)


def _sha256(messages: list[dict[str, str]]) -> str:
	return hashlib.sha256(json.dumps(messages, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _withheld_json(withheld: tuple[Withheld, ...]) -> list[dict]:
	return [{"turn_id": str(w.turn_id), "seq": w.seq, "reason": w.reason} for w in withheld]


async def _model_clearance(db: AsyncSession, org_id: uuid.UUID, model: str, policy: PolicyConfig) -> tuple[int, tuple | None, int]:
	"""The rank applied now, the registry inputs (loaded once, reused by the routing check), and the rank enforcement would apply.

	They differ only under ``log_only``: nothing is withheld yet, but the preview says what would be."""
	if policy.routing_mode == "off":
		return _UNCAPPED, None, _UNCAPPED
	inputs = await llm_service.routing_inputs(db, org_id)
	entry = next((c for c in inputs[0] if c.model_id == model), None)
	enforced = clearance(entry) if entry is not None else -1  # not in the registry: nothing is cleared; routing refuses it
	return (enforced if policy.routing_mode == "enforce" else _UNCAPPED), inputs, enforced


async def prepare_turn(
	db: AsyncSession,
	*,
	conversation: Conversation,
	model: str,
	content: str,
	asserted_class: str | None,
	policy: PolicyConfig,
	system_prompt: str | None,
	token_budget: int,
) -> tuple[Classification, ContextPackage, str, tuple | None, tuple]:
	"""Everything decided before the call: the new message's class, the context, and the class of the package as a whole."""
	new_class = await classify_text(content, policy, asserted_class)
	allowed, inputs, enforced = await _model_clearance(db, conversation.org_id, model, policy)
	turns = list((await db.scalars(select(ConversationTurn).where(ConversationTurn.conversation_id == conversation.id))).all())
	package = build_context(turns, content, clearance=allowed, token_budget=token_budget, system_prompt=system_prompt)
	by_id = {t.id: t for t in turns}
	preview = ()
	if policy.routing_mode == "log_only":
		preview = build_context(turns, content, clearance=enforced, token_budget=token_budget, system_prompt=system_prompt).withheld
	# Everything the model receives counts: the system prompt is text the model reads, so it is classified like the message.
	system_class = (await classify_text(system_prompt, policy, None)).data_class if system_prompt else new_class.data_class
	package_class = _highest(new_class.data_class, system_class, *(by_id[i].data_class for i in package.included_ids if by_id[i].data_class in DATA_CLASSES))
	if any(by_id[i].data_class not in DATA_CLASSES for i in package.included_ids):
		package_class = DATA_CLASSES[-1]  # an unreadable class on a stored turn: assume the worst
	return new_class, package, package_class, inputs, preview


@dataclass(frozen=True)
class PreparedTurn:
	"""Everything decided before the provider is called: the plan, and what the record and the stored turns will say."""

	conversation_id: uuid.UUID
	org_id: uuid.UUID
	user_id: uuid.UUID
	model: str
	content: str
	new_class: Classification
	package: ContextPackage
	package_class: str
	preview: tuple
	policy: PolicyConfig
	plan: CallPlan


async def begin_turn(
	db: AsyncSession,
	redis,
	*,
	conversation: Conversation,
	user_id: uuid.UUID,
	model: str,
	content: str,
	asserted_class: str | None,
	policy: PolicyConfig,
	system_prompt: str | None = None,
	temperature: float | None = None,
	max_tokens: int | None = None,
	token_budget: int = DEFAULT_CONTEXT_TOKENS,
	before_call: Callable[[int], Awaitable[None]] | None = None,
) -> PreparedTurn | TurnResult:
	"""Classify, build the context, run it through policy and routing and choose the key. A ``TurnResult`` means the turn ended here
	(refused, or no key): nothing was sent and nothing is stored. Otherwise the caller makes the call and then finalizes."""
	new_class, package, package_class, inputs, preview = await prepare_turn(
		db, conversation=conversation, model=model, content=content, asserted_class=asserted_class,
		policy=policy, system_prompt=system_prompt, token_budget=token_budget,
	)
	if before_call is not None:
		await before_call(package.estimated_tokens)  # e.g. the rate limit, on what is really about to be sent
	package_classification = Classification(package_class, new_class.source, new_class.entities)  # type: ignore[arg-type]
	planned = await plan_call(
		db=db, redis=redis, org_id=conversation.org_id, user_id=user_id, model=model, messages=package.messages, policy_config=policy,
		source="conversation", extra_metadata={"conversation_id": str(conversation.id), "withheld_turns": len(package.withheld)},
		temperature=temperature, max_tokens=max_tokens, classification=package_classification, routing_inputs=inputs,
	)
	if isinstance(planned, RunOutcome):
		return TurnResult(outcome=planned)
	assert isinstance(planned, CallPlan)
	return PreparedTurn(conversation.id, conversation.org_id, user_id, model, content, new_class, package, package_class, preview, policy, planned)


async def finalize_turn(db: AsyncSession, conversation: Conversation, prepared: PreparedTurn, outcome: RunOutcome) -> TurnResult:
	"""Record what was sent and, if the call succeeded, store the exchange. ``conversation`` must belong to ``db``."""
	package = prepared.package
	record = ConversationContextPackage(
		org_id=prepared.org_id, conversation_id=prepared.conversation_id, model=prepared.model, data_class=prepared.package_class,
		routing_mode=prepared.policy.routing_mode, included_turn_ids=[str(i) for i in package.included_ids], withheld=_withheld_json(package.withheld),
		would_withhold=_withheld_json(prepared.preview), estimated_tokens=package.estimated_tokens, payload_sha256=_sha256(package.messages),
		outcome="error" if outcome.error else "ok",
	)
	if outcome.error:
		db.add(record)
		await db.commit()
		return TurnResult(package=record, outcome=outcome)

	reply_class = await classify_text(outcome.content, prepared.policy, None)
	next_seq = (await db.scalar(select(func.coalesce(func.max(ConversationTurn.seq), 0)).where(ConversationTurn.conversation_id == prepared.conversation_id))) + 1
	stored_question, _ = payload_capture.prepare_output(prepared.content)
	stored_answer, _ = payload_capture.prepare_output(outcome.content)
	user_turn = ConversationTurn(
		org_id=prepared.org_id, conversation_id=prepared.conversation_id, seq=next_seq, role="user", content=stored_question,
		data_class=prepared.new_class.data_class,
	)
	# The answer was written from everything the model saw, so it carries the highest class among that and its own content.
	assistant_turn = ConversationTurn(
		org_id=prepared.org_id, conversation_id=prepared.conversation_id, seq=next_seq + 1, role="assistant", content=stored_answer,
		data_class=_highest(reply_class.data_class, prepared.package_class), model=prepared.model,
	)
	db.add_all([user_turn, assistant_turn])
	await db.flush()
	record.assistant_turn_id = assistant_turn.id
	db.add(record)
	conversation.updated_at = func.now()
	await db.commit()
	await db.refresh(user_turn)
	await db.refresh(assistant_turn)
	await db.refresh(record)
	return TurnResult(user_turn=user_turn, assistant_turn=assistant_turn, package=record, outcome=outcome)


async def run_turn(db: AsyncSession, redis, *, conversation: Conversation, **kwargs) -> TurnResult:
	"""One whole turn, answered in one piece. Never raises for a model or policy failure: those come back as ``outcome``."""
	prepared = await begin_turn(db, redis, conversation=conversation, **kwargs)
	if isinstance(prepared, TurnResult):
		return prepared
	outcome = await execute_plan(prepared.plan, redis=redis, org_id=prepared.org_id, user_id=prepared.user_id)
	return await finalize_turn(db, conversation, prepared, outcome)


async def stream_turn(prepared: PreparedTurn, redis):
	"""One turn as events: ``("context", dict)``, then ``("delta", dict)`` for each piece of text, then ``("done", TurnResult)`` or
	``("error", TurnResult)``. Storing happens in a session of its own, because the request's session may be closed by then.

	If the caller disconnects the generator is closed: nothing is stored (an answer nobody received is not a turn), the call is
	audit-logged as abandoned by the runner, and the lock is the route's to release."""
	package = prepared.package
	yield "context", {
		"model": prepared.model, "data_class": prepared.package_class, "routing_mode": prepared.policy.routing_mode,
		"included_turn_ids": [str(i) for i in package.included_ids], "withheld": _withheld_json(package.withheld),
		"would_withhold": _withheld_json(prepared.preview), "estimated_tokens": package.estimated_tokens,
	}
	outcome: RunOutcome | None = None
	inner = stream_plan(prepared.plan, redis=redis, org_id=prepared.org_id, user_id=prepared.user_id)
	try:
		async for item in inner:
			if isinstance(item, RunOutcome):
				outcome = item
			else:
				yield "delta", {"text": item}
	finally:
		# Closing this generator must close the provider stream now, so an abandoned call is audited and priced before this returns,
		# not whenever the garbage collector reaches it (or never, if the process exits first).
		await inner.aclose()
	assert outcome is not None
	async with org_scoped_session(prepared.org_id) as db:
		conversation = await db.get(Conversation, prepared.conversation_id)
		if conversation is None:  # deleted while the answer was streaming
			yield "error", TurnResult(outcome=RunOutcome(error="the conversation was deleted"))
			return
		result = await finalize_turn(db, conversation, prepared, outcome)
	yield ("error" if outcome.error else "done"), result
