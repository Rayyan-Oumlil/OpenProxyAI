"""Team management endpoints — CRUD and member management for departmental cost attribution."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import delete, func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import CurrentUser, get_db
from app.models.team import Team, team_members
from app.models.user import User
from app.schemas.team import (
    TeamCreateRequest,
    TeamDetailResponse,
    TeamMemberResponse,
    TeamResponse,
    TeamUpdateRequest,
)
from app.services.admin_audit_service import get_ip, log_admin_action, serialize_team

router = APIRouter(prefix="/api/v1/teams", tags=["Teams"])

_ADMIN_ONLY = "Only admins can manage teams"


def _to_response(team: Team, member_count: int = 0) -> TeamResponse:
    return TeamResponse(
        id=team.id,
        org_id=team.org_id,
        name=team.name,
        budget_monthly_usd=team.budget_monthly_usd,
        created_at=team.created_at,
        member_count=member_count,
    )


@router.get("", response_model=list[TeamResponse])
async def list_teams(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    membership: str | None = None,
) -> list[TeamResponse]:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=_ADMIN_ONLY)

    member_counts = (
        select(team_members.c.team_id, func.count().label("cnt"))
        .group_by(team_members.c.team_id)
        .subquery()
    )
    stmt = (
        select(Team, member_counts.c.cnt)
        .outerjoin(member_counts, Team.id == member_counts.c.team_id)
        .where(Team.org_id == current_user.org_id)
        .order_by(Team.created_at.desc())
    )
    if membership == "me":
        my_teams = select(team_members.c.team_id).where(team_members.c.user_id == current_user.id)
        stmt = stmt.where(Team.id.in_(my_teams))
    rows = (await db.execute(stmt)).all()
    return [_to_response(team, member_count=int(cnt) if cnt is not None else 0) for team, cnt in rows]


@router.post("", response_model=TeamResponse, status_code=status.HTTP_201_CREATED)
async def create_team(
    payload: TeamCreateRequest,
    request: Request,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> TeamResponse:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=_ADMIN_ONLY)

    team = Team(
        org_id=current_user.org_id,
        name=payload.name,
        budget_monthly_usd=payload.budget_monthly_usd,
    )
    db.add(team)
    await db.flush()

    await log_admin_action(
        db,
        org_id=current_user.org_id,
        actor_id=current_user.id,
        actor_email=current_user.email,
        action="team.created",
        resource_type="team",
        resource_id=str(team.id),
        before=None,
        after=serialize_team(team),
        ip_address=get_ip(request),
    )

    await db.commit()
    await db.refresh(team)
    return _to_response(team, member_count=0)


@router.get("/{team_id}", response_model=TeamDetailResponse)
async def get_team(
    team_id: uuid.UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> TeamDetailResponse:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=_ADMIN_ONLY)

    team = await db.scalar(
        select(Team).where(
            Team.id == team_id,
            Team.org_id == current_user.org_id,
        )
    )
    if team is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")

    member_ids = (
        await db.scalars(
            select(team_members.c.user_id).where(team_members.c.team_id == team_id)
        )
    ).all()

    members: list[TeamMemberResponse] = []
    if member_ids:
        users = (
            await db.scalars(
                select(User).where(
                    User.id.in_(member_ids),
                    User.org_id == current_user.org_id,
                )
            )
        ).all()
        members = [
            TeamMemberResponse(id=u.id, email=u.email, name=u.name)
            for u in users
        ]

    return TeamDetailResponse(
        id=team.id,
        org_id=team.org_id,
        name=team.name,
        budget_monthly_usd=team.budget_monthly_usd,
        created_at=team.created_at,
        member_count=len(members),
        members=members,
    )


@router.patch("/{team_id}", response_model=TeamResponse)
async def update_team(
    team_id: uuid.UUID,
    payload: TeamUpdateRequest,
    request: Request,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> TeamResponse:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=_ADMIN_ONLY)

    team = await db.scalar(
        select(Team).where(
            Team.id == team_id,
            Team.org_id == current_user.org_id,
        )
    )
    if team is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")

    before = serialize_team(team)
    updates = payload.model_dump(exclude_unset=True)
    for field_name, field_value in updates.items():
        setattr(team, field_name, field_value)
    after = serialize_team(team)

    await log_admin_action(
        db,
        org_id=current_user.org_id,
        actor_id=current_user.id,
        actor_email=current_user.email,
        action="team.updated",
        resource_type="team",
        resource_id=str(team_id),
        before=before,
        after=after,
        ip_address=get_ip(request),
    )

    await db.commit()
    await db.refresh(team)

    count_row = await db.execute(
        select(func.count()).select_from(team_members).where(team_members.c.team_id == team_id)
    )
    count = count_row.scalar_one() or 0
    return _to_response(team, member_count=count)


@router.delete("/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_team(
    team_id: uuid.UUID,
    request: Request,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> None:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=_ADMIN_ONLY)

    team = await db.scalar(
        select(Team).where(
            Team.id == team_id,
            Team.org_id == current_user.org_id,
        )
    )
    if team is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")

    before = serialize_team(team)

    await log_admin_action(
        db,
        org_id=current_user.org_id,
        actor_id=current_user.id,
        actor_email=current_user.email,
        action="team.deleted",
        resource_type="team",
        resource_id=str(team_id),
        before=before,
        after=None,
        ip_address=get_ip(request),
    )

    await db.delete(team)
    await db.commit()


@router.post("/{team_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def add_team_member(
    team_id: uuid.UUID,
    user_id: uuid.UUID,
    request: Request,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> None:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=_ADMIN_ONLY)

    team = await db.scalar(
        select(Team).where(
            Team.id == team_id,
            Team.org_id == current_user.org_id,
        )
    )
    if team is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")

    user = await db.scalar(
        select(User).where(
            User.id == user_id,
            User.org_id == current_user.org_id,
        )
    )
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    existing = await db.execute(
        select(team_members).where(
            team_members.c.team_id == team_id,
            team_members.c.user_id == user_id,
        )
    )
    if existing.first() is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already a member of this team",
        )

    await db.execute(
        insert(team_members).values(team_id=team_id, user_id=user_id)
    )

    await log_admin_action(
        db,
        org_id=current_user.org_id,
        actor_id=current_user.id,
        actor_email=current_user.email,
        action="team.member_added",
        resource_type="team",
        resource_id=str(team_id),
        before=None,
        after={"user_id": str(user_id), "user_email": user.email},
        ip_address=get_ip(request),
    )

    await db.commit()


@router.delete("/{team_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_team_member(
    team_id: uuid.UUID,
    user_id: uuid.UUID,
    request: Request,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> None:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=_ADMIN_ONLY)

    team = await db.scalar(
        select(Team).where(
            Team.id == team_id,
            Team.org_id == current_user.org_id,
        )
    )
    if team is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")

    result = await db.execute(
        delete(team_members).where(
            team_members.c.team_id == team_id,
            team_members.c.user_id == user_id,
        )
    )
    if result.rowcount == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not a member of this team",
        )

    await log_admin_action(
        db,
        org_id=current_user.org_id,
        actor_id=current_user.id,
        actor_email=current_user.email,
        action="team.member_removed",
        resource_type="team",
        resource_id=str(team_id),
        before={"user_id": str(user_id)},
        after=None,
        ip_address=get_ip(request),
    )

    await db.commit()
