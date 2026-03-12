# Step 4 — Database Models & First Migration

> **Reference:** Follow `prompts/01_backend_backbone.prompt.md` for the full SQL schema. Steps 2–3 are complete — the app starts and `/health` returns 200.

---

## Context

FastAPI is running. Now define all SQLAlchemy ORM models and create the first Alembic migration that produces the complete database schema from the master spec.

---

## What To Build This Session

### 1. `backend/app/models/base.py`

`DeclarativeBase` subclass with two mixins:
- `UUIDPrimaryKeyMixin` — `id: Mapped[uuid.UUID]` with `server_default=text("gen_random_uuid()")`
- `TimestampMixin` — `created_at`, `updated_at` as `Mapped[datetime]` with `server_default=func.now()` and `onupdate=func.now()`

### 2. `backend/app/models/organization.py`

`Organization` model. Fields exactly as in the master schema:
- `name`, `slug` (unique), `plan` (default `'free'`)
- `settings: Mapped[dict]` as JSONB
- `budget_monthly_usd: Mapped[Decimal | None]`
- `is_active: Mapped[bool]` default True
- Relationship: `users`, `api_keys`, `request_logs`

### 3. `backend/app/models/user.py`

`User` model:
- `org_id` FK → `organizations.id` ON DELETE CASCADE
- `email` unique, `name`, `password_hash`
- `role: Mapped[str]` default `'developer'` — validate against `('admin', 'developer', 'viewer')`
- `budget_daily_usd`, `budget_monthly_usd` as `Decimal | None`
- `is_active`, `last_login_at`
- Relationship: `organization`, `api_keys`, `request_logs`

### 4. `backend/app/models/api_key.py`

`APIKey` model:
- `user_id` FK → `users.id` ON DELETE CASCADE
- `org_id` FK → `organizations.id` ON DELETE CASCADE
- `key_hash` (unique, indexed) — SHA-256 of full key, never plaintext
- `key_prefix` — first ~16 chars for display (e.g. `opai_dev_a3f8k2m9`)
- `name`, `permissions: Mapped[list]` as JSONB default `["proxy:llm"]`
- `is_active`, `last_used_at`, `expires_at`

### 5. `backend/app/models/llm_provider_key.py`

`LLMProviderKey` model:
- `org_id` FK → `organizations.id` ON DELETE CASCADE
- `provider` (e.g. `'openai'`, `'anthropic'`, `'azure'`)
- `key_alias` — human name (e.g. `"OpenAI Production"`)
- `api_key_encrypted` — Fernet-encrypted at rest
- `weight: Mapped[int]` default 1 — for weighted random selection
- `is_active`

### 6. `backend/app/models/request_log.py`

`RequestLog` model — this is the ClickHouse-compatible hot table:
- `request_id: Mapped[uuid.UUID]` — the `X-OpenProxyAI-Request-Id` value
- `org_id` FK, `user_id` FK, `api_key_id` FK (nullable)
- `model`, `provider`
- `prompt_tokens`, `completion_tokens`, `total_tokens` — all `int`
- `cost_usd: Mapped[Decimal]` — 6 decimal places
- `latency_ms: Mapped[int | None]`
- `ttft_ms: Mapped[int | None]` — time to first token
- `status_code: Mapped[int]` — HTTP status; negatives: -2=timeout, -3=cancel, -4=blocked
- `error_message: Mapped[str | None]`
- `request_metadata: Mapped[dict]` as JSONB default `{}`
- Indexes: `(org_id, created_at DESC)`, `(user_id, created_at DESC)`, `(model, created_at DESC)`

### 7. `backend/app/models/__init__.py`

Export all models so Alembic's `env.py` can import them via `from app.models import *`.

### 8. First Alembic migration

Run `alembic revision --autogenerate -m "initial_schema"`.

Then manually review and enhance the generated file to add:
- The `mv_daily_spend` materialized view (raw SQL via `op.execute()`)
- The three composite indexes on `request_logs`
- An initial `CREATE EXTENSION IF NOT EXISTS "pgcrypto"` for `gen_random_uuid()`

---

## Done When

```bash
cd backend

# Run the migration
alembic upgrade head

# Verify all tables exist
docker compose exec postgres psql -U openproxyai -c "\dt"
# → organizations, users, api_keys, llm_provider_keys, request_logs, alembic_version

# Verify indexes
docker compose exec postgres psql -U openproxyai -c "\di"
# → shows the 3 composite indexes on request_logs

# Verify materialized view
docker compose exec postgres psql -U openproxyai -c "\dm"
# → mv_daily_spend

# App still starts (no import errors from models)
uvicorn app.main:app --reload --port 8000
curl http://localhost:8000/ready
# → {"status":"ready","postgres":"ok","redis":"ok"}

# Roll back and forward works cleanly
alembic downgrade base
alembic upgrade head
```
