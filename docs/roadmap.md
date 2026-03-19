# OpenProxyAI — Roadmap

> Last reviewed: 2026-03-19
> Current state: Phase 6 nearly complete. 462 tests passing across 40 test files. Stripe billing shipped. Public deployment is the only remaining gate to first revenue.

---

## What is production-ready today

Everything below is shipped, tested, and working:

### Core proxy
- `/v1/chat/completions` and `/v1/embeddings` — streaming and non-streaming
- LiteLLM multi-provider (OpenAI, Anthropic, Azure, Mistral, and 100+ others)
- Provider fallback chains — automatic retry on 429/5xx, never on 4xx client errors
- Weighted provider key rotation with per-model pattern matching
- Streaming peek — errors surface as proper HTTP codes, never buried in SSE

### Auth & access
- API key auth (SHA-256 hash, plaintext never stored)
- RBAC — admin / developer / viewer roles
- OIDC/SSO — per-org generic OIDC connector, auth-code flow, JIT provisioning
- Invite system — SHA-256 tokens, 7-day TTL
- Auth brute-force protection — Redis-backed IP+email counter, 429 after N attempts
- JWT silent refresh — proactive token renewal 5 min before expiry, transparent to user
- Admin action audit log — every policy change, key rotation, user invite/deactivate logged (SOC 2 CC6)

### Rate limiting & cost
- RPM, TPM, per-user daily budget — all enforced in Redis
- O(1) rate limiter — fixed-window counter (not sorted-set sliding window)
- Per-model rate limits via policy config
- Cost anomaly detection — baseline multiplier alert
- Budget alert webhooks with guaranteed delivery (retry job with exponential backoff)
- Request tagging — `x-openproxy-labels` header for departmental chargebacks
- Budget forecasting — projected month-end spend card on dashboard from daily average

### Policy engine
- Enforcement modes: `off` / `log_only` / `enforce`
- Model allowlist, keyword blocking, regex-based PII detection
- ML-based prompt injection detection — `protectai/deberta-v3-base-prompt-injection`, fail-open
- Response guardrails — keyword + PII checks on LLM output before returning to client
- Response PII redaction — replaces detected PII with `[REDACTED]` in-stream
- Per-org policy config stored in PostgreSQL, 60s Redis cache, instant invalidation on save
- Policy event analytics — `GET /api/v1/analytics/policy/export` (JSON + CSV)

### Observability
- Async audit log — immutable PostgreSQL `request_logs`, plan-based retention + archival cron
- ClickHouse dual-write — fire-and-forget sidecar for OLAP analytics at scale
- Langfuse tracing — optional, fire-and-forget (v4 SDK, OTel transport)
- Prometheus metrics — `/metrics` endpoint, ServiceMonitor for Kubernetes
- p95/p99 latency in analytics — `percentile_cont()` in PostgreSQL
- Materialized view `mv_daily_spend` — refreshed every 5 minutes for sub-second dashboard queries

### Compliance & reporting
- Compliance report CSV export — policy violations, user access, key rotation, budget vs actual (`GET /api/v1/analytics/compliance/export`)
- CSV formula injection prevention — cell values prefixed to block spreadsheet exploits
- Admin-only authorization on all export endpoints
- SOC 2 CC6/CC7 evidence artifacts — immutable audit trail + exportable compliance report

### Admin console
- Dashboard (cost, tokens, request volume, latency percentiles, projected month-end spend)
- Log viewer with request detail and label filtering
- Policy editor — all fields configurable per org without code changes
- Team management — invite, deactivate, role change
- Provider key management — create, rotate, delete (audit-logged)
- Organization settings — plan info, webhook config, integrations
- Onboarding modal — 3-step first-run key creation
- Self-serve signup — public registration at `/signup`, no manual DB setup needed
- Compliance export button — one-click CSV download from dashboard

### Infrastructure
- Docker Compose for local development
- Kubernetes Helm chart — HPA, PDB, ServiceMonitor, init-container migrations
- Frontend Docker build — multi-stage nginx image with SPA fallback
- GitHub Actions CI/CD — test → build → push GHCR → helm upgrade on every push to main
- Exact-match Redis cache with configurable TTL (off by default)

