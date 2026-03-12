"""Auth endpoints — POST /api/v1/auth/register, /login, /logout, /me."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import CurrentUser, get_db, get_redis
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserMeResponse
from app.services.auth_service import (
	authenticate_user,
	blocklist_token,
	create_access_token,
	create_refresh_token,
	create_user,
	enforce_auth_rate_limit,
	verify_refresh_token,
)

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])
http_bearer = HTTPBearer(auto_error=False)


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
	rate_key = f"login:{payload.email.lower()}:{request.client.host if request.client else 'unknown'}"
	await enforce_auth_rate_limit(redis, rate_key)

	user = await authenticate_user(db=db, email=payload.email, password=payload.password)
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
	redis: Redis = Depends(get_redis),
) -> TokenResponse:
	if credentials is None or not credentials.credentials:
		raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")

	payload = await verify_refresh_token(credentials.credentials, redis=redis)
	user_id = payload.get("sub")
	org_id = payload.get("org_id")
	role = payload.get("role", "developer")
	if not user_id or not org_id:
		raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

	access_token = create_access_token(user_id, org_id, role=role)
	new_refresh_token = create_refresh_token(user_id, org_id, role=role)
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
