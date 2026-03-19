# OpenProxyAI — Roadmap

> Forward-looking only. For shipped features, see [features.md](./features.md).
>
> Prioritized by enterprise RFP frequency and revenue impact, informed by competitive analysis of Portkey, Helicone, Kong, Cloudflare, LiteLLM, Envoy, AWS Bedrock, Azure API Management, Bifrost, Martian, Braintrust, and LangSmith.
>
> Last updated: 2026-03-19

---

## Blocking: Go-live

| Item | What's needed | Time estimate |
|---|---|---|
| Public deployment | Create DOKS cluster, provision managed DB/Redis, configure DNS, set GitHub secrets. All code is done. See `plans/public-deployment.md` | ~1 hour of infra work |
| Stripe keys | Create Stripe products/prices, set env vars in production. All code is done. See `docs/guides/stripe-setup.md` | ~30 min |

Everything below is post-launch, prioritized by competitive gap and revenue impact.

---

## P0 — Table stakes gaps (competitors already ship these)

### Semantic caching
**RFP signal:** 58% of enterprise RFPs ask for it. Portkey, Helicone, Kong, and Bifrost all ship it.

**Why:** Exact-match cache only helps CI/eval loops. Semantic cache reduces token spend 20–40% for production chatbot and RAG workloads — the top cost justification for choosing a gateway over raw API calls.

**Scope:**
- Embed request messages via a lightweight model (e.g. `text-embedding-3-small`)
- Store in vector store (pgvector or Pinecone) alongside the cached response
- Cosine-similarity match above configurable threshold (default 0.95)
- Per-request override via `x-openproxy-cache: skip` header
- Dashboard metric: cache hit rate (exact vs semantic) with cost savings estimate
- Optional: in-memory L1 + Redis L2 dual cache layer (from LiteLLM DualCache pattern)

**Files:** Extend `backend/app/services/cache_service.py`, new vector store client, config flags.

### Prompt playground / model compare
**RFP signal:** 42% of RFPs ask for prompt management. LiteLLM Proxy, Portkey Studio, and Helicone all ship comparison UIs.

**Why:** Without this, developers test prompts in external tools and lose the audit trail. Portkey charges separately for Prompt Studio — opportunity to include it.

**Scope:**
- New admin console page: side-by-side prompt testing against 2–3 models
- Show TTFT, total latency, token count, cost per response
- Save prompt templates (name, system message, user template with `{{variables}}`)
- Prompt history linked to request logs for audit

**Files:** New `admin-console/src/features/playground/`, new `backend/app/routes/playground.py`.

### `GET /v1/models` endpoint
**Why:** Every competitor exposes this. SDKs expect it. Quick win for compatibility.

**Scope:** Aggregate available models from provider keys + `model_patterns`. Return OpenAI-compatible model list.

---

## P1 — Revenue accelerators (directly close deals)

### Data residency & regional routing
**RFP signal:** 65% of enterprise RFPs — the #1 deal blocker. Helicone, Kong, LiteLLM, Envoy, AWS, and Azure all support it.

**Why:** EU enterprises refuse to sign if data leaves region. GDPR compliance is non-negotiable. Even a config-level solution unblocks conversations.

**Scope (Tier 1 — config-based, 1 sprint):**
- `data_region` field on organizations (e.g. `eu`, `us`, `ap`)
- Routing rules: "If org is EU, use only EU-region provider keys"
- Provider keys gain `region` field for geographic tagging

**Scope (Tier 2 — self-hosted, 2–3 sprints):**
- Publish hardened Helm chart for on-premise deployment
- Air-gapped mode: license key validation, no outbound telemetry
- Ops documentation for healthcare and government customers

**Deal impact:** $100K+ ACV per customer. Self-hosted unlocks $1M+ ARR from regulated sectors.

### Vertical-specific compliance templates
**RFP signal:** 35% of RFPs. No competitor does this well — unique moat opportunity.

**Why:** Healthcare (HIPAA), finance (PCI-DSS), and government (FedRAMP) each need pre-built policy sets. Today every customer hand-configures policies. Templates let sales say "HIPAA-ready out of the box."

**Scope:**
- Healthcare template: SSN/MRN PII rules, PHI keyword list, audit retention 7 years, model allowlist (no external fine-tunes)
- Finance template: PCI credit card regex, trade compliance keywords, SOX audit export format
- Government template: FedRAMP-aligned security headers, US-only provider keys, classified keyword blocking
- `POST /api/v1/orgs/{id}/apply-template` endpoint + admin console "Quick Setup" wizard

**Deal impact:** $75K+ per healthcare customer, $50K+ per finance customer.

### Usage-based billing metering
**Why:** Enterprise customers expect pay-per-token pricing or hybrid models. Stripe supports metered billing natively.

**Scope:**
- Periodic job (hourly) syncs aggregated token usage to Stripe usage records
- New plan tier option: "metered" with per-token pricing
- Dashboard shows usage vs included quota with overage projection
- Invoice line items show token breakdown by model

**Files:** Extend `billing_service.py`, new `metering_service.py`, Stripe usage record API.

### Multi-tenant RLS audit
**Why:** Every enterprise sales conversation asks "how do you isolate our data?" Application-level `org_id` filtering exists, but PostgreSQL RLS is defense-in-depth and produces audit evidence for SOC 2 CC6.3.

