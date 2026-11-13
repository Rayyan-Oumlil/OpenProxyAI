# OpenProxyAI — Architecture Rules

## What This Is
Enterprise LLM gateway / AI control plane. Sits between applications and LLM providers (OpenAI, Anthropic, Azure, Mistral, etc.) and MCP tool servers. Single API key, full audit trail, policy enforcement, data-class routing, cost control, compliance.

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
| Deploy | Docker Compose (local and demo), Helm chart (self-hosted Kubernetes) |

## Dev Commands

```bash
# Start everything
docker compose up

# Seeded demo (fake LLM, demo org, sample traffic) and its smoke test; see docs/getting-started/demo.md
docker compose -f docker-compose.demo.yml up --build
scripts/smoke.sh

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
  alembic/versions/  # 57 migration files
admin-console/
  src/
    api/             # Typed API client
    components/      # Shared UI components
    features/        # Feature-scoped components
    state/           # AuthContext and global state
    lib/             # Utilities (jwt.ts, etc.)
deploy/              # Helm chart, cluster issuer
docs/  docs-site/   # Operator docs; public site and blog
scripts/             # Demo smoke tests (smoke.sh, smoke_*.py)
web-app/             # Marketing website
sdk/                 # Python + TypeScript SDKs
```

## Request Pipeline (every request, in order)
```
Auth → request_gate.admit (policy, classify, route, team check, rate limit; refusals) → Cache Check → LiteLLM → Cache Store → Log (async)
```
`request_gate.admit` is the one admission step shared by chat and every other endpoint (embeddings, rerank, images, audio, Responses, batch lines, conversation turns, eval runs). Chat keeps its own experiments, cache, templates, taint and streaming around it. `tests/test_chat_parity.py` and `scripts/mutate_gate.py` guard that they stay identical.

## Key Files
| File | Purpose |
|---|---|
| `backend/app/routes/proxy.py` | Core proxy endpoints (`/v1/chat/completions`, `/v1/embeddings`, `/v1/models`) |
| `backend/app/services/llm_service.py` | LiteLLM wrapper, provider key rotation, experiments, streaming |
| `backend/app/services/request_gate.py` | The shared admission step (policy, classification, routing, refusals, rate limits) |
| `backend/app/services/modality_pipeline.py` + `modalities.py` | Embeddings, rerank, images, audio, Responses through the gate |
| `backend/app/services/routing_service.py` | Authorized-set routing from the model registry |
| `backend/app/services/model_runner.py` | One governed call path for eval runs, batches and conversations |
| `backend/app/services/policy_service.py` | Hook system (`before_request` / `after_request` guardrails), `evaluate_tool_call` for MCP |
| `backend/app/routes/mcp.py` + `services/mcp_gateway.py` | MCP gateway (`POST /v1/mcp`): aggregation, tool policy, audit |
| `backend/app/services/cache_service.py` | 3-tier cache (L1 TTLCache, L2 Redis, L3 pgvector semantic) |
| `backend/app/services/audit_logger.py` | Fire-and-forget async logging (never blocks response) |
| `backend/app/services/rate_limiter.py` | Token-based rate limiting (requests/min + tokens/min + dollars/day) |
| `backend/app/database.py` | `set_session_org_id()` — must be called before any RLS-protected query |
| `backend/app/config.py` | `PLAN_FEATURES` dict, `AIRGAP_MODE` flag, all env-based settings |
| `backend/app/main.py` | Lifespan (DB + Redis init), APScheduler jobs, middleware stack |

## Migrations
Alembic, 57 revisions in `backend/alembic/versions/`. List the chain with `cd backend && alembic history`; the head is a merge (`v7w8x9y0z1a2`). Two branches must never both end in a head: if `alembic heads` shows more than one, add a merge revision. See `docs/architecture/database-schema.md`.

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

### Governance Rules (no silent anything)
- **One admission step.** A new endpoint that sends anything to a model joins `request_gate.admit` and the guardrail suite in `tests/test_modalities_pipeline.py`. Grep every `acompletion`, `aembedding` and outbound `httpx` call when adding a guard: a path that bypasses it is the usual bug.
- **Every fallback comes from the authorized set.** Routing returns the requested model if authorized, otherwise nothing. No silent fallback, no experiment-variant swap that skips the check. An empty set is a 446 with zero upstream calls.
- **Fail closed on unknown shapes.** Walk whole structures, not one field; an unknown value counts as the most restrictive; use `fullmatch` for allowlist regexes.
- **Long-lived work re-checks per unit.** Streams, batches, realtime sessions and conversations re-apply budget, owner status and policy per unit of work, not once at the start.
- **Outbound calls use the guarded client.** Provider endpoints, MCP servers, webhooks and Vault go through `guarded_http_client` (validated address, no redirects, TLS against the hostname). A request body never chooses an endpoint or credentials.
- **Refusals carry two things:** a stable `reason_code` and a one-sentence `explanation` that names no rule detail (`refusal_explanations.py`).
- **Never price at zero.** An unpriced model or a broken stream is charged from its tokens or a flat estimate, and audited.
- **Admin visibility without content.** Admin pages show metadata, counts and cost, never message or file contents.

### Provider Key Rotation
Multiple provider keys per provider — weighted random rotation in `llm_service.py`. Keys stored in `llm_provider_keys` table with `data_region` for data residency filtering.

## Custom HTTP Status Codes
| Code | Meaning |
|---|---|
| 402 | Pre-flight estimate exceeds the remaining daily budget (org or user); plan limit exceeded |
| 403 | Real authorization failure (admin required, not a team member, missing permission). Never a policy block |
| 429 | Rate limit hit, or a user's daily budget already spent (`user_budget_daily_usd`) |
| 446 | Blocked by policy (including `no_authorized_model` when routing is enforced): request guardrails (PII, keyword, model allowlist) and response guardrails; also the audit status of refused MCP tool calls. Constant: `POLICY_BLOCK_STATUS` |

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
- `ALLOW_INTERNAL_PROVIDER_ENDPOINTS` — lets a provider key's `api_base` be private or plain http (self-hosted only; off for multi-tenant)
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
- **Never** put a test-fixture password literal in a commit (generate it per run); the secret scan covers history
- **Never** claim "WCAG compliant": say "automated WCAG 2.1 A/AA checks pass"
