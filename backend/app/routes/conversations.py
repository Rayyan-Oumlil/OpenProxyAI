"""Conversations: /api/v1/conversations (Phase 4).

Who sees what, inside an org (RLS only separates orgs, so this is enforced here and proven per route in the tests):

- the owner reads, edits, shares and deletes their conversation;
- a teammate reads a conversation its owner shared with a team they belong to, and nothing more;
- an admin can list every conversation in the org as *metadata* (title, owner, size) and delete one, which is audited. An
  admin cannot read another user's turns: a private conversation is private, and an audit of who is using the feature does not
  need what they said.

A conversation the caller may not see is a 404, never a 403, so its existence is not revealed.
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import CurrentUser, get_db, get_redis
from app.models.conversation import ORG, PRIVATE, TEAM, Conversation, ConversationContextPackage, ConversationTurn
from app.models.team import Team, team_members
from app.models.user import User
from app.schemas.conversation import (
	MAX_PER_USER,
	ConversationCreate,
	ConversationResponse,
	ContextSummary,
	ModelChoice,
	TeamChoice,
	ConversationUpdate,
	TurnExchange,
	TurnRequest,
	TurnResponse,
)
from app.services.admin_audit_service import get_ip, log_admin_action
from app.services.data_class import DATA_CLASSES
from app.services.routing_service import clearance, load_candidates
from app.services.conversation_turns import DEFAULT_CONTEXT_TOKENS, PreparedTurn, TurnResult, begin_turn, run_turn, stream_turn
from app.services.policy_service import POLICY_BLOCK_STATUS, policy_store
from app.services.rate_limiter import rate_limiter_service

router = APIRouter(prefix="/api/v1/conversations", tags=["Conversations"])

_WRITE_ROLES = frozenset({"admin", "developer"})  # who may start a conversation (a viewer may read what a teammate shared)


def _not_found() -> HTTPException:
	return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")


def _my_teams(user):
	return select(team_members.c.team_id).where(team_members.c.user_id == user.id)


def visible_to(user):
	"""SQL condition: conversations this user may read."""
	return or_(
		Conversation.owner_id == user.id,
		Conversation.visibility == ORG,
		and_(Conversation.visibility == TEAM, Conversation.team_id.in_(_my_teams(user))),
	)


async def load_readable(db: AsyncSession, user, conversation_id: UUID) -> Conversation:
	row = await db.scalar(select(Conversation).where(Conversation.id == conversation_id, Conversation.org_id == user.org_id, visible_to(user)))
	if row is None:
		raise _not_found()
	return row


async def load_owned(db: AsyncSession, user, conversation_id: UUID) -> Conversation:
	"""The conversation if the caller owns it. A teammate who can read it still gets a 404 here, not a 403."""
	row = await db.scalar(select(Conversation).where(Conversation.id == conversation_id, Conversation.org_id == user.org_id, Conversation.owner_id == user.id))
	if row is None:
		raise _not_found()
	return row


async def _require_enabled(redis, db: AsyncSession, user) -> None:
	policy = await policy_store.load(user.org_id, db, redis)
	if not policy.conversations_enabled:
		raise HTTPException(
			status_code=status.HTTP_403_FORBIDDEN,
			detail={"error": "conversations_disabled", "detail": "Conversations are not enabled for this organization."},
		)


def _require_admin_to_publish(user) -> None:
	"""Org-wide sharing puts a conversation in front of every member, so only an admin may do it (and only with their own)."""
	if user.role != "admin":
		raise HTTPException(
			status_code=status.HTTP_403_FORBIDDEN,
			detail={"error": "admin_only", "detail": "Only an organization admin can share a conversation with the whole organization."},
		)


async def _validate_team(db: AsyncSession, user, team_id: UUID) -> None:
	"""The team must be in the caller's org and the caller a member: you cannot share with a team you are not in."""
	in_org = await db.scalar(select(Team.id).where(Team.id == team_id, Team.org_id == user.org_id))
	member = in_org is not None and await db.scalar(
		select(team_members.c.user_id).where(team_members.c.team_id == team_id, team_members.c.user_id == user.id)
	)
	if not member:
		raise HTTPException(
			status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
			detail={"error": "not_a_team_member", "detail": "You can only share a conversation with a team you belong to."},
		)


