# OpenProxyAI — Backend Backbone Scaffold

## Who You Are
You are building the backend for **OpenProxyAI**, a Zero Trust AI Gateway for regulated enterprises (finance, healthcare, government). You are a solo founder. The marketing website already exists (React + Vite + shadcn/ui in `web-app/`). Now you're building the real product.

## What To Build
Scaffold the complete **backend service skeleton** — the FastAPI application, database layer, Docker infrastructure, and core proxy endpoint. This is Week 1–2 of the MVP. Everything must compile, start, and respond to requests. No stubs that return `pass` — every endpoint must do something real, even if minimal.

---

## Project Identity

- **Repo:** `Rayyan-Oumlil/OpenProxyAI` (GitHub, public, `main` branch)
- **Product name:** OpenProxyAI
- **API key prefix:** `opai_` (format: `opai_{env}_{key_id}_{secret}{checksum}`)
- **Response header prefix:** `X-OpenProxyAI-`
- **Default port:** 8000 (backend API)
- **License:** MIT

---

## Tech Stack (Non-Negotiable)

| Layer | Technology | Why |
|---|---|---|
| Language | Python 3.11+ | Async ecosystem, LiteLLM is Python |
| Framework | FastAPI | Async, OpenAPI auto-docs, Pydantic |
| LLM Abstraction | `litellm` (pip install) | 100+ providers via one interface, cost calc built in |
| ORM | SQLAlchemy 2.0 + asyncpg | Async ORM, Alembic migrations |
| Database | PostgreSQL 16 | Users, orgs, keys, configs, request logs |
| Cache / Rate Limiting | Redis 7+ | Sliding window rate limits, budget tracking, sessions |
| Migrations | Alembic | Schema versioning |
| Serialization | orjson | Fast JSON for high-throughput proxy |
| Auth | pyjwt + secrets (API keys) | JWT for dashboard, API keys for proxy |
| HTTP Client | httpx | Async HTTP for health checks, webhooks |
| Task Scheduling | apscheduler | Materialized view refresh, cleanup jobs |
| Metrics | prometheus_client | `/metrics` endpoint |
| Testing | pytest + pytest-asyncio + httpx | Async test client |
| Containerization | Docker + Docker Compose | Postgres + Redis + API in one command |

### Key pip packages (pin these versions):
```
fastapi>=0.115.0
uvicorn[standard]>=0.30.0
litellm>=1.50.0
sqlalchemy[asyncio]>=2.0.30
asyncpg>=0.30.0
alembic>=1.13.0
redis[hiredis]>=5.0.0
pydantic>=2.7.0
pydantic-settings>=2.3.0
python-dotenv>=1.0.0
orjson>=3.10.0
httpx>=0.27.0
pyjwt[crypto]>=2.8.0
prometheus-client>=0.20.0
passlib[bcrypt]>=1.7.4
python-multipart>=0.0.9
apscheduler>=3.10.0
pytest>=8.0.0
pytest-asyncio>=0.23.0
```

---

## Directory Structure

