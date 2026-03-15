# Backend Overview — OpenProxyAI

> Last updated: 2026-03-15 (Phase 2 + Observability complete)
> Stack: FastAPI · PostgreSQL · Redis · LiteLLM · Alembic · Docker Compose

---

## Architecture at a Glance

Every request flows through a fixed pipeline:

```
Client → Auth → Policy → Rate Limit → LiteLLM (provider) → Async Log
```

The proxy runs as a single FastAPI async process. Logging is fire-and-forget (background task) so it never adds latency to the response path. Redis handles rate limiting and policy config caching. PostgreSQL is the source of truth for everything else.

---

## What Is Deployed

### Proxy Engine

**`POST /v1/chat/completions`** and **`POST /v1/embeddings`**

The core gateway. Authenticates the request via API key, runs policy evaluation, checks rate limits, selects a provider key (weighted random from DB or env fallback), forwards to LiteLLM `acompletion` / `aembedding`, and returns the response with cost/latency headers.

- Streaming is fully supported — TTFT is measured from the first chunk
- Every response includes `X-OpenProxyAI-*` headers (request ID, provider, model, cost, latency)
- Blocked requests return HTTP 403 with `policy_violation` error body
- Rate-limited requests return HTTP 429 with `Retry-After` and `X-RateLimit-*` headers
- Provider timeouts return HTTP 504; provider errors return HTTP 502

---

### Authentication

**`/api/v1/auth`**

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/register` | Creates a new user + organization, returns access + refresh tokens |
| `POST` | `/login` | Email/password login, returns tokens |
| `POST` | `/refresh` | Rotates refresh token (old token is blocklisted in Redis) |
| `POST` | `/logout` | Blocklists the current access token |
| `GET` | `/me` | Returns authenticated user profile |

- Passwords are hashed with bcrypt
- Access tokens are short-lived JWTs; refresh tokens are longer-lived JWTs
- Token blocklist lives in Redis (key expires with the token TTL)
- Login and register endpoints are rate-limited per email + IP

---

### API Key Management

**`/api/v1/api-keys`**

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | List all API keys for the authenticated user |
| `POST` | `/` | Create a new API key (full key shown once) |
| `DELETE` | `/{key_id}` | Revoke a key (soft delete — sets `is_active = false`) |

- Keys are stored as SHA-256 hashes; the plaintext is never persisted
- Keys carry a permissions array (default: `["proxy:llm"]`) and an optional expiry

---

### User Management

**`/api/v1/users`**

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | List all users in the organization |
| `GET` | `/{user_id}` | Get a single user |
| `PATCH` | `/{user_id}` | Update role or active status (admin only) |

- Roles: `admin`, `developer`, `viewer`
- Guards prevent an admin from removing the last active admin in an org
- Per-user daily budget (`budget_daily_usd`) is enforceable via rate limiter

---

### Organization Settings

**`/api/v1/organizations`**

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/current` | Get org profile (name, slug, plan, budget) |
| `PATCH` | `/current` | Update org name or settings (admin only) |
| `GET` | `/current/policy` | Get active policy configuration |
| `PATCH` | `/current/policy` | Merge-update policy configuration (admin only) |

Policy config is stored as a JSONB field in `org.settings.policy` and cached in Redis with a 60-second TTL.

---

### Provider Key Management

**`/api/v1/provider-keys`**

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | List provider keys (masked — first 8 chars only) |
| `POST` | `/` | Add a new provider key (admin only) |
| `PATCH` | `/{key_id}` | Update alias, weight, or active status (admin only) |
| `DELETE` | `/{key_id}` | Remove a provider key (admin only) |

- Provider keys are encrypted at rest using AES-GCM (`crypto_service`)
- Multiple keys per provider are supported with weighted random selection
- Falls back to env vars (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `AZURE_API_KEY`) if no DB keys are active

---

### Analytics