async def _responses(db: AsyncSession, user, rows: list[Conversation]) -> list[ConversationResponse]:
	if not rows:
		return []
	counts = dict((await db.execute(
		select(ConversationTurn.conversation_id, func.count())
		.where(ConversationTurn.conversation_id.in_([row.id for row in rows])).group_by(ConversationTurn.conversation_id)
	)).all())
	emails = dict((await db.execute(select(User.id, User.email).where(User.id.in_({row.owner_id for row in rows})))).all())
	my_teams = set((await db.scalars(_my_teams(user))).all())

	def may_read(row: Conversation) -> bool:
		# The org-wide listing is metadata for admins: a persona is content, so it is shown only where the caller could read the conversation.
		return row.owner_id == user.id or row.visibility == ORG or (row.visibility == TEAM and row.team_id in my_teams)

	return [
		ConversationResponse(
			id=row.id, title=row.title, visibility=PRIVATE if row.visibility == TEAM and not row.team_id else row.visibility, team_id=row.team_id, tags=list(row.tags or []), system_prompt=row.system_prompt if may_read(row) else None, owner_id=row.owner_id,
			owner_email=emails.get(row.owner_id), is_owner=row.owner_id == user.id, turn_count=int(counts.get(row.id, 0)),
			created_at=row.created_at, updated_at=row.updated_at,
		)
		for row in rows
	]


@router.post("", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
	payload: ConversationCreate, current_user: CurrentUser, db: AsyncSession = Depends(get_db), redis=Depends(get_redis)
) -> ConversationResponse:
	if current_user.role not in _WRITE_ROLES:
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Your role cannot start conversations")
	await _require_enabled(redis, db, current_user)
	if payload.visibility == ORG:
		_require_admin_to_publish(current_user)
	if payload.team_id is not None:
		await _validate_team(db, current_user, payload.team_id)
	owned = await db.scalar(select(func.count()).select_from(Conversation).where(Conversation.owner_id == current_user.id))
	if (owned or 0) >= MAX_PER_USER:
		raise HTTPException(
			status_code=status.HTTP_409_CONFLICT,
			detail={"error": "too_many_conversations", "detail": f"You can keep at most {MAX_PER_USER} conversations. Delete some first."},
		)
	row = Conversation(
		org_id=current_user.org_id, owner_id=current_user.id, team_id=payload.team_id, title=payload.title,
		visibility=payload.visibility, tags=payload.tags, system_prompt=payload.system_prompt,
	)
	db.add(row)
	await db.commit()
	await db.refresh(row)
	return (await _responses(db, current_user, [row]))[0]


@router.get("", response_model=list[ConversationResponse])
async def list_conversations(
	current_user: CurrentUser,
	scope: Literal["mine", "shared", "org"] = Query("mine", description="mine: yours; shared: teammates' shared with you; org: every conversation, admins only, metadata"),
	limit: int = Query(100, ge=1, le=200),
	offset: int = Query(0, ge=0),
	db: AsyncSession = Depends(get_db),
) -> list[ConversationResponse]:
	query = select(Conversation).where(Conversation.org_id == current_user.org_id)
	if scope == "mine":
		query = query.where(Conversation.owner_id == current_user.id)
	elif scope == "shared":
		query = query.where(Conversation.owner_id != current_user.id, visible_to(current_user))
	elif current_user.role != "admin":
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only organization admins can list every conversation")
	rows = (await db.scalars(query.order_by(Conversation.updated_at.desc(), Conversation.id).limit(limit).offset(offset))).all()
	return await _responses(db, current_user, list(rows))


@router.get("/teams", response_model=list[TeamChoice])
async def my_teams(current_user: CurrentUser, db: AsyncSession = Depends(get_db)) -> list[TeamChoice]:
	"""The teams the caller belongs to: the only ones a conversation can be shared with."""
	rows = await db.execute(select(Team.id, Team.name).where(Team.org_id == current_user.org_id, Team.id.in_(_my_teams(current_user))).order_by(Team.name))
	return [TeamChoice(id=i, name=n) for i, n in rows.all()]


@router.get("/models", response_model=list[ModelChoice])
async def usable_models(current_user: CurrentUser, db: AsyncSession = Depends(get_db)) -> list[ModelChoice]:
	"""Registry models that are enabled and have an active key, with the most sensitive class each may receive. Lets the picker
	say up front which models will not see an earlier confidential turn."""
	candidates = await load_candidates(db, current_user.org_id)
	usable = [c for c in candidates if c.enabled and c.key_active]
	return [ModelChoice(model_id=c.model_id, max_data_class=DATA_CLASSES[clearance(c)]) for c in sorted(usable, key=lambda c: c.model_id)]


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(conversation_id: UUID, current_user: CurrentUser, db: AsyncSession = Depends(get_db)) -> ConversationResponse:
	return (await _responses(db, current_user, [await load_readable(db, current_user, conversation_id)]))[0]