Create exactly this structure inside `backend/`:

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app factory, middleware, startup/shutdown
│   ├── config.py                  # Pydantic Settings (env vars)
│   ├── database.py                # Async SQLAlchemy engine, session factory
│   ├── dependencies.py            # Shared Depends() — get_db, get_redis, get_current_user
│   │
│   ├── models/                    # SQLAlchemy ORM models
│   │   ├── __init__.py
│   │   ├── base.py                # DeclarativeBase + mixins (id, timestamps)
│   │   ├── organization.py        # Organization model
│   │   ├── user.py                # User model (with role enum)
│   │   ├── api_key.py             # API key model (hashed storage)
│   │   ├── llm_provider_key.py    # Provider API keys (encrypted, weighted)
│   │   └── request_log.py         # LLM request log (ClickHouse-compatible schema)
│   │
│   ├── schemas/                   # Pydantic request/response schemas
│   │   ├── __init__.py
│   │   ├── auth.py                # Login, token, API key create/response
│   │   ├── chat.py                # ChatCompletionRequest/Response (OpenAI-compatible)
│   │   ├── organization.py        # Org CRUD schemas
│   │   ├── user.py                # User CRUD schemas
│   │   ├── analytics.py           # Analytics response schemas
│   │   └── common.py              # Pagination, error response, health check
│   │
│   ├── routes/                    # API route handlers
│   │   ├── __init__.py
│   │   ├── health.py              # GET /health, GET /ready
│   │   ├── proxy.py               # POST /v1/chat/completions, /v1/embeddings
│   │   ├── auth.py                # POST /api/v1/auth/login, /register
│   │   ├── api_keys.py            # CRUD /api/v1/api-keys
│   │   ├── organizations.py       # CRUD /api/v1/organizations
│   │   ├── users.py               # CRUD /api/v1/users
│   │   └── analytics.py           # GET /api/v1/analytics/*
│   │
│   ├── services/                  # Business logic (not in routes)
│   │   ├── __init__.py
│   │   ├── llm_service.py         # LiteLLM wrapper — acompletion, cost calc, streaming
│   │   ├── auth_service.py        # API key generation/validation, JWT create/verify
│   │   ├── rate_limiter.py        # Redis sliding window — req/min, tokens/min, $/day
│   │   ├── cost_tracker.py        # Budget check, spend update, alert threshold
│   │   └── audit_logger.py        # Async background task request logging
│   │
│   ├── middleware/                 # FastAPI middleware
│   │   ├── __init__.py
│   │   ├── request_id.py          # Inject X-OpenProxyAI-Request-Id on every response
│   │   ├── timing.py              # Measure and inject X-OpenProxyAI-Latency-Ms
│   │   └── cors.py                # CORS configuration
│   │
│   └── utils/
│       ├── __init__.py
│       ├── crypto.py              # API key hashing, constant-time compare
│       └── logging.py             # Structured JSON logging setup
│
├── alembic/                       # Database migrations
│   ├── env.py
│   ├── script.py.mako
│   └── versions/                  # Migration files go here
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py                # Fixtures — test DB, test client, test API key
│   ├── test_health.py
│   ├── test_proxy.py
│   └── test_auth.py
│
├── alembic.ini
├── requirements.txt
├── Dockerfile
├── .env.example
└── README.md
```

---

## Database Schema

Design these tables. The `request_logs` schema is intentionally ClickHouse-compatible — when migrating to ClickHouse in Phase 3, the schema copies directly (same column names, same types).

```sql
-- Organizations (tenants)
CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    plan VARCHAR(50) NOT NULL DEFAULT 'free',  -- 'free', 'starter', 'growth', 'enterprise'
    settings JSONB NOT NULL DEFAULT '{}',
    budget_monthly_usd DECIMAL(10,2),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Users
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255),
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'developer',  -- 'admin', 'developer', 'viewer'
    budget_daily_usd DECIMAL(10,2),
    budget_monthly_usd DECIMAL(10,2),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- API Keys (only hashes stored, never plaintext)
CREATE TABLE api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    key_hash VARCHAR(255) NOT NULL UNIQUE,
    key_prefix VARCHAR(20) NOT NULL,  -- e.g. "opai_prod_a3f8" for display
    name VARCHAR(100),
    permissions JSONB NOT NULL DEFAULT '["proxy:llm"]',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    last_used_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Provider API keys (encrypted, weighted for rotation)
CREATE TABLE llm_provider_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    provider VARCHAR(50) NOT NULL,     -- 'openai', 'anthropic', 'azure', etc.
    key_alias VARCHAR(100) NOT NULL,   -- human-readable name
    api_key_encrypted TEXT NOT NULL,   -- encrypted at rest
    weight INTEGER NOT NULL DEFAULT 1, -- for weighted random selection
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Request logs (ClickHouse-compatible column layout)
CREATE TABLE request_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id UUID NOT NULL,          -- X-OpenProxyAI-Request-Id
    org_id UUID NOT NULL REFERENCES organizations(id),
    user_id UUID NOT NULL REFERENCES users(id),
    api_key_id UUID REFERENCES api_keys(id),
    model VARCHAR(100) NOT NULL,
    provider VARCHAR(50) NOT NULL,
    prompt_tokens INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    cost_usd DECIMAL(10,6) NOT NULL DEFAULT 0,
    latency_ms INTEGER,
    ttft_ms INTEGER,                   -- time to first token (streaming only)
    status_code INTEGER NOT NULL,      -- HTTP status; negatives: -2=timeout, -3=cancel, -4=blocked
    error_message TEXT,
    request_metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_request_logs_org_created ON request_logs(org_id, created_at DESC);
CREATE INDEX idx_request_logs_user_created ON request_logs(user_id, created_at DESC);
CREATE INDEX idx_request_logs_model ON request_logs(model, created_at DESC);

