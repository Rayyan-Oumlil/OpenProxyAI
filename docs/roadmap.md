# OpenProxyAI — Roadmap

> Last reviewed: 2026-03-18
> Current state: Phase 5 complete. 294 tests passing. All P0 and P1 hardening done.

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
- Model allowlist, keyword blocking, PII detection (regex fallback — see known gaps)
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

### Infrastructure
- Docker Compose for local development
- Kubernetes Helm chart — HPA, PDB, ServiceMonitor, init-container migrations
- Exact-match Redis cache with configurable TTL (off by default)

### SDKs
- Python SDK — `openproxy-ai` on PyPI, sync + async, streaming, typed errors
- TypeScript SDK — `openproxy-ai` on npm, ESM + CJS, typed streaming

---

## Known bugs and gaps (fix before going public)

These are real discrepancies between what the code says and what is actually true.

### Bug 1 — OrganizationSettingsPage plan names are wrong
**File:** `admin-console/src/features/placeholder/OrganizationSettingsPage.tsx`

The UI plan dropdown has: `free / pro / team / enterprise`
The backend plan matrix has: `free / starter / growth / enterprise`

`pro` and `team` do not exist in `config.py PLAN_FEATURES`. If an admin selects either,
it saves an invalid plan string that maps to nothing — plan enforcement silently breaks
(no PII detection gating, no user limits, no retention rules apply).

**Fix:** Change the two `<option>` values to `starter` and `growth`.

---

### Bug 2 — Presidio PII detection is not installed
**File:** `backend/requirements.txt`

```
# presidio-analyzer>=2.2   ← commented out
```

The roadmap and docs say "Microsoft Presidio NLP PII detection" is shipped.
It is not. `presidio_service.py` falls back immediately to an empty list.
PII detection is regex-only. This is fine for now, but the docs are inaccurate.

**Fix when ready:** Uncomment the requirement, rebuild the Docker image.
Note: Presidio adds ~800MB to the image and requires spaCy language model download on first run.

---

### Gap 3 — Cache is exact-match, not semantic
**File:** `backend/app/services/cache_service.py`

What's built: SHA-256 hash of `(model, messages, temperature)` → Redis lookup.
This only hits on byte-for-byte identical requests.

What the roadmap calls "semantic caching" is different: embed the request with a
small embedding model, store the vector, return a cached response when cosine
similarity exceeds a threshold. That is not built.

The exact-match cache is useful (good for repeated API calls in CI/CD or eval loops).
It just does not reduce cost for paraphrased or slightly different prompts.

---

### Gap 4 — No JWT silent refresh in admin console
**File:** `admin-console/src/` — not implemented anywhere

The `POST /api/v1/auth/refresh` endpoint exists and works (tested).
The React admin console does not call it. Users are silently logged out after 24h.

**Fix:** On app mount, schedule a `setInterval` that fires 5 minutes before token expiry,
calls `/auth/refresh`, and updates the token in `AuthContext`.

---

## What's completely missing (blocks revenue)

| Item | Why it blocks revenue |
|---|---|
| **Public deployment** | No URL to share. Nobody can try the product. |
| **Stripe billing** | Can't charge customers. Plan enforcement has no payment backing. |
| **Self-serve signup** | New orgs require manual DB work. No public registration flow. |
| **Compliance report export** | SOC 2 auditors want one-click CSV. It's a `SELECT` + download. Not built. |
| **Budget forecasting** | "You're on track to spend $X this month" — one SQL query. Not built. |

---

## Next phases

### Phase 6 — Go-to-market (do this before anything else)

This is the highest-leverage phase. The product is production-ready.
The only thing blocking the first paying customer is the ability to sign up and pay.

**6.0 — Fix known bugs first (1 day)**
- Fix OrganizationSettingsPage plan names (`pro` → `starter`, `team` → `growth`)
- Add JWT silent refresh to admin console

**6.1 — Stripe billing integration**
Accept payment for Starter ($2,500/mo), Growth ($7,500/mo), and Enterprise plans.
Stripe Checkout for self-serve signup, Customer Portal for plan changes and invoice history.
Webhook handler for `customer.subscription.updated` to sync plan in PostgreSQL.

**6.2 — Self-serve signup flow**
A visitor lands on a marketing page, clicks "Start free trial", creates an org, gets their
first API key, and makes their first proxied call — without talking to anyone.
Currently the org must be created manually or via the register endpoint with no frontend.

**6.3 — Public deployment**
Deploy to a public URL (EKS, GKE, or DigitalOcean Kubernetes).
Add a custom domain, SSL cert, and a minimal landing page.
Without this, there is nothing to share with potential customers.

**6.4 — Admin console session refresh** *(see Gap 4 above)*
Silent refresh in the admin console 5 minutes before JWT expiry.

---

### Phase 7 — Enterprise hardening

These items make existing customers renew and make procurement reviews pass.

**7.1 — Compliance report export**
One-click CSV download from the admin console: policy violations by date range,
full user access list with role history, provider key rotation log, budget vs actual spend.
Directly maps to SOC 2 CC7 evidence gathering.

