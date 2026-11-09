# OpenProxyAI — Feature Reference

> Complete inventory of shipped capabilities. 755 passing backend tests across 68 test files (`cd backend && pytest`; 740 without Postgres + Redis, which the RLS and end-to-end suites need).

---

## LLM Proxy & Gateway

| Feature | Details |
|---|---|
| Chat completions | `POST /v1/chat/completions` — streaming (SSE) and non-streaming |
| Embeddings | `POST /v1/embeddings` — same auth/policy/audit pipeline |
| Multi-provider | 100+ LLM providers via LiteLLM (OpenAI, Anthropic, Azure, Mistral, Google, etc.) |
| Provider fallback | Automatic retry on 429/5xx; never on 4xx client errors. Configurable chain depth |
| Weighted key rotation | Per-provider keys with `weight` field for probabilistic selection |
| Router strategies | `simple_shuffle`, `round_robin`, `lowest_latency` via `ROUTER_STRATEGY`; per-org override in `settings.router.strategy` |
| Provider health check | APScheduler pings keys, marks unhealthy; routing skips unhealthy keys when `PROVIDER_HEALTH_CHECK_ENABLED` |
| Circuit breaker | Per-key failure tracking; after N consecutive 429/5xx, key skipped until cooldown (`CIRCUIT_BREAKER_ENABLED`, `CIRCUIT_BREAKER_FAILURE_THRESHOLD`, `CIRCUIT_BREAKER_COOLDOWN_SECONDS`). Dashboard shows circuit state (Open/Closed) per key |
| Adaptive load balancing | When `ADAPTIVE_LB_ENABLED`, samples latency/error per provider key from `request_logs`; adjusts effective weights for selection; Provider Keys dashboard shows P99, Error %, Eff. Weight. See [operational-features.md](./guides/operational-features.md#adaptive-load-balancing) |
| Key rotation scheduler | Re-encrypt provider keys on interval (`KEY_ROTATION_SCHEDULER_ENABLED`, `KEY_ROTATION_INTERVAL_DAYS`) |
| Custom provider endpoints | An `openai` provider key can set `api_base` (any OpenAI-compatible server: vLLM, Ollama's `/v1`, a private gateway) and `is_internal`; other providers cannot, because only OpenAI-compatible calls can go through the guard. Chat, streaming, embeddings, the playground compare and the health check call that endpoint instead of the provider's. Checked three times: when saved (clear error), before a call (a key that stopped validating is skipped, and if all are skipped the request fails with 503 instead of using another credential), and **on every connection** by a guard that never follows redirects, resolves the host itself and connects to the address it validated, verifies TLS against the hostname, and re-reads the operator switch. External endpoints must be https and public; private or plain-http endpoints need `ALLOW_INTERNAL_PROVIDER_ENDPOINTS`; link-local and cloud-metadata addresses are never reachable. Refused in `AIRGAP_MODE` unless internal |
| Data classification | Every chat and embedding request gets a class (built-in detector, `app/services/pii_detection.py`, shared with PII blocking and response redaction: text is normalized first, cards need a valid Luhn checksum, SSNs must be issuable; `data_class_map` names only fire for what the detector reports: `email`, `ssn`, `payment_card`, or Presidio's entity types when Presidio is installed): the highest of the org's `default_data_class` (default `internal`), the caller's `x-openproxy-data-class` header (raise only; unknown value is a 400) and the class of each kind of PII found (`data_class_map` over built-in defaults, e.g. SSN and payment card are `confidential`). Text too large to scan counts as `confidential`. Returned as `X-OpenProxyAI-Data-Class`, stored in the audit row's metadata (kinds of PII only, never the text), shown on the request trace. Off when `pii_detection_enabled` is false. The default class, the per-kind classes and the routing mode are set on the console's Policy > Data and routing tab; routing uses the class (see Classification-aware routing) |
| Classification-aware routing | Per-org `routing_mode`: `off` (default), `log_only` (record the decision, refuse nothing) or `enforce`. Enforced, a model serves a request only if the registry says so: enabled, active key, cleared for the request's class (the lower of the model's and its key's), in the org's region, within `max_risk_rating`, on the policy allowlist. A refused request gets HTTP 446 `routing_blocked` / `no_authorized_model` before any upstream call. The model is served **only by its registry key** (no other key of that provider, never an environment key). A `x-openproxy-fallback-model` that is not authorized is ignored; an experiment variant that is not authorized is dropped for the model the caller asked for; the semantic cache and the evaluation hook are skipped above `OFF_REGISTRY_MAX_DATA_CLASS` (destinations the registry does not govern). The playground compare endpoint obeys the same rules: a model that is not authorized for the prompt is reported as refused and never called. `model: "cap:NAME"` picks the cheapest, then lowest-risk authorized model with that capability. Decision in the audit row, `X-OpenProxyAI-Route-Model` and `-Route-Reason` headers, a `route` trace stage, and a plain-language "Routing" line on the request trace page (what was authorized, why a model was ruled out). Chat completions and embeddings (embeddings have no fallback header, experiments or `cap:` routing) |
| Policy preview | `POST /api/v1/policy/preview` (admin only): classify, policy-check and route a hypothetical request without sending it. Shows the class and what set it, whether policy would block it, which registry model would serve it and through which key, why every other model was ruled out, and whether a fallback model would be allowed. Always shows what `enforce` would do, so routing can be previewed before it is turned on. On the console: Policy > Data and routing > Preview a request (admin only; it uses the saved policy, not unsaved edits). No upstream call, no audit row, no rate-limit or budget use. An e2e table of scenarios keeps it identical to the real pipeline |
| Model registry | `/api/v1/model-registry` (admin only): per-model `max_data_class` (cannot exceed its provider key's), `regions`, `risk_rating`, `retention_days`, `trains_on_data`, `capabilities`, `cost_tier`, `owner`, `enabled`, linked `provider_key_id` (same org, same provider). Deleting the key detaches the entry. Row-level security; changes are in the admin audit log. Routing reads it (see Classification-aware routing); managed on the console Model registry page |
| Key data class | `max_data_class` on a provider key (`public` < `internal` < `confidential` < `secret`, default `internal`): the most sensitive data its endpoint may receive. Routing uses it: a model is never served through a key cleared for less than the request's class |
| Model pattern matching | `fnmatch` patterns on provider keys (e.g. `gpt-4*`, `claude-*`) |
| Streaming peek | First SSE chunk inspected — provider errors surface as proper HTTP codes, not buried in stream |
| Response caching | SHA-256 exact-match Redis cache with configurable TTL (off by default) |
| Semantic caching | 3-tier cache: L1 in-memory TTLCache, L2 Redis exact-match, L3 pgvector cosine similarity. Configurable threshold (default 0.95). Per-request override via `x-openproxy-cache` header (`skip`, `no-store`, `no-cache`). Dashboard hit-rate metrics with tokens-saved tracking |
| Model list | `GET /v1/models` — OpenAI-compatible model list aggregated from provider keys + `model_patterns` via fnmatch expansion |
| Data residency | `region` field on provider keys (`us`, `eu`, `ap`, `global`), `data_region` on orgs. SQL filtering ensures EU orgs never route through US-only keys |
| Budget pre-flight | Estimated cost check before streaming begins — rejects with 402 if remaining budget is too low |
| Response headers | Every response includes `X-OpenProxyAI-Request-Id`, `-Cost-USD`, `-Latency-Ms`, `-TTFT-Ms`, `-Cache`, `-Provider`, `-Model`, `-Gateway-Error`, `-Policy-Action`, and `X-RateLimit-*` headers |
| Request labels | `x-openproxy-labels` header for departmental chargebacks, stored in log metadata |
| Per-request overrides | `x-openproxy-retries` (0–5 max fallback attempts), `x-openproxy-fallback-model` (alternate model when primary keys fail), `x-openproxy-session-id` (trace grouping) |
| Prompt ID on proxy | Chat completions accept optional `prompt_id` + `variables` instead of `messages`; templates from Playground are resolved server-side with `{{var}}` substitution before policy/model selection |
| Model A/B experiments | `experiments` + weighted variants on a `target_model`; gateway resolves a variant per request, tags `request_metadata.experiment` (incl. `variant_id`); enforces **resolved** model against policy `allowed_models`; results API aggregates per-variant metrics from `request_logs`; **Request Scores API** (`POST /api/v1/requests/{id}/scores`) for quality scores; **eval hook** (`EVAL_HOOK_URL` / `EVAL_LLM_MODEL`) auto-submits scores for experiment requests (fail-open); results include `scores` (avg, count) per variant; **Experiments dashboard** shows Quality column per variant; PostgreSQL RLS on `experiments` / `experiment_variants`; create/update reject `target_model` / variant models not on the org allowlist when the allowlist is non-empty |

---

## MCP Gateway

| Feature | Details |
|---|---|
| Endpoint | `POST /v1/mcp` — MCP 2025-11-25 Streamable HTTP, JSON-RPC 2.0, authenticated with an OpenProxyAI API key |
| Aggregation | `tools/list` merges every active upstream server of the org; tools are namespaced `<server>__<tool>`; unreachable servers reported in `_meta` |
| Tool policy | `mcp_allowed_tools` / `mcp_blocked_tools` (fnmatch) plus keyword/PII guardrails on tool arguments; follows `off` / `log_only` / `enforce` |
| Blocking | Refused calls never reach the upstream; JSON-RPC error `-32001` with `reason_code` |
| Audit | One `request_logs` row per `tools/call` (`provider = mcp:<server>`, status 200/446/502/400) |
| Tool pinning | Per-server `pin_mode`: `off`, `warn` (default; trust on first use, later changes mark the tool `drifted`) or `enforce` (admin approval required). `tools/list` serves the approved snapshot, never the live description; drifted/pending/blocked tools are hidden and refused with JSON-RPC -32004 under `enforce`. Definitions are hashed (sha256 of canonical JSON), versions kept append-only, synced every 15 min (`MCP_TOOL_SYNC_*`) and on `POST /api/v1/mcp-servers/{id}/sync`; review with `.../tools/{id}/approve` and `.../block` |
| Injection scanning | Per-server `scan_mode`: `off`, `log` (default; report only), `redact` (strip and mark) or `block`. Applied to the tool descriptions agents are shown and to every tool result: invisible Unicode tags and zero-width characters, "ignore previous instructions", `<IMPORTANT>`-style markup, concealment ("do not tell the user"), markdown-image exfiltration URLs, long base64 runs, oversized or deeply nested text. Blocked results return JSON-RPC -32007 (audit status 446); findings (category names only, never the text) go to the audit row. Heuristics can false-positive, hence the `log` default |
| Tool grants | `tool_grants` rows (subject: role, team, user or API key; fnmatch pattern over `<server>__<tool>`; `allow`/`deny`) managed at `/api/v1/mcp-grants`. Org policy stays the outer cap; a deny always wins; if any allow grant applies to the caller the tool must match one, otherwise the caller is unrestricted. `X-OpenProxy-MCP-Tools: pattern,pattern` can only narrow a request (malformed or repeated header: 400). The patterns that applied are written to the audit row as `tool_access` |
| Virtual bundles | A bundle is a named set of tool patterns (`/api/v1/mcp-bundles`), attached to API keys and served at `POST /v1/mcp/{slug}` as one more narrowing layer after org policy and grants. A key attached to any bundle is confined to its bundles (bare `/v1/mcp` returns 403); unknown, inactive and not-attached slugs all return the same 404; an empty bundle allows nothing |
| Taint tracking | `initialize` now issues a real session (Redis `mcp:sess:<id>`, bound to the API key; unknown, expired or foreign ids get 404 so the client re-initializes). A tool result from any tool not matched by a `trusted_output` trust rule taints the session; a tool matched by a `sink` rule refuses to run in a tainted or session-less call (JSON-RPC -32009, audit 446). Rules are managed at `/api/v1/mcp-trust-rules`. On `/v1/chat/completions`, when the conversation contains output of an untrusted tool, sink tools are removed from the request's `tools` (and forcing one through `tool_choice` is a policy block); `log_only` reports without changing the request. Taint state is written to the audit row |
| Telemetry export | Sidecar, off by default, never blocks or fails a request (bounded queue, drops are counted, errors logged once a minute without exception text). **SIEM** (`SIEM_EXPORT_ENABLED`, `SIEM_FORMAT=cef|json`, `SIEM_SINK=stdout|file|syslog_udp|syslog_tcp`): events `AI-POLICY-BLOCK`, `AI-DLP-BLOCK`, `AI-INJECTION-BLOCK`, `AI-INJECTION-FLAGGED`, `AI-UNAUTHORIZED-MCP`, `AI-MCP-TOOL-BLOCK`, `AI-TOOL-DRIFT`, `AI-TAINT-BLOCK`, `AI-BUDGET-EXCEEDED`, `AI-RATE-LIMIT` carry ids, reason codes and category names, never prompts, results or arguments; RFC 5424 framing for syslog sinks. **OpenTelemetry** (`OTEL_EXPORT_ENABLED`, `OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_EXPORTER_OTLP_HEADERS`): one `gen_ai.*` span per chat request (`chat <model>`) and per MCP call (`execute_tool <tool>`) over OTLP/HTTP JSON, no SDK dependency. Misconfiguration fails startup instead of silently disabling export |
| Transport safety | Hostname resolved once and the validated IP is connected to (Host/SNI preserved); 3xx rejected; 2 MB response cap; 30 s total deadline; upstream session closed with `DELETE`; upstream error text is logged, never returned to the agent |
| Access | API key needs the `proxy:mcp` permission (403 otherwise); browser `Origin` must be in `CORS_ORIGINS` (403); `MCP_RATE_LIMIT_PER_MINUTE` per key (429 + `Retry-After`, default 120) |
| Server registry | `/api/v1/mcp-servers` — admin-only writes, HTTPS + SSRF check, encrypted write-only auth header, admin audit log |
| Guide | [docs-site/docs/guides/mcp-gateway.md](../docs-site/docs/guides/mcp-gateway.md) |

---

## Teams (org structure)

| Feature | Details |
|---|---|
| Teams API | `GET/POST/PATCH/DELETE /api/v1/teams`, member add/remove — **admin-only** mutations |
| Members & budgets | Many-to-many users↔teams; optional `budget_monthly_usd` per team |
| Org isolation | All team operations scoped to the caller's organization |
| Team-scoped API keys | Optional `team_id` on gateway API keys; creating user must be team member; key's team context propagates to requests |
| Cost by team | Analytics `by_team` in overview; dashboard "Cost by team" table; team filter on usage |
| Team rate limits | Policy `per_team_limits: {rpm, tpm}` — per-team RPM/TPM when request has team context |

---

## Prompt Playground

| Feature | Details |
|---|---|
| Model compare | Side-by-side testing against 2+ models with TTFT, total latency, token count, and cost per response |
| Prompt templates | CRUD for named templates with system message, user template (`{{variables}}`), versioning, and soft-delete; templates can be invoked on the proxy via `prompt_id` in chat completions |
| Policy enforcement | Compare endpoint evaluates org policy (model allowlist, keywords, PII) before running comparisons |
| Audit integration | All playground requests logged through the same audit pipeline as proxy requests |

---

## Compliance Templates

| Feature | Details |
|---|---|
| Healthcare / HIPAA | PII entities (SSN, MRN, PHI), blocked keywords, model allowlist, 7-year audit retention |
| Finance / PCI-DSS | Credit card regex, trade compliance keywords, SOX export format |
| Government / FedRAMP-style | Classified-marking keyword blocking, PII redaction, 3-year audit retention. Not a FedRAMP authorization; the template does not enforce US-only providers (assign US-region provider keys yourself) |
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
| Batched spend writes | Optional Redis queue → Postgres flush every 60s (`BATCH_SPEND_ENABLED`) — reduces DB load under high traffic |
| User daily budget | Per-user spend cap independent of org limit |
| Per-model rate limits | Model-specific RPM/TPM caps via policy config |
| Per-team rate limits | Policy `per_team_limits` — RPM/TPM per team when request has team context (API key or `x-openproxy-team-id`) |
| Budget threshold alerts | Webhook fired at 80% spend (atomic dedup, once per day per org) |
| Spend reports | Weekly (Mon) and monthly (1st) digest to Slack webhook or email; org settings `spend_report.webhook` / `spend_report.email` |
| Cost anomaly detection | 7-day baseline comparison per org and per user, configurable multiplier |
| Rate-limit headers | `X-RateLimit-Requests-Remaining`, `-Tokens-Remaining`, `-Budget-Remaining-USD`, `-Reset` |

---

## Policy Engine

| Feature | Details |
|---|---|
| Enforcement modes | `off` / `log_only` / `enforce` — configurable per org |
| Model allowlist | Restrict which models an org can use |
| Keyword blocking | Scan prompt text for forbidden terms |
| PII detection (regex) | Built-in regex for email, SSN and credit card numbers (phone numbers and names need the optional Presidio integration) |
| PII detection (NLP) | Optional Presidio integration — disabled by default due to image size (+800 MB) |
| Prompt injection detection | ML model (`protectai/deberta-v3-base-prompt-injection`); regex patterns when the model is not loaded; timeouts and inference errors fail open |
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
| Metered usage (Stripe) | Optional metered price + subscription item; hourly job reports token usage to Stripe usage records; plan includes `metered` feature and `included_tokens_monthly`; admin billing shows usage vs included quota (see `docs/guides/stripe-setup.md`) |
| Plan override guard | PATCH org with plan returns 409 when Stripe-managed |
| Billing UI | Plan comparison cards, upgrade flow, post-checkout polling, portal redirect, metered usage summary when configured |

---

## Analytics & Observability

| Feature | Details |
|---|---|
| Dashboard overview | Requests, cost, tokens and latency with the change against the previous period and a sparkline each; success rate, policy blocks and flags, cache hit rate; month-to-date budget burn-down with a projection to month end. The overview's totals and every breakdown read live `request_logs`, so they agree with each other right after traffic |
| Daily usage trend | Per-day requests, tokens, cost and latency from `request_logs` (the `mv_daily_spend` view is still used by billing, the compliance export and provider reconciliation) |
| Cost by model/user/team/API key | `by_model`, `by_user`, `by_team` and `by_key` in the analytics overview, with the team and session filters; dashboard tables for team, API key and user (admin only) |
| Latency percentiles | p50/p95/p99 via `percentile_cont()` |
| TTFT tracking | Time-to-first-token on streaming requests |
| Monthly projection | Projected month-end spend from daily average |
| Request log viewer | Paginated, filterable by model, status, policy action, label |
| Log detail drill-down | Full request/response metadata in slide-out drawer |
| Request trace | `/logs/:id` waterfall of where a request spent its time: `auth`, `policy`, `rate_limit`, `cache`, `upstream` (chat and embeddings), recorded in `request_metadata.stages`. A stage that did not run is absent; rows logged before stage timing say so |
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
| Dashboard | KPI cards with deltas and sparklines, reliability and governance tiles, budget burn-down, daily trend, spend by model, team, API key and user, compliance export |
| Request logs | Filterable table on the shared `DataTable` (filters stay on screen when they match nothing), detail drawer, and a full request trace page |
| API Keys | Create, list, revoke (with confirmation) gateway API keys; optional team association |
| Model registry | Governance > Model registry: list, add, edit, enable or disable and remove vetted models with their provider key, data class, regions, risk, retention and capabilities; shows when a model has no key attached |
| Provider Keys | Add, toggle, delete upstream provider keys with region tagging, custom endpoint and data class; adaptive load-balancing columns when reported |
| Provider health | One state per key (healthy, degraded, down, not checked, disabled) with the reason, last health check, p99, error rate and effective weight; says why data is missing when health checks or adaptive load balancing are off |
| Policy Config | Tabs for Enforcement (mode, model allowlist, blocked keywords), Data protection (PII, prompt injection, response guardrails), Rate limits (per model) and Templates (compliance quick-apply); one form, one save bar with unsaved-changes state and Discard |
| MCP servers | Register upstream tool servers, set pin and scan mode, review each server's tools: approve, block, sync, and a field-level diff of a drifted tool against its approved definition |
| Billing | Plan cards, Stripe checkout upgrade, portal redirect, subscription status |
| Audit Log | Paginated admin action log with before/after JSON diff |
| Prompt Playground | Side-by-side model comparison, prompt template management, variable substitution |
| Organization Settings | Name, budget, data region selector, read-only plan display |
| Teams | List/create/edit/delete teams, member management, team budgets |
| Experiments | Create model A/B tests, variants & weights, start/stop, results view |
| Users & Roles | Invite, deactivate, role management |
| Onboarding | 3-step wizard for first-run key creation |
| Navigation | Responsive: pinned sidebar on wide screens, drawer on narrow ones; groups Observe, Govern, Connect, Admin; breadcrumbs; command palette (Ctrl/Cmd+K) to jump to any page or sign out |
| Design system | Shared tokens with dark, light and system themes; `DataTable`, `StatusBadge`, `PageHeader`, tabs and a confirmation dialog (`useConfirm`) used across pages; route-level code splitting; a route error boundary so one broken page keeps the console usable |
| Quality gates | ESLint (0 problems), `tsc`, unit tests, and a Playwright suite with axe-core (WCAG 2.1 A and AA) on every screen in both themes on desktop and mobile viewports, run in CI |

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
| Seeded demo | `docker-compose.demo.yml`: own Postgres and Redis, a fake OpenAI-compatible upstream (no provider key, no cost), migrations, a demo organization with policy, a budget-limited user and a pinned MCP server, the console, and a traffic job. [Run it](./getting-started/demo.md); [3-minute walkthrough](./getting-started/walkthrough.md). `scripts/smoke.sh` boots it from nothing and checks it over HTTP; the same check runs in CI |
| Helm chart | Backend + frontend deployments, HPA (2-10 replicas), PDB, ServiceMonitor, init-container migrations |
| Frontend Docker | Multi-stage nginx build with SPA fallback |
| CI/CD | GitHub Actions on push to main: test → build → push to GCP Artifact Registry → migrations as a Cloud Run job → deploy to Cloud Run. The Helm chart is for self-hosted installs |
| cert-manager | LetsEncrypt ClusterIssuer for automatic TLS |
| Kubernetes | Ingress, ConfigMap, ServiceAccount, bundled PostgreSQL + Redis subcharts |
| Customer-cluster install | [customer-cluster-install.md](./guides/customer-cluster-install.md) — use your PostgreSQL/Redis, no managed deps |
| Air-gap mode | `AIRGAP_MODE=true` + `LICENSE_KEY` — disables Langfuse, ClickHouse, spend reports, Stripe metered sync; LLM provider calls remain |

---

## SDKs & Integration

| Item | Details |
|---|---|
| Python SDK | `sdk/python` (install from source) — sync + async, streaming, typed errors |
| TypeScript SDK | `sdk/typescript` (install from source) — ESM + CJS, typed streaming |
| Base URL migration | Use OpenAI/Anthropic SDKs with only a `base_url` change — see [base-url-migration.md](./guides/base-url-migration.md) |
