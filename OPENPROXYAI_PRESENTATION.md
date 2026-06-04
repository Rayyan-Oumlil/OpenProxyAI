# OpenProxyAI — Project Presentation

## Key Terms (Quick Reference)

| Term | Plain-English Definition |
|------|--------------------------|
| **LLM** | Large Language Model — the AI brain behind tools like ChatGPT, Claude, etc. Takes text in, produces text out. |
| **API** | Application Programming Interface — a way for software to talk to other software. Like a waiter taking your order to the kitchen. |
| **API Key** | A secret password that identifies who is making a request to a service. |
| **Proxy / Gateway** | A middleman that sits between a user and a service. Every request passes through it, so it can inspect, log, block, or reroute. |
| **Provider** | A company that runs an LLM (OpenAI, Anthropic, Azure, Mistral, Google, etc.). |
| **Token** | The unit LLMs use to measure text. Roughly 1 token ≈ ¾ of a word. Providers charge per token. |
| **Streaming** | Sending the AI response word-by-word as it's generated, instead of waiting for the full answer. Feels faster to the user. |
| **PII** | Personally Identifiable Information — names, emails, phone numbers, SSNs. Regulated data that shouldn't be sent to external AI. |
| **Prompt Injection** | A trick where a user hides malicious instructions inside their input to make the AI do something unintended. |
| **Rate Limiting** | Capping how many requests a user can make per minute/hour/day to prevent abuse or runaway costs. |
| **Webhook** | An automatic notification sent to another system when something happens (e.g., "budget exceeded" triggers an alert to Slack). |
| **Cache** | Storing a previous answer so the same question doesn't need to be re-asked (and re-paid for) to the AI provider. |
| **Semantic Cache** | A smarter cache that recognizes "What is 2+2?" and "What's two plus two?" are the same question, using vector similarity. |
| **SOC 2 / HIPAA / GDPR** | Compliance standards. SOC 2 = security controls for SaaS. HIPAA = healthcare data protection. GDPR = EU privacy law. |
| **SSO / OIDC** | Single Sign-On / OpenID Connect — lets employees log in with their company account (Google, Okta, etc.) instead of a separate password. |
| **RBAC** | Role-Based Access Control — admins can do everything, developers can use the API, viewers can only read dashboards. |
| **Latency** | How long it takes from sending a request to getting a response. Lower = better. |
| **TTFT** | Time To First Token — how long until the first word of the AI response appears. Key metric for streaming. |
| **Fallback** | If Provider A fails, automatically retry with Provider B. Only done for temporary errors (overload, outage), not permanent ones (bad request). |
| **Materialized View** | A pre-calculated summary table in the database. Dashboard queries read this instead of scanning millions of raw rows — makes charts load instantly. |
| **Docker / Kubernetes** | Docker = packages the app so it runs the same everywhere. Kubernetes = orchestrates many Docker containers at scale in production. |
| **CI/CD** | Continuous Integration / Continuous Deployment — automated pipelines that test and deploy code every time a change is pushed. |
| **Air-Gap Mode** | Running the system completely offline with no external connections — required by some government and military customers. |

---

## 1) What Is OpenProxyAI?
OpenProxyAI is a secure **gateway** (middleman) between a company and AI providers (OpenAI, Anthropic, Azure, Mistral, and others).

Instead of every team using different keys, tools, and rules, OpenProxyAI gives one controlled entry point:
- One **API** (programmatic interface) for many AI providers
- Central security and **compliance** (meeting legal/regulatory requirements) rules
- Cost and usage control
- Full **audit** (who did what, when, and how much it cost) visibility

In simple terms: it is the "control tower" for enterprise AI usage.

---

## 2) Why This Product Exists (The Core Problem)
When companies adopt AI quickly, they usually face these issues:
- No central visibility of who used what model and at what cost
- Risk of sensitive data leakage
- Difficult **compliance reporting** (SOC 2 = security audit standard, HIPAA = healthcare data law, internal audits)
- Budget surprises from uncontrolled usage
- Hard to standardize teams on secure best practices