**7.2 — Budget forecasting**
Show "projected month-end spend: $X" on the cost dashboard, calculated from the current
daily average. One SQL query, one dashboard card, high customer perceived value.

**7.3 — Presidio PII detection (real NLP)**
Uncomment `presidio-analyzer` in requirements.txt, rebuild image.
Add `presidio-analyzer` as an optional Helm sub-chart for self-hosted customers.

**7.4 — Real-time cost dashboard (WebSocket)**
Replace the polling dashboard with a WebSocket feed.
Enterprise customers with high-volume teams want live spend visibility.

---

### Phase 8 — Advanced gateway

Features that expand what the gateway can do.

**8.1 — Semantic caching**
Embed each request with a small model (e.g. `text-embedding-3-small`), store vector +
response in Redis or Pinecone, return cached response when cosine similarity exceeds
threshold. Reduces cost 20–40% for repetitive workloads like chatbots.

**8.2 — Voice endpoint**
`POST /v1/audio/transcriptions` — wrap Whisper API (or self-hosted) with the same
auth/policy/audit pipeline as chat completions.
Full architecture in `docs/guides/voice-integration.md`.

**8.3 — Model A/B testing**
Route a configurable percentage of traffic to model A vs model B.
Aggregate latency, cost, and quality metrics per variant in the dashboard.
Enterprise prompt engineers need this for model migration decisions.

**8.4 — Multi-region routing**
Wire the existing `data_region` column on `organizations` to a routing layer that sends
EU-org requests only to EU-hosted providers. Required for GDPR data residency compliance.

---

### Phase 9 — Moat features

Long-horizon items that create durable competitive advantage.

**9.1 — WASM plugin system**
Let enterprise customers write custom `before_request` and `after_request` hooks in any
language that compiles to WASM. No competitor offers this as a hosted SaaS.

**9.2 — On-premise distribution**
Air-gapped Helm chart + license key validation for healthcare/government customers who
cannot send data to a SaaS. The Helm chart already exists; this adds license enforcement
and an air-gapped image registry.

---

## What NOT to build yet

| Item | Why to skip for now |
|---|---|
| Semantic caching (embeddings) | Complex infra, no customer has asked for it |
| Voice endpoint | No demand signal yet |
| WASM plugins | Impressive but zero customers need it |
| Model A/B testing | Nice to have, not urgent |
| Multi-region routing | Only relevant once you have EU customers |

---

## Blueprint input — one-liners for `/blueprint`

```
/blueprint openproxyai "Fix OrganizationSettingsPage plan names — pro→starter, team→growth"
/blueprint openproxyai "JWT silent refresh in admin console — call POST /auth/refresh 5 min before expiry, update AuthContext"
/blueprint openproxyai "Stripe billing — Starter/Growth/Enterprise plans, Checkout, Customer Portal, webhook sync to plan column"
/blueprint openproxyai "Self-serve signup — public org creation, first API key generation, onboarding without manual DB setup"
/blueprint openproxyai "Public deployment — DigitalOcean or EKS, custom domain, SSL, minimal landing page"
/blueprint openproxyai "Compliance report export — one-click CSV of violations, user access list, key rotation log, budget vs actual"
/blueprint openproxyai "Budget forecasting — projected month-end spend card on cost dashboard from current daily average"
/blueprint openproxyai "Presidio sidecar in Helm chart — optional presidio-analyzer sub-chart with presidio.enabled: true in values.yaml"
/blueprint openproxyai "Real-time cost dashboard — replace REST polling with WebSocket feed for live spend and request volume"
/blueprint openproxyai "Semantic caching — embed requests, cosine-match against Redis/Pinecone vector store, return cached response above threshold"
/blueprint openproxyai "Voice endpoint — POST /v1/audio/transcriptions wrapping Whisper with same auth/policy/audit pipeline as chat completions"
/blueprint openproxyai "Model A/B testing — route % of traffic to model variants, aggregate latency/cost/quality per variant in dashboard"
/blueprint openproxyai "WASM plugin system — customer-written before/after hooks compiled to WASM, loaded and executed per request"
```

---

## Fastest path to first revenue

1. Fix Bug 1 (plan names) and Gap 4 (JWT refresh) — 1 day
2. Deploy to a public URL — 1 day
3. Add Stripe billing for the Starter plan — 3 days
4. Enable self-serve signup with a minimal landing page — 2 days
5. Target one fintech or healthcare startup — they already feel the compliance pain

The proxy, auth, rate limiting, policy enforcement, audit trail, admin console,
and Kubernetes chart are all production-grade. Nothing in the core is a blocker.

---

## Business model

| Plan | Price | Users | Notes |
|---|---|---|---|
| Free | $0 | 3 | Self-serve, no PII detection |
| Starter | $2,500/mo | 50 | PII detection, 30-day log retention |
| Growth | $7,500/mo | 200 | 90-day log retention |
| Enterprise | $25,000+/mo | Unlimited | SSO, on-premise, 365-day retention |

Target: $500K ARR Year 1, $5M ARR Year 2.