@router.get("/{conversation_id}/turns", response_model=list[TurnResponse])
async def list_turns(conversation_id: UUID, current_user: CurrentUser, db: AsyncSession = Depends(get_db)) -> list[TurnResponse]:
	await load_readable(db, current_user, conversation_id)
	rows = await db.scalars(select(ConversationTurn).where(ConversationTurn.conversation_id == conversation_id).order_by(ConversationTurn.seq))
	return [
		TurnResponse(id=t.id, seq=t.seq, role=t.role, content=t.content, data_class=t.data_class, model=t.model, created_at=t.created_at)
		for t in rows
	]


@router.patch("/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
	conversation_id: UUID, payload: ConversationUpdate, current_user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> ConversationResponse:
	row = await load_owned(db, current_user, conversation_id)
	changes = payload.model_fields_set
	if "title" in changes:
		row.title = payload.title
	if "tags" in changes:
		row.tags = payload.tags
	if "system_prompt" in changes:
		row.system_prompt = payload.system_prompt
	if "visibility" in changes or "team_id" in changes:
		visibility = payload.visibility if "visibility" in changes else row.visibility
		team_id = payload.team_id if "team_id" in changes else row.team_id
		if visibility in (PRIVATE, ORG):
			if "team_id" in changes and payload.team_id is not None:
				raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="team_id is only for a conversation shared with a team")
			if visibility == ORG and row.visibility != ORG:
				_require_admin_to_publish(current_user)
			team_id = None
		elif team_id is None:
			raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="team_id is required when visibility is 'team'")
		else:
			await _validate_team(db, current_user, team_id)
		row.visibility, row.team_id = visibility, team_id
	row.updated_at = func.now()
	await db.commit()
	await db.refresh(row)
	return (await _responses(db, current_user, [row]))[0]


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(conversation_id: UUID, request: Request, current_user: CurrentUser, db: AsyncSession = Depends(get_db)) -> Response:
	"""The owner deletes their own. An admin may delete any (to enforce retention or remove something that should not be
	kept), and that is written to the admin audit log with the owner's id but never the content."""
	row = await db.scalar(select(Conversation).where(Conversation.id == conversation_id, Conversation.org_id == current_user.org_id))
	if row is None or (row.owner_id != current_user.id and current_user.role != "admin"):
		raise _not_found()
	if row.owner_id != current_user.id:
		await log_admin_action(
			db, org_id=current_user.org_id, actor_id=current_user.id, actor_email=current_user.email, action="conversation.deleted",
			resource_type="conversation", resource_id=str(row.id), after={"owner_id": str(row.owner_id), "visibility": row.visibility},
			ip_address=get_ip(request),
		)
	await db.delete(row)
	await db.commit()
	return Response(status_code=status.HTTP_204_NO_CONTENT)


_TURN_LOCK_SECONDS = 180  # longer than a model call can take; a crashed request frees the conversation when it expires


def _turn_response(turn: ConversationTurn) -> TurnResponse:
	return TurnResponse(id=turn.id, seq=turn.seq, role=turn.role, content=turn.content, data_class=turn.data_class, model=turn.model, created_at=turn.created_at)


def _context_summary(package: ConversationContextPackage) -> ContextSummary:
	return ContextSummary(
		package_id=package.id, model=package.model, data_class=package.data_class, routing_mode=package.routing_mode,
		included_turn_ids=package.included_turn_ids, withheld=package.withheld, estimated_tokens=package.estimated_tokens,
		payload_sha256=package.payload_sha256, outcome=package.outcome, would_withhold=package.would_withhold, created_at=package.created_at,
	)


async def _rate_limit(redis, user, policy, model: str, estimated_tokens: int) -> None:
	ok, _, limit_type, limit_detail, retry_after = await rate_limiter_service.check_limits(
		redis=redis, org_id=str(user.org_id), user_id=str(user.id), request_tokens_estimate=estimated_tokens,
		max_rpm=settings.DEFAULT_RATE_LIMIT_RPM, max_tpm=settings.DEFAULT_RATE_LIMIT_TPM,
		max_daily_budget_usd=Decimal(str(settings.DEFAULT_BUDGET_DAILY_USD)), user_daily_budget_usd=getattr(user, "budget_daily_usd", None),
		model=model, policy_config=policy,
	)
	if not ok:
		raise HTTPException(
			status_code=status.HTTP_429_TOO_MANY_REQUESTS,
			detail={"error": "rate_limit_exceeded", "limit_type": limit_type, "detail": limit_detail, "retry_after": retry_after},
		)


def _sse(event: str, data: dict) -> str:
	return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


