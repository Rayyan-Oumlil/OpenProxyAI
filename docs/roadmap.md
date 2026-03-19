# OpenProxyAI — Roadmap

> **Shipped inventory:** [features.md](./features.md). **Below:** reference analysis (how we chose priorities), then go-live blockers, then P1–P3 backlog and operational polish.
>
> Last updated: 2026-03-19
>
> **Reality check:** Several things competitors bundle (semantic cache, compliance templates, experiments, Tier-1 data residency, metered Stripe billing) are already shipped — see [features.md](./features.md). The build sections here are **only** what is still worth doing or hardening.

---

## Reference analysis

Architecture and feature patterns from competitor projects studied during planning. This section **drives RFP-weighted prioritization** in P1–P3 below.

### Competitor stack summary

| Project | Stack | Notable patterns |
|---|---|---|
| **LiteLLM** | Python, FastAPI, DualCache (mem+Redis), Prisma | Proxy hooks (CustomLogger), DBSpendUpdateWriter (batch spend 60s), router strategies (lowest_latency, simple_shuffle), many proxy endpoints (/v1/messages, /v1/images, /v1/batches, etc.), Redis/GCS/S3/Qdrant semantic cache |
| **Portkey Gateway** | TypeScript, Hono, Workers/Node | tryTargetsRecursively fallback, HookSpan/HooksManager (before/after, Guardrail vs Mutator), plugin registry (aporia, patronus, etc.), config from headers, circuit breaker |
| **Bifrost** | Go, 11 µs overhead | Semantic cache, MCP gateway, adaptive load balancing, Vault, plugins (governance, logging, semanticcache), NPX zero-config, Web UI |
| **Helicone** | NextJS, Worker, Express, Supabase, ClickHouse | Sessions (agent trace grouping), Scores API for evals, Playground, prompt versioning, real-time webhooks, Datasets + RAGAS |
| **Envoy AI Gateway** | Go, Kubernetes Gateway API | AIGatewayRoute CRD, routing by x-ai-eg-model header, LLMRequestCosts in metadata, external processor (WASM-capable) |

### Competitive landscape (March 2026)

**Market bifurcation:**

1. **Performance / developer-focused** (Helicone, LiteLLM, Envoy) — speed, open-source, DX  
2. **Enterprise / compliance-focused** (Portkey, Kong, Azure) — governance, audit trails, regulatory  
3. **Niche specialists** (Braintrust, LangSmith, Martian) — observability + evals, semantic routing  

**Key threat:** Cloud providers (Azure, AWS) bundling LLM gateway features for free. **Mitigation:** stay multi-cloud and provider-agnostic.

**OpenProxyAI positioning:** *Compliance-first, cost-optimized AI gateway* — between Portkey’s feature breadth and Helicone’s performance minimalism. Differentiate on **vertical compliance templates** (healthcare / finance / gov) that most competitors do weakly.

### Top deal closers by RFP frequency

Statuses reflect [features.md](./features.md) (shipped vs partial vs not started), not old placeholder roadmap labels.

| Feature | % of enterprise RFPs | OpenProxyAI status | ACV impact |
|---|---|---|---|
| Data residency / on-prem | 65% | **Tier 1 shipped** (org `data_region` + provider `region` routing). **Tier 2** = self-hosted / air-gap (**P1** below) | $100K+ blocker |
| Semantic caching | 58% | **Shipped** (L1/L2/L3 + `x-openproxy-cache`, dashboard metrics) | $50K+ cost justification |
| Prompt versioning & A/B testing | 42% | **Partial:** prompt templates + versioning in admin/playground **shipped**; **model A/B experiments** **shipped**; **not yet:** `prompt_id` + `variables` on `POST /v1/chat/completions` (**P2** below) | $20K+ feature request |
| Vertical compliance templates | 35% | **Shipped** (HIPAA / PCI-DSS / FedRAMP apply + templates API) | $75K+ for healthcare |
| Canary deployments | 28% | **Largely shipped** via **experiments** (weighted variants, metrics). **P2** follow-up: quality scoring / LLM-as-judge | $15K+ feature request |
| MCP / tool governance | 12% | **P3** below | Emerging |

---

## Blocking: Go-live

| Item | What's needed | Time estimate |
|---|---|---|
| Public deployment | Create DOKS cluster, provision managed DB/Redis, configure DNS, set GitHub secrets. All code is done. See `plans/public-deployment.md` | ~1 hour of infra work |
| Stripe keys | Create Stripe products/prices, set env vars in production. All code is done. See `docs/guides/stripe-setup.md` | ~30 min |

Everything below is post-launch, prioritized by competitive gap and revenue impact.

---

## P1 — Revenue accelerators (directly close deals)

### Data residency — Tier 2 (self-hosted / air-gap)
Tier 1 (org `data_region` + provider key `region` filtering) is shipped; a **Helm chart** for cloud deploy also exists — see [features.md](./features.md). Tier 2 is **not** “chart vs no chart”; it is **customer-controlled** infra:

**Scope:**
- Hardening + documented path for **customer-cluster** install (no managed dependency assumptions)
- Air-gapped mode: license key validation, no outbound telemetry
- Ops / security documentation for healthcare and government evals

**Deal impact:** Self-hosted unlocks $1M+ ARR from regulated sectors.

### Team follow-ups (teams entity is shipped)
**Why:** [Teams](./features.md) (CRUD, members, budgets, admin UI) are live. Larger accounts still want **keys and analytics** tied to teams.

**Scope:**
- Optional `team_id` on gateway API keys; validate user membership when issuing
- Dashboard / analytics filters and cost breakdown by team
- Optional team-level rate limits and stricter budget caps (beyond org budget)

---

## P2 — Competitive differentiators (win bake-offs)

### Experiment quality scoring (optional)
**RFP signal:** A/B testing is [shipped](./features.md); differentiation moves to **quality**, not presence of the feature.

**Scope:** LLM-as-judge or external eval hooks on experiment results; compare variants on rubric scores, not just latency/cost/tokens.

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

### Prompt management — proxy integration (templates exist)
**Why:** [Prompt templates](./features.md) (CRUD, versioning, playground) are **already shipped**. The gap vs Portkey/Braintrust is **production traffic**: callers still send raw `messages`; there is no `prompt_id` on the OpenAI-compatible proxy.

**Scope:**
- `POST /v1/chat/completions` (and optionally embeddings): accept `prompt_id` + `variables`, resolve template server-side, then same policy/audit pipeline
- Optional: promote/rollback UX and diff view beyond current version list API

### Session/trace grouping
**Source:** Helicone Sessions — group related LLM calls for agent trace visibility.

**Scope:**
- Accept `x-openproxy-session-id` (and optional path/name)
- Store in `request_logs`; dashboard filter by session
- View multi-step agent traces as a single unit

### Per-request config overrides (finish header surface)
**Source:** Portkey `x-portkey-*` headers — routing, retries, and overrides from HTTP headers.

**Already shipped:** `x-openproxy-cache`, `x-openproxy-labels`, `x-openproxy-team-id` (see [features.md](./features.md)).

**Scope (remaining):**
- `x-openproxy-retries`, `x-openproxy-fallback-model` (and any other high-value overrides you want to document)
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
