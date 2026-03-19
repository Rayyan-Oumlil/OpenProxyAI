"""Auth endpoints — POST /api/v1/auth/register, /login, /logout, /me, /accept-invite."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from sqlalchemy import select

from app.dependencies import CurrentUser, get_db, get_real_ip, get_redis
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserMeResponse
from app.schemas.invite import AcceptInviteRequest
from app.services.auth_service import (
	authenticate_user,
	blocklist_token,
	create_access_token,
	create_refresh_token,
	create_user,
	enforce_auth_rate_limit,
	verify_refresh_token,
)
from app.services import invite_service

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])
http_bearer = HTTPBearer(auto_error=False)


async def _check_auth_rate_limit(ip: str, email: str, redis: Redis) -> None:
    key = f"auth:attempts:{ip}:{email}"
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, 60)  # 1-minute window
    if count > 10:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many authentication attempts. Try again in 60 seconds.",
            headers={"Retry-After": "60"},
        )


async def _reset_auth_rate_limit(ip: str, email: str, redis: Redis) -> None:
    await redis.delete(f"auth:attempts:{ip}:{email}")


@router.post("/register", response_model=TokenResponse)
async def register(
	payload: RegisterRequest,
	request: Request,
	db: AsyncSession = Depends(get_db),
	redis: Redis = Depends(get_redis),
) -> TokenResponse:
	rate_key = f"register:{payload.email.lower()}:{request.client.host if request.client else 'unknown'}"
	await enforce_auth_rate_limit(redis, rate_key)

	user = await create_user(
		db=db,
		email=payload.email,
		password=payload.password,
		name=payload.name,
		org_name=payload.org_name,
	)
	access_token = create_access_token(str(user.id), str(user.org_id), user.role)
	refresh_token = create_refresh_token(str(user.id), str(user.org_id), user.role)
	return TokenResponse(
		access_token=access_token,
		refresh_token=refresh_token,
		expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
	)


@router.post("/login", response_model=TokenResponse)
async def login(
	payload: LoginRequest,
	request: Request,
	db: AsyncSession = Depends(get_db),
	redis: Redis = Depends(get_redis),
) -> TokenResponse:
	await _check_auth_rate_limit(get_real_ip(request), payload.email, redis)

	user = await authenticate_user(db=db, email=payload.email, password=payload.password)
	await _reset_auth_rate_limit(get_real_ip(request), payload.email, redis)
	access_token = create_access_token(str(user.id), str(user.org_id), user.role)
	refresh_token = create_refresh_token(str(user.id), str(user.org_id), user.role)
	return TokenResponse(
		access_token=access_token,
		refresh_token=refresh_token,
		expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
	)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
	credentials: HTTPAuthorizationCredentials | None = Depends(http_bearer),
	db: AsyncSession = Depends(get_db),
	redis: Redis = Depends(get_redis),
) -> TokenResponse:
	if credentials is None or not credentials.credentials:
		raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")

	payload = await verify_refresh_token(credentials.credentials, redis=redis)
	user_id = payload.get("sub")
	org_id = payload.get("org_id")
	if not user_id or not org_id:
		raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

	user = await db.scalar(
		select(User).where(User.id == user_id, User.org_id == org_id)
	)
	if user is None or not user.is_active:
		raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

	access_token = create_access_token(str(user.id), str(user.org_id), role=user.role)
	new_refresh_token = create_refresh_token(str(user.id), str(user.org_id), role=user.role)
	await blocklist_token(redis, credentials.credentials)
	return TokenResponse(
		access_token=access_token,
		refresh_token=new_refresh_token,
		expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
	)


@router.post("/logout")
async def logout(
	credentials: HTTPAuthorizationCredentials | None = Depends(http_bearer),
	redis: Redis = Depends(get_redis),
) -> dict[str, str]:
	if credentials is None or not credentials.credentials:
		raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")

	await blocklist_token(redis, credentials.credentials)
	return {"status": "logged_out"}


@router.get("/me", response_model=UserMeResponse)
async def me(current_user: CurrentUser) -> UserMeResponse:
	return UserMeResponse.model_validate(current_user)


@router.post("/accept-invite", response_model=TokenResponse)
async def accept_invite(
	payload: AcceptInviteRequest,
	request: Request,
	db: AsyncSession = Depends(get_db),
	redis: Redis = Depends(get_redis),
) -> TokenResponse:
	await _check_auth_rate_limit(get_real_ip(request), payload.token, redis)

	user = await invite_service.accept_invite(
		db=db,
		token=payload.token,
		name=payload.name,
		password=payload.password,
	)
	await _reset_auth_rate_limit(get_real_ip(request), payload.token, redis)
	access_token = create_access_token(str(user.id), str(user.org_id), user.role)
	refresh_token = create_refresh_token(str(user.id), str(user.org_id), user.role)
	return TokenResponse(
		access_token=access_token,
		refresh_token=refresh_token,
		expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
	)