**`/api/v1/analytics`**

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/overview` | Aggregated usage metrics for `period_days` (1–90) |
| `GET` | `/logs` | Paginated request log (up to 200/page), filterable by model, status, policy action/reason |
| `GET` | `/logs/{log_id}` | Full detail for a single request |
| `GET` | `/policy` | Policy event summary (allow / log_only / block counts, top reasons) |
| `GET` | `/policy/export` | Export policy events as JSON or CSV, with optional date range and action filters |
| `POST` | `/reconcile` | Compare provider usage export against gateway aggregates and return per-row deltas |

- The `mv_daily_spend` materialized view is refreshed every 5 minutes by APScheduler
- Export responses larger than the result cap set `X-Result-Truncated: true` header

---

### Health

**`GET /health`** — returns DB and Redis connectivity status. Used for liveness and readiness probes.

---

## Core Services

| Service | File | Responsibility |
|---------|------|---------------|
| `LLMService` | `services/llm_service.py` | LiteLLM wrapper — streaming, cost calc, async logging, provider key selection |
| `PolicyService` | `services/policy_service.py` | Pure evaluation — model allowlist, blocked keywords, regex PII (email, SSN, CC) |
| `PolicyStore` | `services/policy_service.py` | Redis → DB → env fallback for loading/saving policy config |
| `RateLimiterService` | `services/rate_limiter.py` | Sliding-window RPM, TPM, org daily budget, per-user daily budget (all in Redis) |
| `AuthService` | `services/auth_service.py` | User creation, bcrypt verify, JWT issue/verify, token blocklist |
| `AnalyticsService` | `services/analytics_service.py` | Aggregated queries, log pagination, policy summary, reconciliation |
| `AuditLogger` | `services/audit_logger.py` | Fire-and-forget background write to `request_logs` |
| `CostTracker` | `services/cost_tracker.py` | Wraps LiteLLM cost calculation, increments Redis spend counters |
| `CryptoService` | `services/crypto_service.py` | AES-GCM encrypt/decrypt for provider keys at rest |
| `PlanService` | `services/plan_service.py` | Plan feature gates — HTTP 402 when org exceeds user/key/feature limits |
| `InviteService` | `services/invite_service.py` | Invite token creation, validation, and accept-invite user provisioning |
| `SSOService` | `services/sso_service.py` | OIDC auth-code flow, nonce validation, JIT user provisioning |
| `LangfuseService` | `services/langfuse_service.py` | Optional Langfuse trace forwarding — fire-and-forget, off when keys not set |
| `MetricsService` | `services/metrics_service.py` | Prometheus counter/histogram recording — called synchronously from `AuditLogger` |
| `WebhookService` | `services/webhook_service.py` | HMAC-signed outbound webhook delivery with retry and delivery logging |

---

## Database Schema

### Tables

| Table | Purpose |
|-------|---------|
| `organizations` | Multi-tenant isolation boundary. Holds plan, monthly budget, and JSONB settings (including policy config) |
| `users` | Users scoped to an org. Roles: admin / developer / viewer. Optional per-user daily/monthly budget |
| `api_keys` | Hashed proxy keys issued to users. Carry permissions, optional expiry |
| `llm_provider_keys` | Encrypted provider API keys per org. Weighted for load balancing |
| `request_logs` | Immutable audit trail — every proxy request is logged here. Row-Level Security blocks UPDATE/DELETE. `archived_at` column for soft archival by retention policy. |
| `user_invites` | Pending invites. Token stored as SHA-256 hash, 7-day TTL, accepted_at marks completion |
| `sso_connections` | Generic OIDC connector per org. `client_secret` AES-GCM encrypted. Supports Auth0, Okta, Azure AD, Google Workspace |
| `webhook_deliveries` | Audit trail for outbound webhook attempts — status (delivered/failed), http_status, attempt_count |

### Materialized View

`mv_daily_spend` — pre-aggregated daily cost/token totals per org/user/model/provider. Refreshed every 5 minutes concurrently (no table lock).

### Indexes

- `idx_request_logs_org_created` — primary analytics query path
- `idx_request_logs_user_created` — user-level drill-downs
- `idx_request_logs_model` — model breakdown queries
- `idx_request_logs_archived_at` — archival cron and analytics filtering
- `ix_api_keys_key_hash` — unique, used on every proxy auth lookup
- GIN index on `request_logs.request_metadata` (migration `c4f9a12e8b7d`) — JSONB policy field queries
- Unique index on `mv_daily_spend` (migration `b3e8d87fd2f1`) — enables `REFRESH CONCURRENTLY`
- `idx_webhook_deliveries_org_created`, `idx_webhook_deliveries_status` — delivery log queries

### Migration Chain

`54c0ed90559e` → `c4f9a12e8b7d` → `b3e8d87fd2f1` → `d4e7f12a9c3b` → `e5f8a23b4c1d` → `f1a9c3e7d5b2` → `a2b3c4d5e6f7`

---

## Middleware

Applied in order on every request:

1. **CORS** — configurable origins
2. **RequestId** — injects `X-Request-ID` (UUID) if not provided by caller
3. **Timing** — records total request duration in `X-Response-Time-Ms`

---

## Infrastructure

| Component | Technology |
|-----------|-----------|
| Framework | FastAPI (async) |
| Database | PostgreSQL + SQLAlchemy (async) + Alembic |
| Cache / Rate Limit | Redis (aioredis) |
| LLM abstraction | LiteLLM (`acompletion`, `aembedding`) |
| Scheduler | APScheduler (async, in-process) |
| Auth | Custom JWT (python-jose) + bcrypt |
| Encryption | AES-GCM via cryptography library |
| Containerization | Docker Compose (backend + postgres + redis) |

---

## Test Coverage

| Test file | Coverage area |
|-----------|--------------|
| `test_auth.py` | Register, login, refresh, logout, token expiry |
| `test_proxy.py` | Chat completions, embeddings, policy blocking, rate limiting |
| `test_policy.py` | PolicyService unit tests — all evaluation paths |
| `test_policy_config.py` | Policy CRUD via API (get/patch, enforce mode, PII, keywords) |
| `test_analytics.py` | Overview, logs pagination, log detail, policy summary, export, reconcile |
| `test_management.py` | Users CRUD, organizations CRUD, last-admin guard |
| `test_provider_keys.py` | Provider key CRUD, encryption, weight selection |
| `test_rate_limiter.py` | RPM, TPM, org budget, user budget limit enforcement |
| `test_health.py` | Health endpoint |
| `test_proxy_live_integration.py` | Live integration test against real providers |

---

## What We Are Currently Developing

- **Admin console** (`admin-console/`) — React + Vite + Tailwind SPA. Charts dashboard, request log viewer, provider key management, policy config editor, user/role management, and SDK onboarding modal are all shipped.

---

## Phase 2 — Shipped ✓

### Enterprise Auth & Multi-tenancy

- **Invite system** — `POST /api/v1/invites` generates invite URLs; `POST /api/v1/auth/accept-invite` creates the user. Token stored as SHA-256 hash, 7-day TTL. (`routes/invites.py`, `services/invite_service.py`, migration `d4e7f12a9c3b`)
- **Per-org plan enforcement** — Free / Starter / Growth / Enterprise feature matrix gates max users, max API keys, SSO, PII detection, and audit retention. HTTP 402 on limit exceeded. (`services/plan_service.py`, `config.PLAN_FEATURES`)
- **OIDC/SSO** — Generic OIDC connector per org (Auth0, Okta, Azure AD, Google Workspace). Full authorization-code flow with nonce validation, JIT user provisioning, and encrypted `client_secret` at rest. (`routes/sso.py`, `services/sso_service.py`, migration `e5f8a23b4c1d`)
- **Audit log immutability** — PostgreSQL RLS on `request_logs` blocks UPDATE/DELETE for the app role. Hourly cron archives logs older than the plan retention window (`archived_at` column). Analytics queries filter archived logs by default; `?include_archived=true` exposes them for admin export. (migration `f1a9c3e7d5b2`)

### SDK & Developer Experience

- **Python SDK** (`sdk/python/`) — `openproxy-ai` on PyPI. Sync + async httpx client, SSE streaming, `GatewayMeta` on every response, custom exceptions (`PolicyViolationError`, `RateLimitError`, `BudgetExceededError`), auto-retry with exponential backoff. OpenAI-compatible interface.
- **TypeScript SDK** (`sdk/typescript/`) — `openproxy-ai` on npm. Fetch-based, ESM + CJS dual output, typed `AsyncIterable` streaming, full error hierarchy, Vitest + msw tests.
- **SDK onboarding flow** — 3-step modal in admin console: create first API key → copy once → code snippet (Python / TypeScript / cURL). Auto-shown to new users with no keys; suppressed via `localStorage` flag after dismiss.

---

## Phase 2 — Observability — Shipped ✓

- **Langfuse integration** — `services/langfuse_service.py` — fire-and-forget trace per request (trace_id = request_id, generation span with tokens/cost/latency). Enable by setting `LANGFUSE_SECRET_KEY` + `LANGFUSE_PUBLIC_KEY`. Off by default.
- **Prometheus metrics endpoint** — `GET /metrics` — 7 metric series: `openproxy_requests_total`, `openproxy_request_latency_seconds`, `openproxy_ttft_seconds`, `openproxy_tokens_total`, `openproxy_cost_usd_total`, `openproxy_policy_violations_total`, `openproxy_rate_limit_hits_total`. Enable via `PROMETHEUS_ENABLED=true` (default on).
- **Webhook delivery** — `services/webhook_service.py` — HMAC-SHA256 signed payloads, 3-retry exponential backoff, delivery logged to `webhook_deliveries` table. Events: `policy.violation` (HTTP 403 blocks) and `budget.alert` (org budget ≥ 80%). Config via `PATCH /api/v1/organizations/current/webhooks` (admin only).

---

## What Should Be Built Next

### Phase 3 — Scale & Compliance

- **ClickHouse** for request logs — replace or supplement PostgreSQL for high-volume analytics queries (>1M req/day)
- **Microsoft Presidio** — replace the current regex PII detection with a proper NLP-based entity recognizer
- **Streaming billing** — real-time cost tracking per token during streaming (currently tracked at stream end)
- **Per-model rate limits** — separate RPM/TPM buckets per model, not just per org
- **Kubernetes deployment** — Helm chart, horizontal pod autoscaling, health probes
- **SOC 2 / HIPAA controls** — encryption-at-rest audit, access log retention policy, data residency config

### Phase 3 — Advanced Gateway Features

- **Response guardrails** — policy hooks on the `after_request` path (not just `before_request`)
- **Prompt injection detection** — detect adversarial inputs before forwarding to provider
- **Cost anomaly alerts** — flag unusual spend spikes per user or per model
- **Model routing rules** — route to specific provider keys based on model, user group, or time-of-day
- **Caching layer** — semantic cache for identical or near-identical prompts (reduce cost and latency)
