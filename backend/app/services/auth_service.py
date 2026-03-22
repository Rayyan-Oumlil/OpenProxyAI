"""API key generation/validation, JWT create/verify, user auth."""

import hashlib
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import HTTPException, status
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models.api_key import ApiKey
from app.models.organization import Organization
from app.models.user import User
from app.utils.crypto import (
	generate_api_key,
	hash_password,
	verify_api_key,
	verify_password,
)

INVALID_CREDENTIALS_ERROR = HTTPException(
	status_code=status.HTTP_401_UNAUTHORIZED,
	detail="Invalid credentials",
)


def _slugify_org_name(name: str) -> str:
	cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in name).strip("-")
	return cleaned or f"org-{uuid.uuid4().hex[:8]}"


def _utc_now() -> datetime:
	return datetime.now(UTC)


async def enforce_auth_rate_limit(redis: Redis, key: str) -> None:
	"""Apply fixed-window auth rate limiting using Redis."""
	bucket_key = f"auth:limit:{key}"
	attempts = await redis.incr(bucket_key)
	if attempts == 1:
		await redis.expire(bucket_key, settings.AUTH_RATE_LIMIT_WINDOW_SECONDS)
	if attempts > settings.AUTH_RATE_LIMIT_MAX_ATTEMPTS:
		raise HTTPException(
			status_code=status.HTTP_429_TOO_MANY_REQUESTS,
			detail="Too many authentication attempts",
		)


async def create_user(
	db: AsyncSession,
	email: str,
	password: str,
	name: str,
	org_name: str,
) -> User:
	"""Register flow: create organization and admin user."""
	normalized_email = email.lower().strip()

	existing_user = await db.scalar(select(User).where(User.email == normalized_email))
	if existing_user is not None:
		raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists")

	base_slug = _slugify_org_name(org_name)
	org_slug = base_slug
	counter = 1
	while await db.scalar(select(Organization).where(Organization.slug == org_slug)) is not None:
		counter += 1
		org_slug = f"{base_slug}-{counter}"

	organization = Organization(name=org_name, slug=org_slug)
	db.add(organization)
	await db.flush()

	user = User(
		org_id=organization.id,
		email=normalized_email,
		name=name,
		password_hash=hash_password(password),
		role="admin",
		is_active=True,
	)
	db.add(user)
	await db.commit()
	await db.refresh(user)
	return user


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User:
	"""Authenticate by email/password with generic 401 errors."""
	normalized_email = email.lower().strip()
	user = await db.scalar(select(User).where(User.email == normalized_email))
	if user is None:
		raise INVALID_CREDENTIALS_ERROR
	if not user.is_active:
		raise INVALID_CREDENTIALS_ERROR
	if not verify_password(password, user.password_hash):
		raise INVALID_CREDENTIALS_ERROR

	user.last_login_at = _utc_now().replace(tzinfo=None)
	await db.commit()
	await db.refresh(user)
	return user


def create_access_token(user_id: str, org_id: str, role: str) -> str:
	now = _utc_now()
	exp = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
	payload = {
		"sub": user_id,
		"org_id": org_id,
		"role": role,
		"type": "access",
		"jti": uuid.uuid4().hex,
		"iat": int(now.timestamp()),
		"exp": int(exp.timestamp()),
	}
	return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def create_refresh_token(user_id: str, org_id: str, role: str) -> str:
	now = _utc_now()
	exp = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
	payload = {
		"sub": user_id,
		"org_id": org_id,
		"role": role,
		"type": "refresh",
		"jti": uuid.uuid4().hex,
		"iat": int(now.timestamp()),
		"exp": int(exp.timestamp()),
	}
	return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


async def verify_access_token(token: str, redis: Redis | None = None) -> dict:
	"""Verify JWT signature, expiry, token type, and optional blocklist."""
	try:
		payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
	except jwt.ExpiredSignatureError as exc:
		raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired") from exc
	except jwt.InvalidTokenError as exc:
		raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

	if payload.get("type") != "access":
		raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

	if redis is not None:
		jti = payload.get("jti")
		if jti and await redis.exists(f"auth:blocklist:{jti}"):
			raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token revoked")
	return payload


