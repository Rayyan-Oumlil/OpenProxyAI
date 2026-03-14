"""LLM provider key management — CRUD for org-scoped provider API keys."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import CurrentUser, get_db
from app.models.llm_provider_key import LLMProviderKey
from app.schemas.provider_key import ProviderKeyCreateRequest, ProviderKeyResponse, ProviderKeyUpdateRequest
from app.services.crypto_service import decrypt, encrypt

router = APIRouter(prefix="/api/v1/provider-keys", tags=["Provider Keys"])

_ADMIN_ONLY = "Only admins can manage provider keys"


def _mask_key(raw_key: str) -> str:
	"""Return the first 8 characters followed by '…' to indicate truncation."""
	return raw_key[:8] + "…"


def _to_response(key: LLMProviderKey, raw_key: str) -> ProviderKeyResponse:
	return ProviderKeyResponse(
		id=key.id,
		provider=key.provider,
		key_alias=key.key_alias,
		key_prefix=_mask_key(raw_key),
		weight=key.weight,
		is_active=key.is_active,
		created_at=key.created_at,
	)


@router.get("", response_model=list[ProviderKeyResponse])
async def list_provider_keys(
	current_user: CurrentUser,
	db: AsyncSession = Depends(get_db),
) -> list[ProviderKeyResponse]:
	rows = await db.scalars(
		select(LLMProviderKey)
		.where(LLMProviderKey.org_id == current_user.org_id)
		.order_by(LLMProviderKey.created_at)
	)
	result: list[ProviderKeyResponse] = []
	for key in rows:
		try:
			raw = decrypt(key.api_key_encrypted)
		except ValueError:
			raw = "????????"  # decryption failed — show placeholder
		result.append(_to_response(key, raw))
	return result


@router.post("", response_model=ProviderKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_provider_key(
	payload: ProviderKeyCreateRequest,
	current_user: CurrentUser,
	db: AsyncSession = Depends(get_db),
) -> ProviderKeyResponse:
	if current_user.role != "admin":
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=_ADMIN_ONLY)

	key = LLMProviderKey(
		org_id=current_user.org_id,
		provider=payload.provider,
		key_alias=payload.key_alias,
		api_key_encrypted=encrypt(payload.api_key),
		weight=payload.weight,
		is_active=True,
	)
	db.add(key)
	await db.commit()
	await db.refresh(key)
	return _to_response(key, payload.api_key)


@router.patch("/{key_id}", response_model=ProviderKeyResponse)
async def update_provider_key(
	key_id: UUID,
	payload: ProviderKeyUpdateRequest,
	current_user: CurrentUser,
	db: AsyncSession = Depends(get_db),
) -> ProviderKeyResponse:
	if current_user.role != "admin":
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=_ADMIN_ONLY)

	key = await db.scalar(
		select(LLMProviderKey).where(
			LLMProviderKey.id == key_id,
			LLMProviderKey.org_id == current_user.org_id,
		)
	)
	if key is None:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider key not found")

	updates = payload.model_dump(exclude_unset=True)
	for field_name, field_value in updates.items():
		setattr(key, field_name, field_value)

	await db.commit()
	await db.refresh(key)

	try:
		raw = decrypt(key.api_key_encrypted)
	except ValueError:
		raw = "????????"
	return _to_response(key, raw)


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_provider_key(
	key_id: UUID,
	current_user: CurrentUser,
	db: AsyncSession = Depends(get_db),
) -> None:
	if current_user.role != "admin":
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=_ADMIN_ONLY)

	key = await db.scalar(
		select(LLMProviderKey).where(
			LLMProviderKey.id == key_id,
			LLMProviderKey.org_id == current_user.org_id,
		)
	)
	if key is None:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider key not found")

	await db.delete(key)
	await db.commit()
