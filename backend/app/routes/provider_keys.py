"""LLM provider key management — CRUD for org-scoped provider API keys."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import CurrentUser, get_db
from app.models.llm_provider_key import LLMProviderKey
from app.schemas.provider_key import ProviderKeyCreateRequest, ProviderKeyResponse, ProviderKeyUpdateRequest
from app.services.admin_audit_service import get_ip, log_admin_action, serialize_provider_key
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
		region=key.region,
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
	request: Request,
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
		region=payload.region,
	)
	db.add(key)

	await log_admin_action(
		db,
		org_id=current_user.org_id,
		actor_id=current_user.id,
		actor_email=current_user.email,
		action="provider_key.created",
		resource_type="provider_key",
		resource_id=key.key_alias,
		before=None,
		after=serialize_provider_key(key),
		ip_address=get_ip(request),
	)

	await db.commit()
	await db.refresh(key)
	return _to_response(key, payload.api_key)


@router.patch("/{key_id}", response_model=ProviderKeyResponse)
async def update_provider_key(
	key_id: UUID,
	payload: ProviderKeyUpdateRequest,
	request: Request,
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

	before = serialize_provider_key(key)

	updates = payload.model_dump(exclude_unset=True)
	for field_name, field_value in updates.items():
		setattr(key, field_name, field_value)

	after = serialize_provider_key(key)

	await log_admin_action(
		db,
		org_id=current_user.org_id,
		actor_id=current_user.id,
		actor_email=current_user.email,
		action="provider_key.updated",
		resource_type="provider_key",
		resource_id=str(key_id),
		before=before,
		after=after,
		ip_address=get_ip(request),
	)

	await db.commit()
	await db.refresh(key)

	try:
		raw = decrypt(key.api_key_encrypted)
	except ValueError:
		raw = "????????"
	return _to_response(key, raw)


@router.post("/{key_id}/rotate")
async def rotate_provider_key(
	key_id: UUID,
	request: Request,
	current_user: CurrentUser,
	db: AsyncSession = Depends(get_db),
) -> dict:
	"""Re-encrypt the stored provider key with a fresh Fernet token (zero-downtime rotation).

	The plaintext API key is unchanged — only the ciphertext is replaced.
	This satisfies CC9.2 vendor risk management (key rotation) under SOC 2.
	"""
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

	plaintext = decrypt(key.api_key_encrypted)
	key.api_key_encrypted = encrypt(plaintext)

	key_prefix = key.key_alias[:8] if len(key.key_alias) >= 8 else key.key_alias
	await log_admin_action(
		db,
		org_id=current_user.org_id,
		actor_id=current_user.id,
		actor_email=current_user.email,
		action="provider_key.rotated",
		resource_type="provider_key",
		resource_id=str(key_id),
		before={"key_prefix": key_prefix},
		after={"key_prefix": key_prefix},
		ip_address=get_ip(request),
	)

	await db.commit()
	return {"rotated": True, "key_id": str(key_id)}


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_provider_key(
	key_id: UUID,
	request: Request,
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

	before = serialize_provider_key(key)

	await log_admin_action(
		db,
		org_id=current_user.org_id,
		actor_id=current_user.id,
		actor_email=current_user.email,
		action="provider_key.deleted",
		resource_type="provider_key",
		resource_id=str(key_id),
		before=before,
		after=None,
		ip_address=get_ip(request),
	)

	await db.delete(key)
	await db.commit()
