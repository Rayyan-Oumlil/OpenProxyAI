# OpenProxyAI — Feature Reference

> Complete inventory of shipped capabilities. 506 tests, 51 test files.

---

## LLM Proxy & Gateway

| Feature | Details |
|---|---|
| Chat completions | `POST /v1/chat/completions` — streaming (SSE) and non-streaming |
| Embeddings | `POST /v1/embeddings` — same auth/policy/audit pipeline |
| Multi-provider | 100+ LLM providers via LiteLLM (OpenAI, Anthropic, Azure, Mistral, Google, etc.) |
| Provider fallback | Automatic retry on 429/5xx; never on 4xx client errors. Configurable chain depth |
| Weighted key rotation | Per-provider keys with `weight` field for probabilistic selection |
| Model pattern matching | `fnmatch` patterns on provider keys (e.g. `gpt-4*`, `claude-*`) |
| Streaming peek | First SSE chunk inspected — provider errors surface as proper HTTP codes, not buried in stream |
| Response caching | SHA-256 exact-match Redis cache with configurable TTL (off by default) |
| Semantic caching | 3-tier cache: L1 in-memory TTLCache, L2 Redis exact-match, L3 pgvector cosine similarity. Configurable threshold (default 0.95). Per-request override via `x-openproxy-cache` header (`skip`, `no-store`, `no-cache`). Dashboard hit-rate metrics with tokens-saved tracking |
| Model list | `GET /v1/models` — OpenAI-compatible model list aggregated from provider keys + `model_patterns` via fnmatch expansion |
| Data residency | `region` field on provider keys (`us`, `eu`, `ap`, `global`), `data_region` on orgs. SQL filtering ensures EU orgs never route through US-only keys |
| Budget pre-flight | Estimated cost check before streaming begins — rejects with 402 if remaining budget is too low |
| Response headers | Every response includes `X-OpenProxyAI-Request-Id`, `-Cost-USD`, `-Latency-Ms`, `-TTFT-Ms`, `-Cache`, `-Provider`, `-Model`, `-Gateway-Error`, `-Policy-Action`, and `X-RateLimit-*` headers |
| Request labels | `x-openproxy-labels` header for departmental chargebacks, stored in log metadata |

---

## Prompt Playground

| Feature | Details |
|---|---|
| Model compare | Side-by-side testing against 2+ models with TTFT, total latency, token count, and cost per response |
| Prompt templates | CRUD for named templates with system message, user template (`{{variables}}`), versioning, and soft-delete |
| Policy enforcement | Compare endpoint evaluates org policy (model allowlist, keywords, PII) before running comparisons |
| Audit integration | All playground requests logged through the same audit pipeline as proxy requests |

---

## Compliance Templates

| Feature | Details |
|---|---|
| Healthcare / HIPAA | PII entities (SSN, MRN, PHI), blocked keywords, model allowlist, 7-year audit retention |
| Finance / PCI-DSS | Credit card regex, trade compliance keywords, SOX export format |
| Government / FedRAMP | US-only provider keys, classified keyword blocking, FedRAMP security headers |
| Apply endpoint | `POST /api/v1/organizations/current/policy/apply-template` — merge semantics preserving existing org config |
| Template listing | `GET /api/v1/organizations/current/policy/templates` — returns all available templates with metadata |

---

## Authentication & Access Control

| Feature | Details |
|---|---|
| API key auth | SHA-256 hashed keys — plaintext never stored |
| Email/password auth | Registration, login, JWT access + refresh tokens |
| RBAC | Three roles: `admin`, `developer`, `viewer` — enforced on all management endpoints |
| OIDC/SSO | Per-org generic OIDC connector with auth-code flow and JIT user provisioning |
| Invite system | SHA-256 token-secured invitations with 7-day TTL and role pre-assignment |
| Brute-force protection | Redis-backed fixed-window counter per IP+email, 429 after threshold |
| JWT silent refresh | Proactive token renewal 5 min before expiry, transparent to clients |
| Token blocklist | Redis-backed logout blocklist — revoked tokens rejected immediately |

---

## Rate Limiting & Cost Control

| Feature | Details |
|---|---|
| Org RPM/TPM limits | Fixed-window Redis counters for requests/min and tokens/min |
| Org daily budget | Redis spend tracking, HTTP 402 on exceeded |
| User daily budget | Per-user spend cap independent of org limit |
| Per-model rate limits | Model-specific RPM/TPM caps via policy config |
| Budget threshold alerts | Webhook fired at 80% spend (atomic dedup, once per day per org) |
| Cost anomaly detection | 7-day baseline comparison per org and per user, configurable multiplier |
| Rate-limit headers | `X-RateLimit-Requests-Remaining`, `-Tokens-Remaining`, `-Budget-Remaining-USD`, `-Reset` |

---

## Policy Engine

| Feature | Details |
|---|---|
| Enforcement modes | `off` / `log_only` / `enforce` — configurable per org |
| Model allowlist | Restrict which models an org can use |
| Keyword blocking | Scan prompt text for forbidden terms |
| PII detection (regex) | Built-in regex for email, SSN, credit card, phone number |
| PII detection (NLP) | Optional Presidio integration — disabled by default due to image size (+800 MB) |
| Prompt injection detection | ML model (`protectai/deberta-v3-base-prompt-injection`) with regex fallback, fail-open |
| Response guardrails | Keyword + PII checks on LLM output before returning to client |
| Response PII redaction | Replaces detected PII with `[REDACTED]` in streaming and non-streaming responses |
| Per-org config | Stored in PostgreSQL, 60s Redis cache, instant invalidation on save |
| Policy event logging | Every evaluation result stored in `request_metadata.policy` for analytics |