async def verify_refresh_token(token: str, redis: Redis | None = None) -> dict:
	"""Verify refresh token and optional blocklist status."""
	try:
		payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
	except jwt.ExpiredSignatureError as exc:
		raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired") from exc
	except jwt.InvalidTokenError as exc:
		raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

	if payload.get("type") != "refresh":
		raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

	if redis is not None:
		jti = payload.get("jti")
		if jti and await redis.exists(f"auth:blocklist:{jti}"):
			raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token revoked")
	return payload


async def blocklist_token(redis: Redis, token: str) -> None:
	"""Blocklist an issued JWT using its jti until natural expiry."""
	try:
		payload = jwt.decode(
			token,
			settings.SECRET_KEY,
			algorithms=["HS256"],
			options={"verify_exp": False},
		)
	except jwt.InvalidTokenError:
		return

	jti = payload.get("jti")
	exp = payload.get("exp")
	if not jti or not exp:
		return

	ttl = max(int(exp - _utc_now().timestamp()), 1)
	await redis.setex(f"auth:blocklist:{jti}", ttl, "1")


async def create_api_key(
	db: AsyncSession,
	user_id: uuid.UUID,
	org_id: uuid.UUID,
	name: str,
	permissions: list[str],
	expires_at: datetime | None,
	env: str = "dev",
	team_id: uuid.UUID | None = None,
) -> tuple[ApiKey, str]:
	"""Create key model and return one-time display full key."""
	from sqlalchemy import text

	full_key, key_hash, key_prefix = generate_api_key(env=env)

	model = ApiKey(
		user_id=user_id,
		org_id=org_id,
		key_hash=key_hash,
		key_prefix=key_prefix,
		name=name,
		permissions=permissions,
		expires_at=expires_at,
		is_active=True,
		team_id=team_id,
	)
	db.add(model)
	await db.flush()  # get model.id for lookup insert
	await db.execute(
		text("INSERT INTO api_key_lookup (key_hash, org_id, api_key_id) VALUES (:key_hash, :org_id, :api_key_id)"),
		{"key_hash": key_hash, "org_id": str(org_id), "api_key_id": str(model.id)},
	)
	await db.commit()
	await db.refresh(model)
	return model, full_key


async def validate_api_key(db: AsyncSession, redis: Redis, api_key: str) -> ApiKey:
	"""Validate API key and return hydrated model with user+org relationships.

	Uses api_key_lookup (no RLS) for key_hash -> org_id, then loads ApiKey from
	api_keys with RLS enforced. No RLS bypass.
	"""
	from sqlalchemy import text

	from app.database import set_session_org_id

	key_hash = hashlib.sha256(api_key.encode("utf-8")).hexdigest()
	row = await db.execute(
		text("SELECT org_id, api_key_id FROM api_key_lookup WHERE key_hash = :key_hash"),
		{"key_hash": key_hash},
	)
	row_data = row.mappings().first()
	if row_data is None:
		raise INVALID_CREDENTIALS_ERROR

	org_id_val = row_data["org_id"]
	if isinstance(org_id_val, str):
		org_id_val = uuid.UUID(org_id_val)
	await set_session_org_id(db, org_id_val)

	model = await db.scalar(
		select(ApiKey)
		.where(ApiKey.id == row_data["api_key_id"])
		.options(selectinload(ApiKey.user), selectinload(ApiKey.organization)),
	)
	if model is None:
		raise INVALID_CREDENTIALS_ERROR

	if not verify_api_key(api_key, model.key_hash):
		raise INVALID_CREDENTIALS_ERROR

	if not model.is_active:
		raise INVALID_CREDENTIALS_ERROR

	if model.expires_at is not None and model.expires_at < _utc_now().replace(tzinfo=None):
		raise INVALID_CREDENTIALS_ERROR

	if model.user is None or not model.user.is_active:
		raise INVALID_CREDENTIALS_ERROR

	if model.user.org_id != model.org_id:
		raise INVALID_CREDENTIALS_ERROR

	model.last_used_at = _utc_now().replace(tzinfo=None)
	await db.commit()
	await db.refresh(model)
	return model

