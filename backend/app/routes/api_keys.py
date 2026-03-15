"""API key management — list, create, revoke keys."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import CurrentUser, get_db
from app.models.api_key import ApiKey
from app.models.organization import Organization
from app.schemas.auth import APIKeyCreateRequest, APIKeyCreatedResponse, APIKeyResponse
from app.services.auth_service import create_api_key
from app.services.plan_service import check_api_key_limit

router = APIRouter(prefix="/api/v1/api-keys", tags=["API Keys"])


@router.get("", response_model=list[APIKeyResponse])
async def list_api_keys(
	current_user: CurrentUser,
	db: AsyncSession = Depends(get_db),
) -> list[APIKeyResponse]:
	rows = await db.scalars(
		select(ApiKey)
		.where(ApiKey.org_id == current_user.org_id, ApiKey.user_id == current_user.id)
		.order_by(ApiKey.created_at.desc())
	)
	return [APIKeyResponse.model_validate(row) for row in rows]


@router.post("", response_model=APIKeyCreatedResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key_route(
	payload: APIKeyCreateRequest,
	current_user: CurrentUser,
	db: AsyncSession = Depends(get_db),
) -> APIKeyCreatedResponse:
	# Enforce per-plan API key limit
	org = await db.get(Organization, current_user.org_id)
	result = await db.execute(
		select(func.count()).where(
			ApiKey.org_id == current_user.org_id,
			ApiKey.is_active == True,  # noqa: E712
		)
	)
	key_count = result.scalar_one()
	check_api_key_limit(org, key_count)

	model, full_key = await create_api_key(
		db=db,
		user_id=current_user.id,
		org_id=current_user.org_id,
		name=payload.name,
		permissions=payload.permissions,
		expires_at=payload.expires_at,
		env=settings.APP_ENV if settings.APP_ENV in {"dev", "prod"} else "dev",
	)
	return APIKeyCreatedResponse(
		**APIKeyResponse.model_validate(model).model_dump(),
		key=full_key,
	)


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
	key_id: uuid.UUID,
	current_user: CurrentUser,
	db: AsyncSession = Depends(get_db),
) -> None:
	model = await db.get(ApiKey, key_id)
	if model is None:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")

	if model.org_id != current_user.org_id:
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

	model.is_active = False
	await db.commit()
