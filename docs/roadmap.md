# OpenProxyAI — Roadmap

> Last reviewed: 2026-03-19
> Current state: Phase 6 in progress. 294 tests passing. Core product is production-ready.

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

### Policy engine
- Enforcement modes: `off` / `log_only` / `enforce`
- Model allowlist, keyword blocking, regex-based PII detection
- ML-based prompt injection detection — `protectai/deberta-v3-base-prompt-injection`, fail-open
- Response guardrails — keyword + PII checks on LLM output before returning to client
- Response PII redaction — replaces detected PII with `[REDACTED]` in-stream
- Per-org policy config stored in PostgreSQL, 60s Redis cache, instant invalidation on save

### Observability
- Async audit log — immutable PostgreSQL `request_logs`, plan-based retention + archival cron
- ClickHouse dual-write — fire-and-forget sidecar for OLAP analytics at scale
- Langfuse tracing — optional, fire-and-forget (v4 SDK, OTel transport)
- Prometheus metrics — `/metrics` endpoint, ServiceMonitor for Kubernetes
- p95/p99 latency in analytics — `percentile_cont()` in PostgreSQL
- Materialized view `mv_daily_spend` — refreshed every 5 minutes for sub-second dashboard queries

### Admin console
- Dashboard (cost, tokens, request volume, latency percentiles)
- Log viewer with request detail and label filtering
- Policy editor — all fields configurable per org without code changes
- Team management — invite, deactivate, role change
- Provider key management — create, rotate, delete (audit-logged)
- Onboarding modal — 3-step first-run key creation
- Self-serve signup — public registration at `/signup`, no manual DB setup needed

### Infrastructure
- Docker Compose for local development
- Kubernetes Helm chart — HPA, PDB, ServiceMonitor, init-container migrations
- Frontend Docker build — multi-stage nginx image with SPA fallback
- GitHub Actions CI/CD — test → build → push GHCR → helm upgrade on every push to main
- Exact-match Redis cache with configurable TTL (off by default)

### SDKs
- Python SDK — `openproxy-ai` on PyPI, sync + async, streaming, typed errors
- TypeScript SDK — `openproxy-ai` on npm, ESM + CJS, typed streaming

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
| **Stripe billing** | Step 1 done (DB schema); Steps 2–5 waiting on Stripe keys | `plans/stripe-billing.md` |
| **Public deployment** | Code complete; waiting on DOKS cluster + DNS setup | `plans/public-deployment.md` |

---

## Phase 6 — Go-to-market *(in progress)*

### 6.1 — Stripe billing *(partially done — blocked on Stripe keys)*
- DB schema: `stripe_customer_id`, `stripe_subscription_id`, `stripe_subscription_status` ✓
- `stripe_events` idempotency table ✓
- Plan override guard (409 when trying to manually change a Stripe-managed plan) ✓
- `billing_service.py`, routes (`/checkout`, `/portal`, `/webhook`), frontend UI — see `plans/stripe-billing.md`

### 6.2 — Self-serve signup ✓ Shipped
- `/signup` route in admin console
- `signup()` in AuthContext calling `POST /api/v1/auth/register`
- Login page links to signup

### 6.3 — Public deployment *(code done — manual infra pending)*
- Frontend Dockerfile + nginx SPA config ✓
- Helm frontend templates + `values.prod.yaml` ✓
- `cert-manager` ClusterIssuer ✓
- GitHub Actions CI/CD (test → build → push → deploy) ✓
- Remaining: DOKS cluster, managed DB/Redis, DNS, GitHub secrets → `plans/public-deployment.md`

---

## Phase 7 — Enterprise hardening *(next after Phase 6)*

### 7.1 — Compliance report export
One-click CSV from admin console: policy violations by date range, user access list with role
history, provider key rotation log, budget vs actual spend. Maps to SOC 2 CC7 evidence.

### 7.2 — Budget forecasting
"Projected month-end spend: $X" card on the cost dashboard from current daily average.

### 7.3 — Presidio PII detection (real NLP)
Uncomment `presidio-analyzer`, rebuild image. Optional Helm sub-chart (`presidio.enabled: true`).

### 7.4 — Real-time cost dashboard (WebSocket)
Replace polling dashboard with WebSocket feed for live spend visibility.

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

1. Get Stripe keys → execute `plans/stripe-billing.md` (Steps 2–5)
2. Create DOKS cluster → execute `plans/public-deployment.md` (manual steps)
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
/blueprint openproxyai "Stripe billing — execute plans/stripe-billing.md Steps 2-5"
/blueprint openproxyai "Compliance report export — one-click CSV of violations, user access list, key rotation log, budget vs actual"
/blueprint openproxyai "Budget forecasting — projected month-end spend card on cost dashboard from current daily average"
/blueprint openproxyai "Presidio sidecar in Helm chart — optional presidio-analyzer sub-chart with presidio.enabled: true in values.yaml"
/blueprint openproxyai "Real-time cost dashboard — replace REST polling with WebSocket feed for live spend and request volume"
/blueprint openproxyai "Semantic caching — embed requests, cosine-match against Redis/Pinecone vector store, return cached response above threshold"
/blueprint openproxyai "Voice endpoint — POST /v1/audio/transcriptions wrapping Whisper with same auth/policy/audit pipeline as chat completions"
/blueprint openproxyai "Model A/B testing — route % of traffic to model variants, aggregate latency/cost/quality per variant in dashboard"
/blueprint openproxyai "WASM plugin system — customer-written before/after hooks compiled to WASM, loaded and executed per request"
```
