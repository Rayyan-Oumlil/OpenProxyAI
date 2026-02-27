# OpenProxyAI — Documentation

**Enterprise-Grade AI Control Plane**
*A security-first LLM proxy for regulated industries — finance, healthcare, government.*

---

## What Is OpenProxyAI?

OpenProxyAI sits between your organization and every LLM provider (OpenAI, Anthropic, Azure, Mistral, etc.). Every AI request flows through it. This gives you:

- **One API key** for all providers — no vendor lock-in
- **Full audit trail** — who asked what, when, with what response, at what cost
- **Policy enforcement** — PII redaction, content filtering, model allowlists
- **Cost control** — per-user budgets, department chargebacks, real-time spend tracking
- **Compliance** — immutable logs, SOC 2 / HIPAA / GDPR ready

Target customers: CISOs and IT teams at banks, hospitals, and government agencies who need AI governance but cannot risk compliance violations.

---

## Documentation Map

### Strategy & Vision
| Document | What it covers |
|---|---|
| [Executive Summary](./00_EXECUTIVE_SUMMARY.md) | Problem, solution, market, business model, revenue targets |
| [Product Vision](./02_Product_Vision/product_vision.md) | Market opportunity, competitive positioning, long-term vision |
| [Business Model & Pricing](./07_Business_Model/pricing_strategy.md) | Pricing tiers, unit economics, LTV:CAC, revenue projections |

### Architecture & Technical Design
| Document | What it covers |
|---|---|
| [System Architecture](./03_System_Architecture/system_architecture.md) | Full technical design, component diagram, data flows, stack decisions |
| [API Design](./05_API_Design/api_reference.md) | OpenAI-compatible API reference, auth, error handling, rate limiting |
| [Security & Compliance](./04_Security_Compliance/security_architecture.md) | Zero Trust, SOC 2, HIPAA, GDPR, PII detection, audit logging |
| [End-User Integration](./10_End_User_Integration/01_traffic_redirection_guide.md) | IT admin guide — PAC files, DNS, firewall, TLS inspection, browser extensions |

### Build Plan
| Document | What it covers |
|---|---|
| [Phase 1 MVP Roadmap](./06_Product_Roadmap/phase_1_mvp.md) | Week-by-week build plan, must-have features, first customer milestone |
| [First 90 Days](./01_Getting_Started/first_90_days.md) | Day-by-day action plan from zero to first paying customer |
| [Resources & Build Plan](./11_Resources_And_Build_Plan/01_resources_and_build_plan.md) | OSS ecosystem map (LiteLLM, Portkey, Helicone), tech stack, 3-phase build |

### Operations
| Document | What it covers |
|---|---|
| [Solo Founder Playbook](./08_Solo_Founder_Playbook/solo_founder_guide.md) | Time management, priorities, sustainable pace, when to hire |
| [Marketing Website](./09_Marketing_Website/relume_prompt.md) | Relume AI builder prompt for the 15-page enterprise marketing site |

---

## Architecture at a Glance

```
Developer / Employee
        │
        ▼
OpenProxyAI Gateway  (your server)
        │
  ┌─────┴──────────────────────────────────┐
  │  1. Auth       — validate API key      │
  │  2. Rate Limit — check Redis quotas    │
  │  3. Policy     — PII scan, guardrails  │
  │  4. Forward    — route to LLM provider │
  │  5. Log        — async audit log       │
  └─────┬──────────────────────────────────┘
        │
        ├──► OpenAI
        ├──► Anthropic
        ├──► Azure OpenAI
        └──► Mistral / Cohere / Groq / ...
```

**The pipeline always runs in this order.** Every request is checked, forwarded, and logged. Logging is always async — it never slows down the response.

### Stack (settled decisions)

| Layer | Choice | Why |
|---|---|---|
| Proxy engine | FastAPI + Python | Async, LiteLLM integrates natively, Presidio for PII |
| LLM abstraction | LiteLLM | 100+ providers, token counting, cost calculation built-in |
| Database | PostgreSQL | Audit logs, org/user data, ACID guarantees |
| Analytics (scale) | ClickHouse | Append-only time-series at 10M+ requests/month |
| Cache / Rate limit | Redis | Sub-ms rate limiting, session storage |
| Auth | Custom API keys → Auth0 | Start simple, add SSO (SAML/OIDC) in Phase 2 |
| PII detection | Microsoft Presidio | Best open-source NER/PII library |
| Admin dashboard | React + Vite + shadcn/ui | Already built for marketing site, reuse |
| LLM observability | Langfuse | Open-source, self-hostable, Langfuse-compatible export |
| Metrics | Prometheus + Grafana | Industry standard |
| Deploy (Phase 1) | Docker Compose | Simple, customer can self-host |
| Deploy (Phase 3) | Kubernetes | When scale demands it |