---

## Billing (Stripe)

| Feature | Details |
|---|---|
| Checkout sessions | `POST /api/v1/billing/checkout` — creates Stripe Checkout for starter/growth plans |
| Customer portal | `POST /api/v1/billing/portal` — Stripe Customer Portal for self-serve management |
| Webhook handler | `POST /api/v1/billing/webhook` — processes checkout.completed, invoice.paid/failed, subscription.updated/deleted |
| Atomic idempotency | `INSERT ... ON CONFLICT DO NOTHING` on `stripe_events` table |
| Plan feature gating | `assert_plan_allows()` enforces user/key limits per tier |
| Plan tiers | Free (3 users), Starter ($2,500/mo, 50 users), Growth ($7,500/mo, 200 users), Enterprise (manual) |
| Plan override guard | PATCH org with plan returns 409 when Stripe-managed |
| Billing UI | Plan comparison cards, upgrade flow, post-checkout polling, portal redirect |

---

## Analytics & Observability

| Feature | Details |
|---|---|
| Dashboard overview | Cost, tokens, request volume, latency percentiles, projected month-end spend |
| Daily usage trend | Aggregated from `mv_daily_spend` materialized view (refreshed every 5 min) |
| Cost by model/user | Breakdown charts for cost attribution |
| Latency percentiles | p50/p95/p99 via `percentile_cont()` |
| TTFT tracking | Time-to-first-token on streaming requests |
| Monthly projection | Projected month-end spend from daily average |
| Request log viewer | Paginated, filterable by model, status, policy action, label |
| Log detail drill-down | Full request/response metadata in slide-out drawer |
| Policy analytics | Violation counts by action/reason with date range filters |
| Policy event export | JSON + CSV download with formula injection prevention |
| Compliance report | CSV export: policy violations, user access, key rotations, budget vs actual |
| Prometheus metrics | 7 metric types: requests, latency, TTFT, tokens, cost, policy, rate-limit |
| Langfuse tracing | Optional fire-and-forget traces per request (v4 SDK, OTel transport) |
| ClickHouse dual-write | Optional fire-and-forget log mirroring for OLAP analytics |

---

## Webhooks

| Feature | Details |
|---|---|
| Per-org config | URL, events, secret — configurable via API |
| HMAC signing | `X-OpenProxy-Signature: sha256={hex}` on every delivery |
| SSRF protection | DNS resolution + private/local/CGN IP rejection, HTTPS-only |
| Retry with backoff | 3 attempts with exponential backoff (1s × 2^n) |
| Delivery audit log | `webhook_deliveries` table tracks status, HTTP code, attempt count |
| Delivery list + replay | `GET /current/webhooks/deliveries` (paginated), `POST .../retry` for manual replay |
| Scheduled retry job | APScheduler job retries failed deliveries with backoff, looks up org secret for HMAC |
| Event types | `policy.violation`, `budget.alert`, `cost.anomaly` |

---

## Admin Console (React SPA)

| Page | Purpose |
|---|---|
| Login / Signup | Email+password auth with self-serve registration |
| Dashboard | 8 metric cards, daily trend chart, top models chart, performance table, compliance export |
| Log Viewer | Filterable request log table with detail drawer |
| API Keys | Create, list, revoke gateway API keys |
| Provider Keys | Add, toggle, delete upstream provider keys with region tagging |
| Policy Config | Full policy editor: enforcement mode, model allowlist, keywords, PII, prompt injection, response guardrails, per-model rate limits, compliance template quick-apply |
| Billing | Plan cards, Stripe checkout upgrade, portal redirect, subscription status |
| Audit Log | Paginated admin action log with before/after JSON diff |
| Prompt Playground | Side-by-side model comparison, prompt template management, variable substitution |
| Organization Settings | Name, budget, data region selector, read-only plan display |
| Users & Roles | Invite, deactivate, role management |
| Onboarding | 3-step wizard for first-run key creation |

---

## Security

| Feature | Details |
|---|---|
| Encryption at rest | Fernet (AES-128-CBC) for provider keys and SSO secrets, PBKDF2 key derivation |
| Webhook SSRF protection | DNS resolution rejects private/loopback/link-local/CGN IPs; HTTPS-only |
| CSV formula injection | Cell prefix sanitization on all CSV export endpoints |
| Admin-only exports | All compliance/policy export endpoints require admin role |
| Secret scrubbing | Webhook secret never returned in API responses |
| Security headers | `X-Content-Type-Options`, `X-Frame-Options`, `HSTS`, `CSP`, `Referrer-Policy`, `Permissions-Policy` |
| Auth rate limiting | Fixed-window Redis counter per IP+email on login and invite acceptance |

---

## Infrastructure & Deployment

| Component | Details |
|---|---|
| Docker Compose | Local development with PostgreSQL, Redis, backend, frontend |
| Helm chart | Backend + frontend deployments, HPA (2-10 replicas), PDB, ServiceMonitor, init-container migrations |
| Frontend Docker | Multi-stage nginx build with SPA fallback |
| CI/CD | GitHub Actions: test → build → push GHCR → helm upgrade on push to main |
| cert-manager | LetsEncrypt ClusterIssuer for automatic TLS |
| Kubernetes | Ingress, ConfigMap, ServiceAccount, bundled PostgreSQL + Redis subcharts |

---

## SDKs

| SDK | Details |
|---|---|
| Python | `openproxy-ai` on PyPI — sync + async, streaming, typed errors |
| TypeScript | `openproxy-ai` on npm — ESM + CJS, typed streaming |