OpenProxyAI solves this by adding **governance** (rules and enforcement) and **observability** (seeing what's happening in real time) without forcing teams to stop using modern AI tools.

---

## 3) What Is Already Implemented (Shipped)

### A) AI Gateway + Multi-Provider Routing
- **Chat completions** (send a prompt, get a response) and **embeddings** (convert text to numbers for search/comparison) endpoints
- **Streaming** (word-by-word delivery) and non-streaming responses
- Multi-provider support through **LiteLLM** (open-source library that speaks to 100+ AI providers)
- Weighted **provider key rotation** (spread requests across multiple API keys to avoid hitting limits)
- **Retry/fallback** logic for upstream failures (if Provider A is down, automatically try Provider B)
- OpenAI-compatible model listing endpoint

### B) Security and Policy Controls
- **API key authentication** (every request proves who it is) + **JWT** (JSON Web Token — a signed login session) admin authentication
- **RBAC** — Role-based access control (admin = full access, developer = use the API, viewer = read-only dashboards)
- **Policy engine** with modes: off, log_only, enforce — controls what users are allowed to do
- **Model allowlists** (only let employees use approved AI models)
- **Blocked keyword checks** (reject requests containing forbidden terms like "drop table")
- **PII detection** (catches names, emails, SSNs before they're sent to an AI provider) and optional response redaction
- **Prompt injection detection** (catches attempts to trick the AI) with ML model + regex fallback

### C) Cost and Rate Governance
- **Rate limits**: requests/min and **tokens**/min caps (tokens ≈ words — the unit AI providers charge by)
- Daily **budget guardrails** (automatically blocks requests when spending hits the limit — returns HTTP 402 "Payment Required")
- Per-user budget limits
- Per-model and per-team limits
- **Budget alert webhooks** (sends an automatic notification to Slack/email when spend crosses a threshold)
- **Cost anomaly detection** (flags unusual spending spikes — e.g., "Engineering spent 3x their normal daily amount")
- Spend report support

### D) Teams and Organization Controls
- Team **CRUD** (Create, Read, Update, Delete) and membership management
- Team-level budget support (each department gets its own spending limit)
- Team-level analytics visibility (each team sees only their own usage)
- Team context propagation through API keys (the system knows which team made each request)

### E) Prompt Playground and Experimentation
- **Prompt Playground** — a sandbox where you type a prompt and compare how different AI models respond side-by-side (speed, cost, quality)
- **Prompt templates** — reusable prompts with variables (e.g., "Summarize this {{document}} for a {{audience}}")
- **A/B model experiments** — send 50% of traffic to GPT-4 and 50% to Claude, then compare which performs better
- Experiment metrics and quality scoring support

### F) Caching and Performance
- **3-tier cache** (store previous answers so the same question doesn't cost money twice):
  - **L1** — in-memory (fastest, lives inside the app)
  - **L2** — **Redis** (fast key-value store shared across servers, exact text match)
  - **L3** — **semantic cache** using **pgvector** (recognizes that "What is 2+2?" and "What's two plus two?" are the same question — uses vector math, not exact text)
- **Cache hit tracking** (how often cached answers are reused) and token savings metrics
- **TTFT** (Time To First Token — how fast the first word appears) and **latency** (total response time) metrics

### G) Billing and Commercial Readiness
- **Stripe** (payment processor) checkout and customer portal flows
- **Webhook** processing with **idempotency** safeguards (if the same payment notification arrives twice, it's only processed once)
- **Plan-based feature gating** (Starter plan gets fewer features than Enterprise plan)
- Optional **metered billing** — sync actual token usage to Stripe so customers pay for what they use

### H) Observability, Audit, and Compliance
- Full **request logging** (every AI request is recorded: who, what model, how many tokens, cost, time)
- Policy violation analytics and exports
- **Compliance-oriented reporting** (CSV/JSON exports for auditors)
- Optional integrations: **Prometheus** (real-time metrics), **Langfuse** (AI-specific tracing), **ClickHouse** (analytics database for millions of rows)
- **Compliance templates** — pre-built policy bundles: HIPAA (healthcare), PCI-DSS (payments), FedRAMP (US government)

### I) Deployment and Platform
- **Docker Compose** (packages the entire app so it runs identically on any machine) for local deployment
- **Helm chart** for **Kubernetes** (orchestration system that manages the app at scale in the cloud) deployment
- **CI/CD** (Continuous Integration / Deployment — automated pipelines that test and deploy code on every change) via GitHub Actions
- **Air-gap mode** (runs fully offline with zero external connections — required by some government/military customers)

---

## 4) How It Works (Simple Flow)
For each AI request, OpenProxyAI follows this sequence:

1. Authenticate user/key
2. Apply rate limits and budget checks
3. Apply policy checks (PII, model rules, guardrails)
4. Check cache for reusable results
5. Route to the best provider/model path
6. Return result to client
7. Log usage and metadata for audit and analytics

This design keeps latency practical while enforcing enterprise controls.

---

## 5) Current Product Value (Business + Technical)

### Business Value
- Reduces compliance and legal risk
- Makes AI costs predictable and controllable
- Speeds up enterprise AI adoption by standardizing access
- Creates a strong foundation for offering AI governance as a product

### Technical Value
- Clear separation between core request path and **sidecar** (optional add-on services that can fail without breaking the main system) integrations
- **Scalable architecture** — Redis (fast cache), PostgreSQL (main database), optional ClickHouse (analytics at scale)
- Strong **auditability** — every action is logged and traceable, which enterprise procurement and security teams require before buying
- Already validated by a large **test suite** (600+ automated tests that verify the system works correctly)

---

## 6) Realistic Use Cases Right Now
- A company wants all internal AI traffic controlled in one place
- Security team needs PII/policy guardrails before AI responses are returned
- Finance team wants hard budget limits and anomaly detection
- Engineering needs **provider failover** (if OpenAI goes down, traffic automatically switches to Anthropic) and **model routing** without rewriting apps
- Compliance team needs logs and reports for audits

---

## 7) Built on Proven Patterns (Reference Architecture)

OpenProxyAI was not built from scratch assumptions. Every major architectural decision was derived from reading the source code of five production LLM gateways, extracting what works, and discarding what doesn't.

### Influence Breakdown

| Reference Project | Influence | What We Took | What We Avoided |
|-------------------|-----------|--------------|-----------------|
| **LiteLLM** | ~42% | Provider abstraction (`acompletion`/`aembedding` as library calls), cost calculation, 3-tier cache (extended from their DualCache), streaming error peek | Their 508KB monolith `proxy_server.py` — we keep handlers under 50 lines |
| **Portkey** | ~28% | Hook system (`before_request`/`after_request` guardrails), thin handler pattern, selective fallback only on transient errors (429/5xx) | Falling back on all errors — retrying a 400 or 401 is wasted latency |
| **Helicone** | ~22% | Async fire-and-forget logging, ClickHouse for OLAP analytics, materialized views for dashboard performance | Blocking the response path with logging — our audit log never adds latency |
| **Bifrost** | ~8% | Gateway vs. provider error distinction (`X-OpenProxyAI-Gateway-Error` header) — critical for correct fallback and alerting | — |
| **Envoy AI Gateway** | Deferred | WASM plugin system planned for Enterprise Phase 4 | Premature complexity — not needed until custom per-org request mutation is required |

### Code Impact (Backend: ~14,000 lines)

| Pattern Source | Key Files | Lines | % of Backend |
|----------------|-----------|-------|--------------|
| LiteLLM | `llm_service.py`, `cache_service.py`, `cost_tracker.py` | ~2,100 | 15% |
| Portkey | `policy_service.py`, `rate_limiter.py`, fallback logic | ~1,300 | 9% |
| Helicone | `audit_logger.py`, `clickhouse_service.py`, `analytics_service.py` | ~1,100 | 8% |
| Bifrost | Error headers + fallback gating in `proxy.py` | ~65 | 0.5% |
| **Total reference-derived** | **20+ files** | **~4,600** | **33%** |

The remaining 67% is OpenProxyAI-original: auth/RBAC, teams, experiments, Stripe billing, compliance templates, admin console, deployment, and the full test suite (600+ tests).

### Why This Matters

1. **Not reinventing the wheel** — Provider routing, cost tracking, and async logging are solved problems. We adopted proven patterns instead of guessing.
2. **Anti-patterns documented** — We studied what went wrong in each project (LiteLLM's monolith, Portkey's over-eager fallback) and explicitly avoided those mistakes.
3. **Every decision has a source** — 13 Architecture Decision Records (ADRs) cite specific source files from reference implementations. This is auditable engineering, not "inspired by" hand-waving.

---

## 8) Future Roadmap (Planned, Not Yet Shipped)
These are planned backlog items:
- **MCP gateway** (Model Context Protocol — lets AI models use external tools like databases, calendars, search)
- **Voice endpoint** (speech-to-text / text-to-speech proxy — talk to AI instead of typing)
- **WASM plugin system** (WebAssembly — lets customers write custom logic that runs inside the gateway safely)
- **External secret manager** integrations (e.g., HashiCorp Vault — enterprise-grade key storage instead of environment variables)
- Standalone **evaluation API** (score AI response quality at scale, beyond the current experiment scoring)

---

## 9) One-Sentence Summary for Presentation
OpenProxyAI is an enterprise AI control plane that makes AI usage secure, auditable, and cost-controlled while staying compatible with modern provider ecosystems.

---

## 10) Tough Questions & Answers

### "What does it actually do? Explain it simply."

It's a middleman between a company and AI services like ChatGPT. Every AI request goes through OpenProxyAI first. That lets the company control who uses what, how much they spend, and make sure no sensitive data leaks out. Think of it like a corporate firewall, but specifically for AI.

### "Why wouldn't a company just use ChatGPT directly?"

They can — for one team. But when 200 employees across 10 departments all use AI differently, you get:
- No idea who spent what (surprise $50K bills)
- No way to stop someone from sending patient records or financial data to OpenAI
- No audit trail for compliance (SOC 2, HIPAA require it)
- No ability to switch providers without rewriting every app

OpenProxyAI solves all four. One key, one dashboard, full control.

### "Who are your competitors?"

| Competitor | What They Do | OpenProxyAI's Edge |
|------------|-------------|-------------------|
| **Portkey** | LLM gateway, mostly developer-focused | We target regulated enterprises (healthcare, finance, government) with compliance templates and audit immutability |
| **Helicone** | Logging and observability for LLM calls | They observe — we observe AND enforce (PII blocking, budget limits, policy guardrails) |
| **LiteLLM Proxy** | Open-source LLM proxy server | Their proxy is a 508KB monolith. We use LiteLLM as a library and built a clean, auditable layer on top |
| **Cloudflare AI Gateway** | CDN-level AI proxy | Basic caching and logging only. No policy engine, no compliance, no PII detection |

The gap: nobody combines gateway + policy engine + compliance + billing in one product for regulated industries.

### "How do you make money?"

SaaS subscription, tiered by org size:

| Plan | Price | Users | Target |
|------|-------|-------|--------|
| Starter | $2,500/mo | Up to 50 | Small teams adopting AI |
| Growth | $7,500/mo | Up to 200 | Mid-market with compliance needs |
| Enterprise | $25,000+/mo | Unlimited | On-premise, custom SLAs, dedicated support |

Revenue target: $500K ARR Year 1, $5M ARR Year 2. Stripe billing is already integrated and functional.

### "Is anybody paying for this yet?"

Not yet — the product is feature-complete and deployment-ready. Next step is controlled pilots with 2–3 design partners in regulated industries. The goal is to validate pricing and get reference customers before scaling sales.

### "What if OpenAI or Microsoft builds this?"

They won't — it works against their interest. OpenAI wants companies locked into their platform. OpenProxyAI is provider-neutral — it lets companies use OpenAI, Anthropic, Azure, and others simultaneously and switch freely. That's the opposite of what any single provider would build.

Microsoft does have Azure AI Gateway, but it only works with Azure services. Companies using multiple providers (which is most of them) need something vendor-neutral.

### "You built this alone?"

Yes. The codebase is ~14,000 lines of backend Python, a React admin console, Python + TypeScript SDKs, Docker + Helm deployment, and 600+ passing tests. Architecture decisions are backed by competitive teardowns of five production gateways (LiteLLM, Portkey, Helicone, Bifrost, Envoy). Every major decision has a documented rationale.

### "What's the hardest technical problem you solved?"

Three things:

1. **Streaming without blocking** — AI responses stream token-by-token. Logging, policy checks, and cost tracking all happen without adding a single millisecond of latency to the user. The first token arrives at the same speed as calling the provider directly.

2. **3-tier semantic cache** — If someone asks "What is 2+2?" and someone else asks "What's two plus two?", the system recognizes they're the same question and returns the cached answer. This uses vector embeddings and cosine similarity — saves tokens and money.

3. **Multi-tenant security** — Every database query is scoped to the requesting org via PostgreSQL Row Level Security. Even a bug in the code can't accidentally leak one customer's data to another.

### "What's your unfair advantage?"

Domain focus. Generic LLM gateways serve developers. OpenProxyAI serves compliance officers, CISOs, and finance teams in regulated industries. The compliance templates (HIPAA, PCI-DSS, FedRAMP), audit immutability, and PII detection aren't afterthoughts — they're core features. That specificity is hard to retrofit into a developer-first tool.

### "What's the risk?"

- **Market timing** — If enterprises slow AI adoption, demand shrinks. Mitigated by the compliance angle: regulation accelerates the need for control planes.
- **Build vs. buy** — Large enterprises might build in-house. Mitigated by offering the product on-premise (Enterprise tier) so it feels like "their" tool.
- **Solo founder** — Bus factor of one. Mitigated by comprehensive docs, 600+ tests, and clean architecture that a new engineer can onboard to quickly.

---

## 11) Optional Live Demo Outline (5–10 min)
If you present this live, use this order:
1. Show dashboard overview (cost, usage, latency)
2. Show policy configuration (model allowlist + PII guardrail)
3. Send a sample chat completion through the gateway
4. Show logs/audit entry for that request
5. Show billing/cost controls and team breakdown
6. Show prompt playground and quick model comparison

This gives both business and technical credibility in one short walkthrough.
