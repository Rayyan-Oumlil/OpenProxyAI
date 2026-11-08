"""Admin API for the model registry: /api/v1/model-registry (admins only).

Nothing on the request path reads the registry yet; routing starts using it in Phase 2 slice S4.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import CurrentUser, get_db
from app.models.llm_provider_key import LLMProviderKey
from app.models.model_registry import ModelRegistryEntry
from app.schemas.model_registry import ModelRegistryCreate, ModelRegistryResponse, ModelRegistryUpdate
from app.services.admin_audit_service import get_ip, log_admin_action
from app.services.data_class import data_class_rank

router = APIRouter(prefix="/api/v1/model-registry", tags=["Model Registry"])

_ADMIN_ONLY = "Only organization admins can manage the model registry"
_AUDITED = ("model_id", "provider", "provider_key_id", "max_data_class", "regions", "risk_rating", "retention_days",
            "trains_on_data", "capabilities", "cost_tier", "owner", "enabled")


def _require_admin(user) -> None:
	if user.role != "admin":
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=_ADMIN_ONLY)


def _invalid(error: str, detail: str) -> HTTPException:
	return HTTPException(status_code=422, detail={"error": error, "detail": detail})


def _snapshot(entry: ModelRegistryEntry) -> dict:
	"""The governance fields, JSON-safe, for the admin audit log."""
	data = {name: getattr(entry, name) for name in _AUDITED}
	data["provider_key_id"] = str(entry.provider_key_id) if entry.provider_key_id else None
	return data


async def _check_key(db: AsyncSession, org_id: UUID, provider: str, key_id: UUID, max_data_class: str) -> None:
	"""The linked key must be this org's, serve this provider, and be cleared for at least this data class."""
	key = await db.scalar(select(LLMProviderKey).where(LLMProviderKey.id == key_id, LLMProviderKey.org_id == org_id))
	if key is None:
		raise _invalid("invalid_provider_key", "Provider key not found in this organization")
	if key.provider != provider:
		raise _invalid("invalid_provider_key", f"Provider key serves {key.provider!r}, but this model's provider is {provider!r}")
	if data_class_rank(max_data_class) > data_class_rank(key.max_data_class):
		raise _invalid(
			"data_class_exceeds_key",
			f"A model cannot be cleared for a higher data class ({max_data_class}) than its provider key ({key.max_data_class})",
		)


async def _load(db: AsyncSession, org_id: UUID, entry_id: UUID) -> ModelRegistryEntry:
	entry = await db.get(ModelRegistryEntry, entry_id)
	if entry is None or entry.org_id != org_id:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Registry entry not found")
	return entry


@router.get("", response_model=list[ModelRegistryResponse])
async def list_entries(current_user: CurrentUser, db: AsyncSession = Depends(get_db)) -> list[ModelRegistryResponse]:
	_require_admin(current_user)
	rows = await db.scalars(
		select(ModelRegistryEntry).where(ModelRegistryEntry.org_id == current_user.org_id).order_by(ModelRegistryEntry.model_id)
	)
	return [ModelRegistryResponse.model_validate(r) for r in rows.all()]


@router.get("/{entry_id}", response_model=ModelRegistryResponse)
async def get_entry(entry_id: UUID, current_user: CurrentUser, db: AsyncSession = Depends(get_db)) -> ModelRegistryResponse:
	_require_admin(current_user)
	return ModelRegistryResponse.model_validate(await _load(db, current_user.org_id, entry_id))


@router.post("", response_model=ModelRegistryResponse, status_code=status.HTTP_201_CREATED)
async def create_entry(
	payload: ModelRegistryCreate, request: Request, current_user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> ModelRegistryResponse:
	_require_admin(current_user)
	provider = payload.model_id.split("/", 1)[0]
	if payload.provider_key_id is not None:
		await _check_key(db, current_user.org_id, provider, payload.provider_key_id, payload.max_data_class)

	entry = ModelRegistryEntry(org_id=current_user.org_id, provider=provider, **payload.model_dump())
	db.add(entry)
	try:
		await db.flush()
	except IntegrityError as exc:
		raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="That model is already in the registry") from exc
	await log_admin_action(
		db, org_id=current_user.org_id, actor_id=current_user.id, actor_email=current_user.email,
		action="model_registry.created", resource_type="model_registry", resource_id=str(entry.id),
		after=_snapshot(entry), ip_address=get_ip(request),
	)
	await db.commit()
	await db.refresh(entry)
	return ModelRegistryResponse.model_validate(entry)


@router.patch("/{entry_id}", response_model=ModelRegistryResponse)
async def update_entry(
	entry_id: UUID, payload: ModelRegistryUpdate, request: Request, current_user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> ModelRegistryResponse:
	_require_admin(current_user)
	updates = payload.model_dump(exclude_unset=True)
	if not updates:
		raise _invalid("empty_update", "Provide at least one field to change")
	entry = await _load(db, current_user.org_id, entry_id)

	key_id = updates.get("provider_key_id", entry.provider_key_id)
	if key_id is not None and ("provider_key_id" in updates or "max_data_class" in updates):
		await _check_key(db, current_user.org_id, entry.provider, key_id, updates.get("max_data_class", entry.max_data_class))

	before = _snapshot(entry)
	for name, value in updates.items():
		setattr(entry, name, value)
	await log_admin_action(
		db, org_id=current_user.org_id, actor_id=current_user.id, actor_email=current_user.email,
		action="model_registry.updated", resource_type="model_registry", resource_id=str(entry.id),
		before=before, after=_snapshot(entry), ip_address=get_ip(request),
	)
	await db.commit()
	await db.refresh(entry)
	return ModelRegistryResponse.model_validate(entry)


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_entry(entry_id: UUID, request: Request, current_user: CurrentUser, db: AsyncSession = Depends(get_db)) -> None:
	_require_admin(current_user)
	entry = await _load(db, current_user.org_id, entry_id)
	await log_admin_action(
		db, org_id=current_user.org_id, actor_id=current_user.id, actor_email=current_user.email,
		action="model_registry.deleted", resource_type="model_registry", resource_id=str(entry.id),
		before=_snapshot(entry), ip_address=get_ip(request),
	)
	await db.delete(entry)
	await db.commit()
