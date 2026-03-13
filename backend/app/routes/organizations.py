"""Organization settings endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import CurrentUser, get_db
from app.models.organization import Organization
from app.schemas.organization import OrganizationResponse, OrganizationUpdateRequest

router = APIRouter(prefix="/api/v1/organizations", tags=["Organizations"])


@router.get("/current", response_model=OrganizationResponse)
async def get_current_organization(
	current_user: CurrentUser,
	db: AsyncSession = Depends(get_db),
) -> OrganizationResponse:
	model = await db.scalar(select(Organization).where(Organization.id == current_user.org_id))
	if model is None:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
	return OrganizationResponse.model_validate(model)


@router.patch("/current", response_model=OrganizationResponse)
async def update_current_organization(
	payload: OrganizationUpdateRequest,
	current_user: CurrentUser,
	db: AsyncSession = Depends(get_db),
) -> OrganizationResponse:
	if current_user.role != "admin":
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

	model = await db.scalar(select(Organization).where(Organization.id == current_user.org_id))
	if model is None:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

	updates = payload.model_dump(exclude_unset=True)
	if updates.get("is_active") is False:
		raise HTTPException(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail="Organization deactivation is not allowed from this endpoint",
		)

	settings_patch = updates.pop("settings", None)

	for field_name, field_value in updates.items():
		setattr(model, field_name, field_value)

	if settings_patch is not None:
		merged_settings = dict(model.settings or {})
		merged_settings.update(settings_patch)
		model.settings = merged_settings

	await db.commit()
	await db.refresh(model)
	return OrganizationResponse.model_validate(model)