-- Materialized view for dashboard queries (refresh every 5 min)
CREATE MATERIALIZED VIEW mv_daily_spend AS
SELECT
    org_id,
    user_id,
    model,
    provider,
    DATE_TRUNC('day', created_at) AS day,
    SUM(cost_usd) AS total_cost_usd,
    SUM(prompt_tokens) AS total_prompt_tokens,
    SUM(completion_tokens) AS total_completion_tokens,
    COUNT(*) AS total_requests,
    AVG(latency_ms) AS avg_latency_ms
FROM request_logs
WHERE status_code >= 0
GROUP BY org_id, user_id, model, provider, day;
```

---

## Core Implementation Requirements

### 1. `app/main.py` — FastAPI App Factory

```python
# Must include:
# - CORS middleware (allow web-app origin)
# - Request ID middleware (UUID per request)
# - Timing middleware (latency header)
# - Structured logging (JSON format)
# - Lifespan handler: connect to DB + Redis on startup, disconnect on shutdown
# - Mount all routers with correct prefixes:
#     /health, /ready           → health router
#     /v1/chat/completions      → proxy router
#     /v1/embeddings            → proxy router
#     /api/v1/auth/*            → auth router
#     /api/v1/api-keys/*        → api_keys router
#     /api/v1/organizations/*   → organizations router
#     /api/v1/users/*           → users router
#     /api/v1/analytics/*       → analytics router
#     /metrics                  → prometheus metrics
```

### 2. `app/services/llm_service.py` — The Proxy Core

This is the heart of OpenProxyAI. Key rules:

- Use `litellm.acompletion()` for all LLM calls — never call provider SDKs directly
- Use `litellm.completion_cost(completion_response=response)` for cost — never use tiktoken
- Streaming must be non-blocking: yield chunks to client AND capture them for logging simultaneously
- After stream ends, schedule the DB log as a `BackgroundTask` — never block the response
- Track `time_to_first_token_ms` from the first streamed SSE chunk
- Implement first-chunk error detection: peek at first SSE chunk; if it's an error, return `JSONResponse(status_code=502)` instead of `StreamingResponse(status_code=200)` with error body
- Add response headers: `X-OpenProxyAI-Request-Id`, `X-OpenProxyAI-Provider`, `X-OpenProxyAI-Model`, `X-OpenProxyAI-Cost-USD`, `X-OpenProxyAI-Latency-Ms`, `X-OpenProxyAI-TTFT-Ms`

### 3. `app/services/rate_limiter.py` — Three-Dimensional Rate Limiting

Redis-based sliding window with three independent counters per org:
- `requests/minute` → ZSET with timestamps
- `tokens/minute` → string with INCR
- `dollars/day` → string with INCRBYFLOAT

Check ALL THREE before forwarding to LLM. Return 429 with `limit_type` field indicating which limit was hit. Return rate limit headers on every response:
- `X-RateLimit-Requests-Remaining`
- `X-RateLimit-Tokens-Remaining`
- `X-RateLimit-Budget-Remaining-USD`

### 4. `app/services/auth_service.py` — API Key System

- Generate keys in format: `opai_{env}_{key_id}_{secret}{checksum}`
- Hash with SHA-256 for storage (never store plaintext)
- Validate with constant-time comparison (`secrets.compare_digest`)
- Prefix stored for display (`opai_prod_a3f8...`)
- Keys expire after 90 days by default
- Support immediate revocation

### 5. `app/services/audit_logger.py` — Async Request Logging

- Log every LLM request as a background task (never block the response)
- After logging to PostgreSQL, also update the Redis budget counter: `INCRBYFLOAT rl:usd:{org_id}:{date} {cost}`
- Fields match the `request_logs` table exactly (ClickHouse-ready)

---

## Docker Compose Stack

```yaml
# docker-compose.yml at repo root
services:
  api:
    build: ./backend
    ports:
      - "8000:8000"
    env_file: ./backend/.env
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ./backend:/app  # hot reload in dev

  postgres:
    image: postgres:16-alpine
    ports:
      - "5432:5432"
    environment:
      POSTGRES_DB: openproxyai
      POSTGRES_USER: openproxyai
      POSTGRES_PASSWORD: ${DB_PASSWORD:-openproxyai_dev}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U openproxyai"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
  redis_data:
```

---

## Environment Variables (`.env.example`)

```env
# App
APP_NAME=OpenProxyAI
APP_ENV=development
DEBUG=true
SECRET_KEY=change-me-in-production-use-openssl-rand-hex-32

