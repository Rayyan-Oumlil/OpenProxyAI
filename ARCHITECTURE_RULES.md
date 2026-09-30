# OpenProxyAI — Project Context

## What This Is
Enterprise LLM proxy / AI control plane. Sits between org users and LLM providers (OpenAI, Anthropic, Azure, Mistral, etc.). Single API key, full audit trail, policy enforcement, cost control, compliance.

## Stack
| Layer | Technology |
|---|---|
| Proxy engine | FastAPI + Python (async) |
| LLM abstraction | LiteLLM (`acompletion` / `aembedding` — library call, NOT a forked proxy server) |
| Database | PostgreSQL 16 + pgvector (port 5434 locally to avoid clash with system Postgres on 5432) |
| Cache / Rate limit | Redis 7 |
| Analytics | ClickHouse 24 (sidecar — may fail silently) |
| Observability | Langfuse, Prometheus (sidecars — may fail silently) |
| Admin UI | React + Vite + TypeScript + shadcn/ui (`admin-console/`) |
| Deploy | Docker Compose (local), Helm chart (prod) |

## Dev Commands

```bash
# Start everything
docker compose up

# Backend only (hot reload against Docker DB+Redis)
cd backend && uvicorn app.main:app --reload --port 8000

# Run migrations
cd backend && alembic upgrade head

# New migration
cd backend && alembic revision --autogenerate -m "description"

# Backend tests
cd backend && pytest

# Admin console
cd admin-console && npm run dev   # http://localhost:5173
cd admin-console && npm run build
cd admin-console && npm run typecheck
```

## Directory Structure
```
backend/
  app/
    main.py          # App factory, lifespan, scheduler, middleware
    config.py        # Settings (env vars, PLAN_FEATURES, AIRGAP_MODE)
    database.py      # AsyncSessionLocal, engine, set_session_org_id()
    dependencies.py  # ProxyAuth, get_db, get_redis, get_request_id
    routes/          # One file per resource (proxy.py is the core)
    services/        # Business logic (llm_service.py is the core)
    models/          # SQLAlchemy ORM models
    schemas/         # Pydantic request/response schemas
    middleware/      # cors.py, request_id.py, timing.py
  alembic/versions/  # 27 migration files
admin-console/
  src/
    api/             # Typed API client
    components/      # Shared UI components
    features/        # Feature-scoped components
    state/           # AuthContext and global state
    lib/             # Utilities (jwt.ts, etc.)
deploy/              # Helm chart, GitHub Actions CI/CD
sdk/                 # Python + TypeScript SDKs
```

## Request Pipeline (every request, in order)
```
Auth → Rate Limit → Policy (hooks) → Cache Check → LiteLLM → Cache Store → Log (async)
```

## Key Files
| File | Purpose |
|---|---|
| `backend/app/routes/proxy.py` | Core proxy endpoints (`/v1/chat/completions`, `/v1/embeddings`, `/v1/models`) |
| `backend/app/services/llm_service.py` | LiteLLM wrapper, provider key rotation, experiments, streaming |
| `backend/app/services/policy_service.py` | Hook system (`before_request` / `after_request` guardrails) |
| `backend/app/services/cache_service.py` | 3-tier cache (L1 TTLCache, L2 Redis, L3 pgvector semantic) |
| `backend/app/services/audit_logger.py` | Fire-and-forget async logging (never blocks response) |
| `backend/app/services/rate_limiter.py` | Token-based rate limiting (requests/min + tokens/min + dollars/day) |
| `backend/app/database.py` | `set_session_org_id()` — must be called before any RLS-protected query |
| `backend/app/config.py` | `PLAN_FEATURES` dict, `AIRGAP_MODE` flag, all env-based settings |
| `backend/app/main.py` | Lifespan (DB + Redis init), APScheduler jobs, middleware stack |

## Migration Chain (27 files; regenerate with `cd backend && alembic history`)
```
54c0ed90559e → b3e8d87fd2f1 → c4f9a12e8b7d → d4e7f12a9c3b → e5f8a23b4c1d
→ f1a9c3e7d5b2 → a2b3c4d5e6f7 → a3b4c5d6e7f8 → b1c2d3e4f5a6 → c3d4e5f6a7b8
→ e6f7a8b9c0d1 → d4e5f6a7b8c9 → e6f7a34b9d0c (branchpoint)
    ├─ f7a8b9c0d1e2 → g8b9c0d1e2f3 → h9c0d1e2f3a4 → i0d1e2f3a4b5 → j1e2f3a4b5c6
    └─ f8a9b0c1d2e3 (RLS policies)
→ k2f3a4b5c6d7 (merge) → l3g4h5i6j7k8 → m4h5i6j7k8l9 → n5i6j7k8l9m0
→ o6j7k8l9m0n1 → q8l9m0n1o2p3 → r9m0n1o2p3q4 → s0n1o2p3q4r5 (head)
```