### SDKs
- Python SDK — `openproxy-ai` on PyPI, sync + async, streaming, typed errors
- TypeScript SDK — `openproxy-ai` on npm, ESM + CJS, typed streaming

### Test coverage (420 tests, 39 files)
- Proxy & LLM: proxy, llm_service, provider fallback, model routing, model rate limits
- Auth & SSO: auth, SSO, API keys, users, auth rate limit
- Policy & guardrails: policy, policy config, policy store, response guardrails, request labels
- Compliance & audit: audit logger, admin audit, audit immutability, SOC 2 controls
- Cost & analytics: cost tracker, cost anomaly, analytics, plan enforcement
- Webhooks: webhook delivery, webhook retry
- Observability: Langfuse, Prometheus metrics, ClickHouse
- Security: crypto service, prompt injection, Presidio
- Infrastructure: health, management, cache service, invites, organizations, provider keys

---

## Known gaps (intentional, not bugs)

### Gap — Cache is exact-match, not semantic
**File:** `backend/app/services/cache_service.py`

SHA-256 hash of `(model, messages, temperature)` → Redis lookup. Only hits on byte-for-byte
identical requests. Good for CI/eval loops. **Semantic caching** is a Phase 8 item.

### Gap — Presidio NLP is disabled by default
**File:** `backend/requirements.txt`

`presidio-analyzer` is commented out due to +800MB image size. Regex PII detection is active.
To enable: uncomment `presidio-analyzer`, rebuild the Docker image. Phase 7 item.

---

## What's still needed before first paying customer

| Item | Status | Where |
|---|---|---|
| **Stripe billing** | ✓ Shipped | — |
| **Public deployment** | Code complete; waiting on DOKS cluster + DNS setup | `plans/public-deployment.md` |

---

## Phase 6 — Go-to-market *(nearly complete)*

### 6.1 — Stripe billing ✓ Shipped
- DB schema: `stripe_customer_id`, `stripe_subscription_id`, `stripe_subscription_status` ✓
- `stripe_events` idempotency table with atomic `ON CONFLICT DO NOTHING` idempotency ✓
- `billing_service.py` — checkout, portal, webhook handler with `SELECT FOR UPDATE` ✓
- Routes: `POST /api/v1/billing/checkout`, `/portal`, `/webhook` ✓
- `BillingPage.tsx` — plan cards, upgrade flow, post-checkout polling, portal redirect ✓
- Plan override guard (409 when Stripe-managed) ✓
- 15 billing tests — all webhook event types, idempotency, unpaid checkout guard ✓

### 6.2 — Self-serve signup ✓ Shipped
- `/signup` route in admin console
- `signup()` in AuthContext calling `POST /api/v1/auth/register`
- Login page links to signup

### 6.3 — Public deployment *(one manual step away from live)*
- Frontend Dockerfile + nginx SPA config ✓
- Helm frontend templates + `values.prod.yaml` ✓
- `cert-manager` ClusterIssuer ✓
- GitHub Actions CI/CD (test → build → push → deploy) ✓
- Remaining: DOKS cluster, managed DB/Redis, DNS, GitHub secrets → `plans/public-deployment.md`

### 6.4 — Security hardening ✓ Shipped
- CSV formula injection prevention in all export endpoints ✓
- Admin-only authorization on compliance and policy export endpoints ✓
- Webhook secret excluded from API responses ✓
- Auth rate limiting on login and invite acceptance ✓

### 6.5 — Compliance & analytics ✓ Shipped
- Compliance report CSV export — policy violations, user access, key rotation, budget ✓
- Policy event analytics endpoint (JSON + CSV) with date range and action filters ✓
- Budget forecasting — projected month-end spend computed from daily average ✓
- Projected cost card on admin dashboard ✓