---

## Current Status

| Area | Status |
|---|---|
| Marketing website | Built (`web-app/`) — React + Vite, 9 sections, deployed |
| Documentation | Complete (this folder) |
| Reference repos | Cloned (`references/`) — LiteLLM, Portkey, Bifrost, Helicone, Envoy |
| Backend proxy | **Not started** — Phase 1 starts now |
| Admin dashboard | Not started — Week 7 of Phase 1 |
| SDK | Not started — Week 10 of Phase 1 |

---

## Key Architecture Decisions (with rationale)

These were settled after studying LiteLLM, Portkey, and Helicone source code directly.

### 1. Async logging — never block the response
Helicone's `ProxyRequestHandler.ts` is the reference implementation. They wrap the response body in a `ReadableInterceptor` that captures the stream in background while simultaneously passing it to the client. The `DBLoggable` object is created immediately but `.log()` is called only after the stream completes — completely non-blocking.

**Decision:** All audit logging is fire-and-forget via background task. The proxy response latency must never increase due to logging.

### 2. Hook system for guardrails — not inline code
Portkey's `middlewares/hooks/` implements `beforeRequestHooks` and `afterRequestHooks`. Each hook is an independent function that receives the request context, runs its check (PII scan, content filter, keyword block), and returns pass/fail. This is cleaner than embedding all guardrail logic in the main proxy handler.

**Decision:** Build a `hooks/` module from day one with `before_request` and `after_request` hook interfaces. PII detection, content filtering, and DLP are all hooks — not inline code.

### 3. Don't build LiteLLM's proxy — use LiteLLM as a library
LiteLLM's `proxy_server.py` is 508KB. It tries to do everything. It is enormously complex and has grown organically over years. The right approach is to use `litellm.acompletion()` as the forwarding call inside your own clean FastAPI app — not to fork or replicate their proxy server.

**Decision:** LiteLLM is a dependency (`pip install litellm`), not architecture to copy. Your proxy calls `litellm.acompletion(**body)` in one line. Everything else (auth, logging, hooks) is your code.

### 4. PostgreSQL for Phase 1, ClickHouse for Phase 3
Helicone uses **ClickHouse** for request logs. PostgreSQL is fine up to ~1M requests/month but becomes slow for analytical queries at scale (aggregate cost by model across 10M rows). ClickHouse is an append-only columnar store that handles this in milliseconds.

**Decision:** Start with PostgreSQL (simpler). Add ClickHouse in Phase 3 when you have paying customers generating volume. Keep the log schema identical so migration is a copy operation.

### 5. Router pattern for multi-provider fallback
LiteLLM's `route_llm_request.py` shows a clean pattern: a `Router` object holds all model configs and handles fallbacks, retries, and aliases. Instead of `if model == "gpt-4o": call_openai()`, you configure a router and call `router.acompletion(model="gpt-4o", ...)` — the router handles all the edge cases.

**Decision:** Wrap LiteLLM's Router in your own `LLMService` class. This gives you one place to configure all provider credentials, fallbacks, and model aliases.

### 6. Config in database, not headers
Portkey passes routing config via `x-portkey-config` request headers. This is elegant for a stateless edge deployment (Cloudflare Workers) but not right for enterprise on-prem. Enterprise customers need IT admins to configure policy centrally, not developers to set headers per-request.

**Decision:** All org config (model allowlist, rate limits, PII policy, budget caps) lives in PostgreSQL and is loaded at request time via the API key lookup. No config headers needed.

---

## Milestones

| When | Milestone |
|---|---|
| Week 4 | First proxied request through your server |
| Week 8 | First design partner using it in production |
| Week 12 | Admin dashboard live, first paying customer |
| Month 8 | SOC 2 Type I certified |
| Month 12 | $500K ARR |
| Month 18 | $2M ARR, Series A ready |

---

*Last updated: February 2026 — after studying LiteLLM, Portkey Gateway, and Helicone source code.*