**Scope:**
- Enable RLS on `request_logs`, `api_keys`, `llm_provider_keys`, `webhook_deliveries`
- `SET LOCAL app.current_org_id = ?` per transaction
- Verification script proving cross-org access is impossible
- PDF/CSV evidence report for auditors

**Files:** Alembic migration, `backend/app/database.py` session hook, verification test suite.

### Team/project scoping
**Why:** Larger customers need to group users and attribute costs to departments. `x-openproxy-labels` handles chargebacks today but lacks first-class entities for budgets and key isolation.

**Scope:**
- New `teams` table: org_id, name, budget_monthly_usd
- Users belong to one or more teams; API keys scoped to a team
- Team-level rate limits and budget caps
- Dashboard filter by team; cost breakdown in analytics

---

## P2 — Competitive differentiators (win bake-offs)

### Model A/B testing & canary deployments
**RFP signal:** 28% of RFPs. Portkey and Kong offer it. No mainstream gateway does it natively with quality tracking.

**Scope:**
- New `experiments` table: name, model variants with traffic weight
- Gateway routes requests by experiment weights
- Per-variant metrics: latency, cost, token usage, policy violation rate
- Admin console page to create/stop experiments and view results
- Optional: quality scoring via LLM-as-judge

### Adaptive load balancing
**Why:** Bifrost and Portkey recompute provider weights dynamically (every 5s) based on latency and error rates. Static weights mean a degraded provider keeps getting traffic.

**Scope:**
- Background job samples recent latency and error rates per provider key
- Adjusts effective weights: healthy keys get more, degraded keys get less
- Configurable sensitivity and floor (minimum weight)
- Dashboard shows real-time provider health

### Circuit breaker
**Source:** Portkey pattern — stops routing to a provider when failure rate exceeds threshold.

**Scope:**
- Per-provider-key `failure_threshold`, `failure_threshold_percentage`, `cooldown_interval`
- When open, skip key in fallback chain until cooldown expires
- Complements adaptive load balancing

### Prompt management & versioning
**Why:** Portkey Studio and Braintrust Loop offer prompt registries. Teams need version-controlled prompts with rollback, not just a playground.

**Scope:**
- `prompt_templates` table: name, version, system message, user template, variables schema
- API: `POST /v1/chat/completions` accepts `prompt_id` + `variables` instead of raw messages
- Version history with diff view in admin console
- Promote/rollback controls

### Session/trace grouping
**Source:** Helicone Sessions — group related LLM calls for agent trace visibility.

**Scope:**
- Accept `x-openproxy-session-id` (and optional path/name)
- Store in `request_logs`; dashboard filter by session
- View multi-step agent traces as a single unit

### Per-request config overrides
**Source:** Portkey `x-portkey-*` headers — routing, retries, and overrides from HTTP headers.

**Scope:**
- `x-openproxy-retries`, `x-openproxy-fallback-model`, `x-openproxy-cache` headers
- Per-request overrides without changing org config

---

## P3 — Future moat

### MCP gateway (tool calling governance)
**RFP signal:** 12% today, projected 40% by year-end as agent frameworks mature. AWS Bedrock AgentCore and Envoy AI Gateway already support it.

**Scope:** Optional MCP proxy so agents call tools through the gateway with policy enforcement, audit logging, and rate limiting on tool calls.

### Voice endpoint
`POST /v1/audio/transcriptions` — Whisper with the same auth/policy/audit pipeline. Enables voice-first enterprise use cases (call centers, field workers).

### WASM plugin system
Customer-written `before_request` / `after_request` hooks compiled to WebAssembly. Runs sandboxed in the request pipeline. Enables custom transformations without forking the gateway.

### Vault / external secrets
Support fetching provider keys from HashiCorp Vault instead of DB. Enterprise ask for regulated industries with centralized secret management.

### Eval scores API
`POST /api/v1/requests/{id}/scores` — submit numeric/boolean eval metrics per request. Dashboard trends over time. Pattern from Helicone.

---

## Operational improvements (low effort, high polish)

| Item | Source | Scope |
|---|---|---|
| Batched spend writes | LiteLLM | Redis queue → PostgreSQL flush every 60s. Reduces DB write load at scale. |
| Provider health check job | LiteLLM | APScheduler pings provider keys, marks unhealthy. Feeds adaptive load balancing. |
| Weekly/monthly spend reports | LiteLLM | Slack or email digest per org. |
| Key rotation scheduler | LiteLLM | Auto-rotate provider keys on interval. |
| Drop-in base URL docs | Bifrost | Document `base_url` swap for OpenAI/Anthropic SDKs — zero code change migration. |
| Router strategies | LiteLLM | Pluggable: `lowest_latency` (p95), `simple_shuffle` (current), `round_robin`. |

---

## What NOT to build (and why)

| Temptation | Why skip it |
|---|---|
| Fine-tuning management | Out of scope — gateways route, they don't train. Customers use their own pipelines. |
| Agent orchestration | LangChain/CrewAI territory. The gateway should be a dumb pipe with smart policies. |
| Image/video generation proxy | Different latency profile, different billing model. Revisit only if customers ask. |
| Custom LLM hosting | The value prop is provider-agnostic routing, not competing with Replicate/Together. |
