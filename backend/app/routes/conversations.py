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

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import CurrentUser, get_db, get_redis
from app.models.conversation import PRIVATE, TEAM, Conversation, ConversationTurn
from app.models.team import Team, team_members
from app.models.user import User
from app.schemas.conversation import (
	MAX_PER_USER,
	ConversationCreate,
	ConversationResponse,
	ConversationUpdate,
	TurnResponse,
)
from app.services.admin_audit_service import get_ip, log_admin_action
from app.services.policy_service import policy_store

router = APIRouter(prefix="/api/v1/conversations", tags=["Conversations"])

_WRITE_ROLES = frozenset({"admin", "developer"})  # who may start a conversation (a viewer may read what a teammate shared)


def _not_found() -> HTTPException:
	return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")


def _my_teams(user):
	return select(team_members.c.team_id).where(team_members.c.user_id == user.id)


def visible_to(user):
	"""SQL condition: conversations this user may read."""
	return or_(Conversation.owner_id == user.id, and_(Conversation.visibility == TEAM, Conversation.team_id.in_(_my_teams(user))))


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
	return [
		ConversationResponse(
			id=row.id, title=row.title, visibility=row.visibility if row.team_id else PRIVATE, team_id=row.team_id, tags=list(row.tags or []), owner_id=row.owner_id,
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
		visibility=payload.visibility, tags=payload.tags,
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
	if "visibility" in changes or "team_id" in changes:
		visibility = payload.visibility if "visibility" in changes else row.visibility
		team_id = payload.team_id if "team_id" in changes else row.team_id
		if visibility == PRIVATE:
			if "team_id" in changes and payload.team_id is not None:
				raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="team_id is only for a conversation shared with a team")
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