## Architecture Rules (Critical)

### RLS — Row Level Security
- Request-path connections run as `app_user` (`SET ROLE` on connect, `DB_APP_ROLE`), so RLS applies even when the login role is a superuser
- Every `AsyncSession` that touches a protected table **must** call `await set_session_org_id(session, org_id)` first
- Background writers use `org_scoped_session(org_id)` (opens a session with the org already set)
- `SystemSessionLocal` keeps the login role and bypasses RLS — only for jobs that must read across orgs (health checks, key rotation, adaptive sampling). Never in request handling
- `request_logs` and `admin_audit_logs` are append-only for `app_user` (only `request_logs.archived_at` is updatable)
- Fire-and-forget background tasks **must** create their own `AsyncSession` — the request-scoped session is closed after the response
- The materialized view `mv_daily_spend` is refreshed via `refresh_mv_daily_spend_definer()` (SECURITY DEFINER) to bypass RLS

### Sidecar Pattern
These services **may** fail silently — swallow their exceptions, never propagate:
- ClickHouse (analytics dual-write)
- Langfuse (observability)
- Prometheus (metrics)
- Webhooks (delivery)

Core services (DB, Redis, LiteLLM, policy, rate limiting) **must** fail hard.

### Async Logging
`audit_logger.log_request()` is always fire-and-forget via `BackgroundTasks`. Never `await` it inline — it would block the response.

### LiteLLM Usage
Use `litellm.acompletion()` and `litellm.aembedding()` as library calls. Do NOT replicate their proxy server pattern.

### Provider Key Rotation
Multiple provider keys per provider — weighted random rotation in `llm_service.py`. Keys stored in `llm_provider_keys` table with `data_region` for data residency filtering.

## Custom HTTP Status Codes
| Code | Meaning |
|---|---|
| 402 | Budget exceeded |
| 429 | Rate limit hit |
| 446 | Guardrail / policy block |

## Background Jobs (APScheduler)
| Job | Interval | Notes |
|---|---|---|
| `refresh_mv_daily_spend` | 5 min | Uses SECURITY DEFINER to bypass RLS |
| `archive_old_logs` | 1 hour | Respects per-plan `audit_retention_days` |
| `retry_failed_webhooks` | 5 min | Exponential backoff, max 3 attempts |
| `hourly_metered_stripe_sync` | 1 hour | Disabled in AIRGAP_MODE |
| `flush_request_logs_batch` | Configurable | Only if `BATCH_SPEND_ENABLED` |
| `provider_health_check` | 5 min | Only if `PROVIDER_HEALTH_CHECK_ENABLED` |
| `adaptive_lb_sampling` | Configurable | Only if `ADAPTIVE_LB_ENABLED` |

## Environment Flags
- `AIRGAP_MODE=true` — disables Langfuse, ClickHouse, spend reports, Stripe metered sync
- `BATCH_SPEND_ENABLED` — enables batched request log flushing
- `PROMETHEUS_ENABLED` — mounts `/metrics` router
- `PROVIDER_HEALTH_CHECK_ENABLED` — enables provider health polling
- `ADAPTIVE_LB_ENABLED` — enables adaptive load balancer sampling

## What to Never Do
- **Never** skip `set_session_org_id()` before touching an RLS-protected table — skip it and RLS silently returns no rows (data loss) or, if the connection bypasses RLS, exposes other orgs' rows
- **Never** block the response path with logging — always use `BackgroundTasks`
- **Never** raise exceptions from sidecar services (ClickHouse, Langfuse, Prometheus, webhooks)
- **Never** mutate a request-scoped DB session in a background task — create a new one
- **Never** fork or replicate LiteLLM's proxy server — use it as a library only
- **Never** add a new route without wiring it in `main.py` via `app.include_router()`
- **Never** change a migration file after it has been applied — always create a new one
