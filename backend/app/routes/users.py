"""User management endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import CurrentUser, get_db
from app.models.user import User
from app.schemas.user import UserResponse, UserUpdateRequest

router = APIRouter(prefix="/api/v1/users", tags=["Users"])


@router.get("", response_model=list[UserResponse])
async def list_users(
	current_user: CurrentUser,
	db: AsyncSession = Depends(get_db),
) -> list[UserResponse]:
	rows = await db.scalars(
		select(User)
		.where(User.org_id == current_user.org_id)
		.order_by(User.created_at.desc())
	)
	return [UserResponse.model_validate(row) for row in rows]


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
	user_id: uuid.UUID,
	current_user: CurrentUser,
	db: AsyncSession = Depends(get_db),
) -> UserResponse:
	model = await db.scalar(
		select(User).where(User.id == user_id, User.org_id == current_user.org_id)
	)
	if model is None:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
	return UserResponse.model_validate(model)


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
	user_id: uuid.UUID,
	payload: UserUpdateRequest,
	current_user: CurrentUser,
	db: AsyncSession = Depends(get_db),
) -> UserResponse:
	if current_user.role != "admin":
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

	model = await db.scalar(
		select(User).where(User.id == user_id, User.org_id == current_user.org_id)
	)
	if model is None:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

	updates = payload.model_dump(exclude_unset=True)
	role_after = updates.get("role", model.role)
	is_active_after = updates.get("is_active", model.is_active)

	removes_admin_access = model.role == "admin" and model.is_active and (
		role_after != "admin" or is_active_after is False
	)
	if removes_admin_access and model.id == current_user.id:
		raise HTTPException(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail="Cannot remove your own active admin access",
		)

	if removes_admin_access:
		active_admin_ids = list(
			await db.scalars(
				select(User.id).where(
					User.org_id == current_user.org_id,
					User.role == "admin",
					User.is_active.is_(True),
				)
			)
		)
		if len(active_admin_ids) <= 1 and model.id in active_admin_ids:
			raise HTTPException(
				status_code=status.HTTP_400_BAD_REQUEST,
				detail="Cannot remove the last active admin in organization",
			)

	for field_name, field_value in updates.items():
		setattr(model, field_name, field_value)

	await db.commit()
	await db.refresh(model)
	return UserResponse.model_validate(model)