# Database
DATABASE_URL=postgresql+asyncpg://openproxyai:openproxyai_dev@localhost:5432/openproxyai

# Redis
REDIS_URL=redis://localhost:6379/0

# LLM Provider Keys (for local dev / testing — production uses DB-stored keys)
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
AZURE_API_KEY=
AZURE_API_BASE=

# Rate Limits (defaults)
DEFAULT_RATE_LIMIT_RPM=60
DEFAULT_RATE_LIMIT_TPM=100000
DEFAULT_BUDGET_DAILY_USD=50.0

# CORS
CORS_ORIGINS=["http://localhost:5173","http://localhost:3000"]
```

---

## Coding Conventions (Enforced)

- **PEP 8**, 4-space indent, 100 char max line length
- **Type hints** on all function signatures and return values
- **`async def`** for all route handlers and I/O-bound operations
- **Pydantic models** for all request/response bodies — never raw dict
- **`Depends()`** for auth, DB sessions, Redis connections
- **`logging`** module only — never `print()`
- **`secrets`** module for token generation — never `random`
- **`f-strings`** for formatting
- Error responses: `{"error": str, "detail": str}` with correct HTTP status
- Never expose stack traces in API responses
- Never hardcode secrets — everything from env vars via `pydantic-settings`

---

## What "Done" Looks Like

After running this prompt, you should be able to:

```bash
cd backend
cp .env.example .env
# Fill in at least OPENAI_API_KEY

# Start everything
docker compose up -d   # Postgres + Redis
alembic upgrade head   # Run migrations
uvicorn app.main:app --reload --port 8000

# Verify
curl http://localhost:8000/health               # → {"status": "healthy"}
curl http://localhost:8000/docs                  # → Swagger UI

# Register + create key
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@test.com","password":"testpass123","name":"Admin","org_name":"TestOrg"}'

# Proxy an LLM call (once you have a key)
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer opai_dev_XXXXX" \
  -H "Content-Type: application/json" \
  -d '{"model":"openai/gpt-4o-mini","messages":[{"role":"user","content":"Hello!"}]}'
```

All of the above must actually work — not return 501 or TODO.

---

## Reference Code to Study (already cloned locally)

These repos are in `references/` — read their code for patterns, don't fork them:

| Reference | What to learn | Key file to read |
|---|---|---|
| `references/litellm/` | `litellm.acompletion()`, `completion_cost()`, Router, proxy hooks | `litellm/proxy/proxy_server.py`, `litellm/router.py` |
| `references/helicone/` | Non-blocking streaming log pattern, ClickHouse schema | `worker/src/lib/HeliconeProxyRequest/ProxyForwarder.ts` |
| `references/portkey-gateway/` | Recursive fallback routing, header-based config | `src/handlers/handlerUtils.ts`, `src/handlers/retryHandler.ts` |
| `references/bifrost/` | Plugin architecture, provider routing | `core/providers/`, `plugins/` |

### External repos worth cloning for additional reference:

```bash
# FastAPI project templates
git clone https://github.com/tiangolo/full-stack-fastapi-template.git references/fastapi-template

# Production FastAPI patterns (auth, RBAC, async SQLAlchemy)
git clone https://github.com/zhanymkanov/fastapi-best-practices.git references/fastapi-best-practices
```

---

## Critical Design Decisions (Do NOT Deviate)

1. **Monolith first.** One FastAPI process. No microservices until >1000 req/sec sustained.
2. **LiteLLM is the provider layer.** Never call `openai.ChatCompletion.create()` directly. Always `litellm.acompletion()`.
3. **Cost calculation via LiteLLM.** Never use tiktoken. `litellm.completion_cost(completion_response=response)` returns a float in USD.
4. **Request logs are ClickHouse-ready.** Same column names, same types. Migration to ClickHouse in Phase 3 is a schema copy.
5. **Budget is a rate limit.** Return 429 (not 402) when daily spend exceeds cap. Budget enforcement is a rate limit, not a billing error.
6. **Stream first, log after.** Never block the SSE stream to write to the database. Capture chunks inline, write the log in a background task after `[DONE]`.
7. **Proxy metadata in headers only.** The response body must be 100% identical to what the upstream provider returns. Custom data goes in `X-OpenProxyAI-*` headers.
8. **Dashboard queries hit materialized views.** Never query `request_logs` directly for analytics. Refresh `mv_daily_spend` every 5 minutes.
