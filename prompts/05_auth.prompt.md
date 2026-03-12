# Step 5 — Authentication

> **Reference:** Follow `prompts/01_backend_backbone.prompt.md` for the API key format, RBAC roles, and security requirements. Steps 2–4 are complete — all tables exist in Postgres.

---

## Context

The database schema is in place. Now build the auth layer: API key generation/validation, user registration, and the JWT-based session token for the dashboard. This is what protects every endpoint going forward.

---

## What To Build This Session

### 1. `backend/app/utils/crypto.py`

All cryptographic primitives — no business logic here:

```python
# API key generation
def generate_api_key(env: str = "dev") -> tuple[str, str, str]:
    """Returns (full_key, key_hash, key_prefix)"""
    # Format: opai_{env}_{key_id}_{secret}{checksum}
    # key_id: secrets.token_hex(4)  → 8 chars
    # secret: secrets.token_hex(16) → 32 chars
    # checksum: sha256(raw)[:4]
    # key_hash: sha256(full_key).hexdigest()
    # key_prefix: first 18 chars of full key for display

def verify_api_key(api_key: str, stored_hash: str) -> bool:
    """Constant-time comparison — never use == directly"""

def hash_password(password: str) -> str:
    """bcrypt via passlib"""

def verify_password(plain: str, hashed: str) -> bool:
    """bcrypt verify"""
```

### 2. `backend/app/services/auth_service.py`

Business logic wrapping crypto + DB:

```python
async def create_api_key(
    db: AsyncSession,
    user_id: uuid.UUID,
    org_id: uuid.UUID,
    name: str,
    permissions: list[str],
    expires_at: datetime | None,
    env: str = "dev",
) -> tuple[APIKey, str]:
    """Creates DB record. Returns (model, full_key). Full key shown once — never stored."""

async def validate_api_key(
    db: AsyncSession,
    redis: Redis,
    api_key: str,
) -> APIKey:
    """
    1. Look up by key_hash in DB
    2. Check is_active and not expired
    3. Update last_used_at (async, non-blocking)
    4. Return APIKey with user + org loaded
    Raises HTTP 401 on any failure — never reveal why (timing-safe)
    """

async def create_user(db: AsyncSession, email: str, password: str, name: str, org_name: str) -> User:
    """Register flow: create org → create admin user → return user"""

async def authenticate_user(db: AsyncSession, email: str, password: str) -> User:
    """Verify email + password. Return user or raise 401."""

def create_access_token(user_id: str, org_id: str, role: str) -> str:
    """JWT with 24h expiry. Payload: sub, org_id, role, iat, exp."""

async def verify_access_token(token: str) -> dict:
    """Decode + verify JWT. Raise 401 if invalid/expired."""
```

### 3. `backend/app/schemas/auth.py`

```python
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str  # min 8 chars, validated
    name: str
    org_name: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds

class APIKeyCreateRequest(BaseModel):
    name: str
    permissions: list[str] = ["proxy:llm"]
    expires_at: datetime | None = None

class APIKeyResponse(BaseModel):
    id: uuid.UUID
    name: str
    key_prefix: str
    permissions: list[str]
    is_active: bool
    expires_at: datetime | None
    created_at: datetime

class APIKeyCreatedResponse(APIKeyResponse):
    key: str  # Only returned on creation, never again
    warning: str = "Store this key securely. It will not be shown again."
```

### 4. `backend/app/routes/auth.py`

```
POST /api/v1/auth/register   → RegisterRequest → TokenResponse + user info
POST /api/v1/auth/login      → LoginRequest → TokenResponse
POST /api/v1/auth/logout     → invalidate token (Redis blocklist)
GET  /api/v1/auth/me         → current user info (requires auth)
```

### 5. `backend/app/routes/api_keys.py`

```
GET    /api/v1/api-keys          → list keys for current user (never shows full key)
POST   /api/v1/api-keys          → create key → returns APIKeyCreatedResponse (key shown once)
DELETE /api/v1/api-keys/{key_id} → revoke (set is_active=False, immediate effect)
```

### 6. `backend/app/dependencies.py`

```python
async def get_db() -> AsyncGenerator[AsyncSession, None]: ...
async def get_redis() -> AsyncGenerator[Redis, None]: ...

async def get_current_user_from_jwt(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User: ...

async def get_current_user_from_api_key(
    api_key: str = Header(alias="Authorization"),  # "Bearer opai_..."
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> tuple[User, APIKey]: ...

# Convenience aliases
CurrentUser = Annotated[User, Depends(get_current_user_from_jwt)]
ProxyAuth = Annotated[tuple[User, APIKey], Depends(get_current_user_from_api_key)]
```

---

## Security Rules (Non-Negotiable)

- Never store plaintext API keys — only `key_hash`
- Never log API keys, passwords, or tokens — not even at DEBUG level
- Use `secrets.compare_digest` for all hash comparisons
- JWT secret comes from `settings.SECRET_KEY` — never hardcoded
- Registration does not require email verification in MVP (add in Phase 2)
- Failed auth always returns 401 with a generic message — never reveal which field was wrong

---

## Done When

```bash
# Register (creates org + admin user + returns JWT)
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@test.com","password":"testpass123","name":"Admin","org_name":"TestOrg"}'
# → {"access_token": "eyJ...", "token_type": "bearer", "expires_in": 86400}

# Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@test.com","password":"testpass123"}'
# → {"access_token": "eyJ..."}

# Create an API key (use JWT from above)
curl -X POST http://localhost:8000/api/v1/api-keys \
  -H "Authorization: Bearer eyJ..." \
  -H "Content-Type: application/json" \
  -d '{"name":"My Dev Key"}'
# → {"key": "opai_dev_...", "warning": "Store this key securely..."}

# List keys (key field absent — never shown again)
curl http://localhost:8000/api/v1/api-keys \
  -H "Authorization: Bearer eyJ..."
# → [{"id": "...", "key_prefix": "opai_dev_...", ...}]  ← no "key" field

# Verify bad key returns 401
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer opai_dev_FAKEFAKEFAKE"
# → 401 Unauthorized
```