### 6.6 — Test hardening ✓ Shipped
- 39 test files covering all routes, services, and edge cases ✓
- 420 tests passing (up from 294) ✓
- New test files: api_keys, organizations, users, audit_logger, cost_tracker, crypto_service, llm_service ✓

---

## Phase 7 — Enterprise hardening *(next)*

### 7.1 — Presidio PII detection (real NLP)
Uncomment `presidio-analyzer`, rebuild image. Optional Helm sub-chart (`presidio.enabled: true`).
Minimal code change — the service already supports both regex and NLP backends.

### 7.2 — Real-time cost dashboard (WebSocket)
Replace polling dashboard with WebSocket feed for live spend visibility. Reduces dashboard
refresh latency from 30s to sub-second for SOC operations centers.

### 7.3 — Usage-based billing metering
Track per-request cost against Stripe usage records for consumption-based pricing. Requires
Stripe metered billing setup and a periodic sync job.

### 7.4 — Multi-tenant data isolation audit
Verify all SQL queries enforce `org_id` filtering. Add PostgreSQL RLS policies as defense-in-depth.
Generate evidence report for SOC 2 CC6.3 auditors.

### 7.5 — Advanced webhook features
Dead-letter queue for permanently failed deliveries. Webhook event replay from admin console.
Delivery status dashboard with success/failure rates per org.

---

## Phase 8 — Advanced gateway

### 8.1 — Semantic caching
Embed requests, cosine-match against vector store, return cached response above threshold.
Reduces cost 20–40% for repetitive workloads like chatbots.

### 8.2 — Voice endpoint
`POST /v1/audio/transcriptions` — Whisper with same auth/policy/audit pipeline as chat.

### 8.3 — Model A/B testing
Route configurable % of traffic to model variants. Aggregate latency/cost/quality per variant.

### 8.4 — Multi-region routing
Wire `data_region` on organizations to a routing layer for GDPR data residency compliance.

---

## Phase 9 — Moat features

### 9.1 — WASM plugin system
Customer-written `before_request` / `after_request` hooks compiled to WASM.

### 9.2 — On-premise distribution
Air-gapped Helm chart + license key validation for healthcare/government customers.

---

## Fastest path to first revenue

1. ~~Get Stripe keys → execute Stripe billing~~ ✓ Done
2. Create DOKS cluster → execute `plans/public-deployment.md` (manual steps, ~1 hour)
3. Target one fintech or healthcare startup at `app.openproxyai.com`

---

## Business model

| Plan | Price | Users | Notes |
|---|---|---|---|
| Free | $0 | 3 | Self-serve, no PII detection |
| Starter | $2,500/mo | 50 | PII detection, 30-day log retention |
| Growth | $7,500/mo | 200 | 90-day log retention |
| Enterprise | $25,000+/mo | Unlimited | SSO, on-premise, 365-day retention |

Target: $500K ARR Year 1, $5M ARR Year 2.

---

## Blueprint one-liners

```
/blueprint openproxyai "Presidio sidecar in Helm chart — optional presidio-analyzer sub-chart with presidio.enabled: true in values.yaml"
/blueprint openproxyai "Real-time cost dashboard — replace REST polling with WebSocket feed for live spend and request volume"
/blueprint openproxyai "Usage-based billing metering — Stripe usage records synced from per-request cost tracking"
/blueprint openproxyai "Multi-tenant data isolation audit — RLS policies on all tables, org_id enforcement verification"
/blueprint openproxyai "Webhook dead-letter queue and replay — DLQ for failed deliveries, admin replay UI, delivery status dashboard"
/blueprint openproxyai "Semantic caching — embed requests, cosine-match against Redis/Pinecone vector store, return cached response above threshold"
/blueprint openproxyai "Voice endpoint — POST /v1/audio/transcriptions wrapping Whisper with same auth/policy/audit pipeline as chat completions"
/blueprint openproxyai "Model A/B testing — route % of traffic to model variants, aggregate latency/cost/quality per variant in dashboard"
/blueprint openproxyai "WASM plugin system — customer-written before/after hooks compiled to WASM, loaded and executed per request"
```
