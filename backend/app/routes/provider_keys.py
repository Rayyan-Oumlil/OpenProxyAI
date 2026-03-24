"""LLM provider key management — CRUD for org-scoped provider API keys."""

import time
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import CurrentUser, get_db, get_redis
from app.models.llm_provider_key import LLMProviderKey
from app.schemas.provider_key import ProviderKeyCreateRequest, ProviderKeyResponse, ProviderKeyUpdateRequest
from app.services.admin_audit_service import get_ip, log_admin_action, serialize_provider_key
from app.services.adaptive_sampling_service import get_error_rate, get_latency_p99
from app.services.circuit_breaker_service import get_open_until, is_enabled as circuit_breaker_enabled
from app.services.crypto_service import decrypt, encrypt
from app.services.provider_key_service import rotate_key as rotate_key_service

router = APIRouter(prefix="/api/v1/provider-keys", tags=["Provider Keys"])

_ADMIN_ONLY = "Only admins can manage provider keys"


def _mask_key(raw_key: str) -> str:
	"""Return the first 8 characters followed by '…' to indicate truncation."""
	return raw_key[:8] + "…"


def _to_response(
	key: LLMProviderKey,
	raw_key: str,
	*,
	circuit_open_until: float | None = None,
	latency_p99_ms: float | None = None,
	error_rate: float | None = None,
	effective_weight: int | None = None,
) -> ProviderKeyResponse:
	return ProviderKeyResponse(
		id=key.id,
		provider=key.provider,
		key_alias=key.key_alias,
		key_prefix=_mask_key(raw_key),
		weight=key.weight,
		is_active=key.is_active,
		region=key.region,
		created_at=key.created_at,
		circuit_open_until=circuit_open_until,
		latency_p99_ms=latency_p99_ms,
		error_rate=error_rate,
		effective_weight=effective_weight,
	)


def _compute_effective_weight(
	base_weight: int,
	p99: float | None,
	error_rate: float | None,
) -> int:
	"""Mirror llm_service formula: health = 1/(1 + p99/10000 + err*10); effective = max(floor, health) * base."""
	if p99 is None and error_rate is None:
		return base_weight
	floor = float(getattr(settings, "ADAPTIVE_LB_WEIGHT_FLOOR", 0.1))
	lat_penalty = (p99 or 0) / 10000
	err_penalty = (error_rate or 0) * 10
	health = 1.0 / (1.0 + lat_penalty + err_penalty)
	effective = max(floor, health) * base_weight
	return max(1, int(effective))


@router.get("", response_model=list[ProviderKeyResponse])
async def list_provider_keys(
	current_user: CurrentUser,
	db: AsyncSession = Depends(get_db),
	redis=Depends(get_redis),
) -> list[ProviderKeyResponse]:
	if current_user.role != "admin":
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=_ADMIN_ONLY)
	rows = await db.scalars(
		select(LLMProviderKey)
		.where(LLMProviderKey.org_id == current_user.org_id)
		.order_by(LLMProviderKey.created_at)
	)
	adaptive = getattr(settings, "ADAPTIVE_LB_ENABLED", False) and redis is not None
	result: list[ProviderKeyResponse] = []
	for key in rows:
		try:
			raw = decrypt(key.api_key_encrypted)
		except ValueError:
			raw = "????????"  # decryption failed — show placeholder
		circuit_until = None
		if circuit_breaker_enabled() and redis:
			open_until = await get_open_until(redis, key.id)
			if open_until is not None and open_until > 0 and time.time() < open_until:
				circuit_until = open_until
		latency_p99_ms = None
		error_rate = None
		effective_weight = None
		if adaptive and redis:
			p99 = await get_latency_p99(redis, key.id)
			err = await get_error_rate(redis, key.id)
			if p99 is not None or err is not None:
				latency_p99_ms = p99
				error_rate = err
				effective_weight = _compute_effective_weight(key.weight, p99, err)
		result.append(
			_to_response(
				key,
				raw,
				circuit_open_until=circuit_until,
				latency_p99_ms=latency_p99_ms,
				error_rate=error_rate,
				effective_weight=effective_weight,
			),
		)
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
	redis=Depends(get_redis),
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
	circuit_until = None
	if circuit_breaker_enabled() and redis:
		open_until = await get_open_until(redis, key.id)
		if open_until is not None and open_until > 0 and time.time() < open_until:
			circuit_until = open_until
	latency_p99_ms = None
	error_rate = None
	effective_weight = None
	if getattr(settings, "ADAPTIVE_LB_ENABLED", False) and redis:
		p99 = await get_latency_p99(redis, key.id)
		err = await get_error_rate(redis, key.id)
		if p99 is not None or err is not None:
			latency_p99_ms = p99
			error_rate = err
			effective_weight = _compute_effective_weight(key.weight, p99, err)
	return _to_response(
		key,
		raw,
		circuit_open_until=circuit_until,
		latency_p99_ms=latency_p99_ms,
		error_rate=error_rate,
		effective_weight=effective_weight,
	)


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

	rotated = await rotate_key_service(
		db,
		key_id,
		current_user.org_id,
		actor_id=current_user.id,
		actor_email=current_user.email,
		ip_address=get_ip(request),
	)
	if not rotated:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider key not found")

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
