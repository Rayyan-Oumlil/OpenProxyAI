"""User management endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import CurrentUser, get_db
from app.models.user import User
from app.schemas.user import UserResponse, UserUpdateRequest
from app.services.admin_audit_service import get_ip, log_admin_action, serialize_user

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
	request: Request,
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

	before = serialize_user(model)

	for field_name, field_value in updates.items():
		setattr(model, field_name, field_value)

	# Determine the most specific action
	if updates.get("is_active") is False:
		action = "user.deactivated"
	elif "role" in updates:
		action = "user.role_changed"
	else:
		action = "user.updated"

	await log_admin_action(
		db,
		org_id=current_user.org_id,
		actor_id=current_user.id,
		actor_email=current_user.email,
		action=action,
		resource_type="user",
		resource_id=str(user_id),
		before=before,
		after=serialize_user(model),
		ip_address=get_ip(request),
	)

	await db.commit()
	await db.refresh(model)
	return UserResponse.model_validate(model)