def _exchange(result: TurnResult) -> TurnExchange:
	outcome = result.outcome
	return TurnExchange(
		user_turn=_turn_response(result.user_turn), assistant_turn=_turn_response(result.assistant_turn), context=_context_summary(result.package),
		prompt_tokens=outcome.prompt_tokens, completion_tokens=outcome.completion_tokens, cost_usd=str(outcome.cost_usd),
	)


def _raise_for_failure(result: TurnResult) -> None:
	outcome = result.outcome
	if outcome.refused:
		raise HTTPException(status_code=POLICY_BLOCK_STATUS, detail={"error": "refused", "detail": outcome.error})
	if outcome.error:
		detail = {"error": "model_error", "detail": outcome.error}
		if result.package is not None:
			detail["package_id"] = str(result.package.id)
		raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail)


async def _events(prepared: PreparedTurn, redis, lock_key: str):
	"""The SSE body. The lock is held for as long as the answer is being written and released however the stream ends."""
	try:
		async for event, data in stream_turn(prepared, redis):
			if event in ("done", "error"):
				result: TurnResult = data
				if event == "done":
					exchange = _exchange(result)
					yield _sse("done", json.loads(exchange.model_dump_json()))
				else:
					yield _sse("error", {"error": "model_error", "detail": result.outcome.error, **({"package_id": str(result.package.id)} if result.package else {})})
			else:
				yield _sse(event, data)
	finally:
		await redis.delete(lock_key)


@router.post("/{conversation_id}/turns", response_model=TurnExchange, status_code=status.HTTP_201_CREATED)
async def add_turn(
	conversation_id: UUID, payload: TurnRequest, current_user: CurrentUser, db: AsyncSession = Depends(get_db), redis=Depends(get_redis)
) -> TurnExchange:
	"""Ask the model a question in this conversation. Only the owner can. See ``services/conversation_turns.py`` for the order of
	guards; in short, the model sees only the earlier turns it is cleared for, and the reply says which it did not see."""
	if current_user.role not in _WRITE_ROLES:
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Your role cannot add turns")
	conversation = await load_owned(db, current_user, conversation_id)
	await _require_enabled(redis, db, current_user)
	policy = await policy_store.load(current_user.org_id, db, redis)

	if payload.stream and policy.response_guardrails_enabled:
		raise HTTPException(
			status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
			detail={
				"error": "streaming_unavailable",
				"detail": "This organization checks answers against response guardrails, which needs the whole answer before any of it is delivered. Ask for the answer without streaming.",
			},
		)

	lock_key = f"conversation-turn:{conversation.id}"
	if not await redis.set(lock_key, "1", nx=True, ex=_TURN_LOCK_SECONDS):
		raise HTTPException(
			status_code=status.HTTP_409_CONFLICT,
			detail={"error": "turn_in_progress", "detail": "Another message in this conversation is still being answered."},
		)
	options = dict(
		user_id=current_user.id, model=payload.model, content=payload.content, asserted_class=payload.data_class, policy=policy,
		system_prompt=payload.system_prompt or conversation.system_prompt, temperature=payload.temperature, max_tokens=payload.max_tokens,
		token_budget=payload.max_context_tokens or DEFAULT_CONTEXT_TOKENS,
		before_call=lambda tokens: _rate_limit(redis, current_user, policy, payload.model, tokens),
	)
	if payload.stream:
		try:
			prepared = await begin_turn(db, redis, conversation=conversation, **options)
		except BaseException:
			await redis.delete(lock_key)
			raise
		if isinstance(prepared, TurnResult):  # refused, or no key: the same errors as without streaming, before any stream starts
			await redis.delete(lock_key)
			_raise_for_failure(prepared)
		return StreamingResponse(
			_events(prepared, redis, lock_key), media_type="text/event-stream",
			headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "X-OpenProxyAI-Request-Id": str(prepared.plan.request_id)},
		)
	try:
		result = await run_turn(db, redis, conversation=conversation, **options)
	finally:
		await redis.delete(lock_key)
	_raise_for_failure(result)
	return _exchange(result)


@router.get("/{conversation_id}/turns/{turn_id}/context", response_model=ContextSummary)
async def get_turn_context(conversation_id: UUID, turn_id: UUID, current_user: CurrentUser, db: AsyncSession = Depends(get_db)) -> ContextSummary:
	"""What was sent to the model for this answer: which earlier turns, which were withheld and why."""
	await load_readable(db, current_user, conversation_id)
	package = await db.scalar(
		select(ConversationContextPackage).where(
			ConversationContextPackage.conversation_id == conversation_id, ConversationContextPackage.assistant_turn_id == turn_id
		)
	)
	if package is None:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No context record for this turn")
	return _context_summary(package)
