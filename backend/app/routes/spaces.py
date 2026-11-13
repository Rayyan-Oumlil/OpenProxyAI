"""Project spaces: /api/v1/spaces.

A space is a folder for finding conversations. It never changes who can read one:

- a space is visible to its owner, and to the members of its team when it has one (an admin is not special);
- only the owner renames, moves or deletes it; anyone else gets a 404, so its existence is not revealed;
- the conversation count shows only conversations the caller could already read.

Which conversations are in a space, and filing one, are on ``/api/v1/conversations`` (``space_id``), where the conversation's
own owner / team / visibility rule applies.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import CurrentUser, get_db, get_redis
from app.models.conversation import Conversation
from app.models.space import Space
from app.routes.conversations import _WRITE_ROLES, _require_enabled, _validate_team, visible_spaces, visible_to
from app.schemas.conversation import MAX_SPACES_PER_USER, SpaceCreate, SpaceResponse, SpaceUpdate

router = APIRouter(prefix="/api/v1/spaces", tags=["Conversations"])


def _not_found() -> HTTPException:
	return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Space not found")


def _name_taken() -> HTTPException:
	return HTTPException(
		status_code=status.HTTP_409_CONFLICT, detail={"error": "space_name_taken", "detail": "You already have a space with that name."}
	)


async def _responses(db: AsyncSession, user, rows: list[Space]) -> list[SpaceResponse]:
	counts = {}
	if rows:
		counts = dict((await db.execute(
			select(Conversation.space_id, func.count())
			.where(Conversation.space_id.in_([row.id for row in rows]), Conversation.org_id == user.org_id, visible_to(user))
			.group_by(Conversation.space_id)
		)).all())
	return [
		SpaceResponse(
			id=row.id, name=row.name, team_id=row.team_id, owner_id=row.owner_id, is_owner=row.owner_id == user.id,
			conversation_count=int(counts.get(row.id, 0)), created_at=row.created_at,
		)
		for row in rows
	]


async def _load_owned(db: AsyncSession, user, space_id: UUID) -> Space:
	row = await db.scalar(select(Space).where(Space.id == space_id, Space.org_id == user.org_id, Space.owner_id == user.id))
	if row is None:
		raise _not_found()
	return row


@router.post("", response_model=SpaceResponse, status_code=status.HTTP_201_CREATED)
async def create_space(
	payload: SpaceCreate, current_user: CurrentUser, db: AsyncSession = Depends(get_db), redis=Depends(get_redis)
) -> SpaceResponse:
	if current_user.role not in _WRITE_ROLES:
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Your role cannot create spaces")
	await _require_enabled(redis, db, current_user)
	if payload.team_id is not None:
		await _validate_team(db, current_user, payload.team_id)
	owned = await db.scalar(select(func.count()).select_from(Space).where(Space.owner_id == current_user.id))
	if (owned or 0) >= MAX_SPACES_PER_USER:
		raise HTTPException(
			status_code=status.HTTP_409_CONFLICT,
			detail={"error": "too_many_spaces", "detail": f"You can keep at most {MAX_SPACES_PER_USER} spaces. Delete some first."},
		)
	row = Space(org_id=current_user.org_id, owner_id=current_user.id, team_id=payload.team_id, name=payload.name)
	db.add(row)
	try:
		await db.commit()
	except IntegrityError:  # the unique index on (owner, lower(name)); two requests with the same name race here
		await db.rollback()
		raise _name_taken()
	await db.refresh(row)
	return (await _responses(db, current_user, [row]))[0]


@router.get("", response_model=list[SpaceResponse])
async def list_spaces(current_user: CurrentUser, db: AsyncSession = Depends(get_db)) -> list[SpaceResponse]:
	"""The spaces the caller can see: their own and their teams'."""
	rows = (await db.scalars(select(Space).where(Space.org_id == current_user.org_id, visible_spaces(current_user)).order_by(func.lower(Space.name), Space.id))).all()
	return await _responses(db, current_user, list(rows))


@router.patch("/{space_id}", response_model=SpaceResponse)
async def update_space(space_id: UUID, payload: SpaceUpdate, current_user: CurrentUser, db: AsyncSession = Depends(get_db)) -> SpaceResponse:
	row = await _load_owned(db, current_user, space_id)
	changes = payload.model_fields_set
	if "team_id" in changes:
		if payload.team_id is not None:
			await _validate_team(db, current_user, payload.team_id)
		row.team_id = payload.team_id
	if "name" in changes:
		row.name = payload.name
	try:
		await db.commit()
	except IntegrityError:
		await db.rollback()
		raise _name_taken()
	await db.refresh(row)
	return (await _responses(db, current_user, [row]))[0]


@router.delete("/{space_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_space(space_id: UUID, current_user: CurrentUser, db: AsyncSession = Depends(get_db)) -> Response:
	"""Deleting a space un-files its conversations (the database does it); no conversation is deleted."""
	row = await _load_owned(db, current_user, space_id)
	await db.delete(row)
	await db.commit()
	return Response(status_code=status.HTTP_204_NO_CONTENT)
