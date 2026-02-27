# OpenProxyAI — Resources & Build Plan

**Founder's Technical Reference**

> A curated map of the open-source ecosystem you're entering, the tools you'll use, and a concrete 3-phase build plan to go from zero to production.

> **Status:** Updated after deep code study of all five reference repos: LiteLLM, Portkey Gateway, Bifrost, Helicone, and Envoy AI Gateway. The reusability analysis below comes from reading the actual source files — not README descriptions.

---

## What You Can Reuse vs. What You Must Build

This is the most important section. Before reading anything else, understand what "reuse" actually means for an LLM proxy.

### Directly Reusable via `pip install`

These are things you install as a Python package and call directly. Zero custom code needed.

| Library | What to use | How to call it |
|---|---|---|
| `litellm` | `litellm.acompletion()` | Your entire provider layer. One call works for OpenAI, Anthropic, Azure, Bedrock, Mistral, Cohere, Ollama, 100+ more. |
| `litellm` | `litellm.completion_cost()` | Pass the response object or `(model, prompt_tokens, completion_tokens)`. Returns exact USD cost. No tiktoken needed. |
| `litellm` | `litellm.Router` | Multi-provider fallback, load balancing, retries, model aliases. Configure a list of providers and call `router.acompletion()`. |
| `litellm` | `CustomGuardrail` base class | Subclass it, implement `async_pre_call_hook` and `async_post_call_success_hook`. Works without the LiteLLM proxy server. |
| `presidio-analyzer` + `presidio-anonymizer` | `analyzer.analyze()` + `anonymizer.anonymize()` | Microsoft's NLP-based PII detection. Finds names, emails, SSNs, phone numbers, medical record numbers. Best open-source PII library. |
| `fastapi` + `uvicorn` | Your ASGI framework | Async, production-grade, LiteLLM integrates natively. |
| `redis` | Rate limiting counters | `INCR` + `EXPIRE` for atomic counters. Sub-millisecond check on every request. |

### Patterns to Copy (Not Install)

These are **concepts and code patterns** from the reference repos. You adapt them in your own code — you don't import them.

| Pattern | Source | What to copy |
|---|---|---|
| Async log after stream | Helicone `ProxyForwarder.ts` | `ctx.waitUntil(log())` → in Python: `background_tasks.add_task(log_request, ...)` called inside the streaming generator after `[DONE]` |
| ClickHouse log schema | Helicone `ClickhouseWrapper.ts` | `RequestResponseRMT` field list: `time_to_first_token`, `reasoning_tokens`, `prompt_cache_read_tokens`, `threat`, `country_code`, `properties`. Use these field names in your Postgres table too. |
| Fallback tree routing | Portkey `tryTargetsRecursively()` | Recursive routing over a config tree. Parent settings (retry, cache, hooks) cascade to children. Children override parents. Only fall back on `onStatusCodes: [429, 500, 502, 503, 504]`. |
| HTTP 446 for policy blocks | Portkey `handlerUtils.ts` | Return 446 (not 400) when a guardrail blocks a request. Include `hook_results` array showing which check failed. |
| Provider error vs gateway error | Bifrost `IsBifrostError` | `X-OpenProxyAI-Gateway-Error: true/false` header. `true` = proxy bug (our fault). `false` = provider failed (their fault). Never fall back on gateway errors. |
| Weighted key selection | Bifrost `WeightedRandomKeySelector` | Multiple API keys per provider, each with a weight. Weighted random pick per request. Set weight=0 to drain a key during rotation. |
| First-chunk error detection | LiteLLM `create_response()` | Peek at first SSE chunk before returning `StreamingResponse`. If it's an error, return `JSONResponse(502)` — prevents `200 OK` with error in stream body. |
| Materialized views for dashboard | LiteLLM `create_views.py` | `mv_daily_spend`, `mv_model_usage` — refresh every 5 min. Dashboard queries hit views, never raw `request_logs`. Keeps dashboard fast even with 10M+ rows. |
| Token-based rate limiting | Envoy AI Gateway, Helicone | Three dimensions: requests/min, tokens/min, dollars/day. All in Redis. `tokens/min` is the real cost control — one GPT-4o call can use 100K tokens. |
| Processor interface (4 methods) | Envoy AI Gateway `processor.go` | `ProcessRequestHeaders`, `ProcessRequestBody`, `ProcessResponseHeaders`, `ProcessResponseBody`. This is the correct abstraction for a middleware pipeline. |

### What You Must Build From Scratch

No reference repo provides this as a reusable library. You design and build it yourself.

| Component | Why it's custom | Estimated complexity |
|---|---|---|
| API key hashing + storage | LiteLLM's is coupled to Prisma/PostgreSQL schema. Use SHA-256 (faster than bcrypt for high-frequency auth). | Medium |
| Org/user/department RBAC | Every project has a different model. Yours is simpler to start: `org → department → user → api_key`. | Medium |
| Budget enforcement per org | All implementations are tied to their own DB schema. Three Redis keys per org: `req_count`, `token_count`, `spend_usd`. | Medium |
| Admin dashboard UI | All dashboards (LiteLLM, Helicone) are tightly coupled to their backend schemas. Build yours on top of your own API. | Hard |
| Traffic redirection (PAC, DNS) | None of these projects do this — it's your unique enterprise value. | Medium (already documented in `docs/10_End_User_Integration/`) |
| SOC 2 audit log schema | Your compliance requirements are specific to regulated industries. | Medium |
| Provider key encryption | Encrypt API keys at rest using `cryptography.fernet`. None of the reference repos publish their key encryption scheme. | Easy |

### What NOT to Copy

| Thing | Why not |
|---|---|
| LiteLLM's `proxy_server.py` architecture | 508KB monolith. Too complex to audit. Use `litellm` as a **library**, not architecture to copy. |
| Portkey's config-via-headers pattern | Right for Cloudflare Workers (stateless). Wrong for on-prem enterprise. Config must be DB-backed. |
| Bifrost's goroutine worker pool | Go-specific. Python's `asyncio` + `aiohttp` connection pooling achieves the same result. |
| Helicone's Cloudflare Durable Objects rate limiter | Cloudflare-specific. Use Redis instead. |
| Helicone's Kafka ingestion pipeline | Kafka adds complexity. Phase 1 logs directly to PostgreSQL. Add Kafka/ClickHouse in Phase 3. |
| Portkey's 70-provider adapter library | Support the 5 providers your enterprise customers actually use. LiteLLM already handles the rest. |
| Envoy AI Gateway CRDs | Kubernetes operator — only relevant when customers want to run OpenProxyAI inside their K8s cluster. Phase 4 feature. |

---

---

## Table of Contents

1. [Tier 1: LLM Proxy / Gateway OSS (Study First)](#1-tier-1-llm-proxy--gateway-oss)
2. [Tier 2: Traditional Proxy Infrastructure](#2-tier-2-traditional-proxy-infrastructure)
3. [Tier 3: Observability Stack](#3-tier-3-observability-stack)
4. [Tier 4: Browser Extension Resources](#4-tier-4-browser-extension-resources)
5. [Recommended Tech Stack](#5-recommended-tech-stack)
6. [Phase 1: Study & Setup (Weeks 1–2)](#6-phase-1-study--setup)
7. [Phase 2: Build MVP (Weeks 3–10)](#7-phase-2-build-mvp)
8. [Phase 3: Production Hardening (Ongoing)](#8-phase-3-production-hardening)
9. [Key Architecture Decisions](#9-key-architecture-decisions)

---

## 1. Tier 1: LLM Proxy / Gateway OSS

These are your **direct competitors and teachers**. Study their code before writing a single line of your own. Understand their architecture, their trade-offs, and where they fall short for enterprise use cases.

### LiteLLM

| | |
|---|---|
| **Repo** | https://github.com/BerriAI/litellm |
| **Language** | Python |
| **Stars** | 33K+ |
| **License** | MIT |

**What it does:** Unified interface for 100+ LLMs. One API call works for OpenAI, Anthropic, Azure, Bedrock, Mistral, Cohere, and more. The most widely used LLM proxy in the ecosystem.

**Why study it:**
- Best-in-class provider abstraction layer
- Excellent cost tracking and token counting
- Has a proxy server mode (`litellm --model gpt-4o`)
- You will likely use LiteLLM as your LLM abstraction layer internally

**Where it falls short (your opportunity):**
- Not security-first (no PII detection, no DLP out of the box)
- No enterprise SSO / SAML
- No immutable audit logs
- Not designed for regulated industries

**What the code actually looks like (read this):**
```
litellm/
├── proxy/
│   ├── proxy_server.py          ← 508KB monolith — DO NOT replicate this pattern
│   ├── route_llm_request.py     ← 450 lines — READ THIS. The Router pattern.
│   ├── litellm_pre_call_utils.py← 73KB pre-processing — shows all edge cases
│   ├── spend_tracking/          ← How they track cost per request
│   ├── guardrails/              ← Their guardrail plugin system
│   ├── auth/                    ← API key validation and team mapping
│   └── middleware/              ← FastAPI middleware layer
├── main.py                      ← Core completion() function — start here
└── utils.py                     ← Token counting, cost calculation
```

**Real code-level findings:**
- `proxy_server.py` is 508KB. It's a cautionary tale — feature bloat from 3 years of growth. Their proxy became a monolith.
- `route_llm_request.py` is the gem. Read it fully. It shows the routing decision tree: team model alias → exact match → wildcard → default deployment → error.
- `litellm.completion_cost(response)` is a one-liner that returns cost in USD. Use it.
- They use a shared `aiohttp` session across requests (connection pool reuse) — important for performance at scale.
- Their `guardrails/` folder is a clean plugin system — each guardrail is independent. Steal this pattern.
- They use Prisma for the DB (not SQLAlchemy) — this is unusual for Python, generates TypeScript-style type-safe queries.

---

### Portkey Gateway

| | |
|---|---|
| **Repo** | https://github.com/Portkey-AI/gateway |
| **Language** | TypeScript (Node.js) |
| **Stars** | 6K+ |
| **License** | MIT |

**What it does:** AI gateway with routing, fallbacks, load balancing, and observability. Cleanest architecture in the space.

**Why study it:**
- Excellent request/response transformation pipeline
- Clean middleware pattern (easy to add your own hooks)
- Good fallback and retry logic
- TypeScript — well-typed, easy to read

**Where it falls short:**
- TypeScript/Node.js (not Python — harder to integrate with Presidio, LiteLLM)
- No enterprise compliance features
- Designed for Cloudflare Workers edge deployment — not on-prem
- Config is passed via request headers (`x-portkey-config`) — not suitable for enterprise DB-backed config

**What the code actually looks like (read this):**
```
portkey-gateway/src/
├── index.ts                 ← 299 lines. READ THIS FIRST. Clean app setup.
├── handlers/
│   └── chatCompletionsHandler.ts ← 57 lines. This is the entire handler.
├── middlewares/
│   ├── hooks/
│   │   └── index.ts         ← HookSpan class. beforeRequestHooks + afterRequestHooks
│   ├── cache/               ← Response caching middleware
│   ├── requestValidator/    ← Input validation
│   └── log/                 ← Request logging
├── providers/               ← Provider-specific adapters (OpenAI, Anthropic, etc.)
└── services/                ← Shared services (cache backends, etc.)
```

**Real code-level findings:**
- `chatCompletionsHandler.ts` is only 57 lines. The handler itself is thin — all logic is in `tryTargetsRecursively()`.
- The hook system (`middlewares/hooks/`) is the cleanest guardrail pattern in any of the reference repos. `HookSpan` runs `beforeRequestHooks` → forward → `afterRequestHooks`. Each hook returns pass/modify/block.
- They use **Hono** (not Express) — a lightweight TypeScript HTTP framework that runs on Cloudflare Workers, Node, Bun, Deno, and AWS Lambda. Fast and minimal.
- Middleware order in `index.ts`: `compress` → `prettyJSON` → `logHandler` → `hooks` → `memoryCache` → route handlers. Note: **hooks run before routing**, which is the correct order for guardrails.
- `constructConfigFromRequestHeaders()` — their config comes from `x-portkey-config` header. Skip this for OpenProxyAI; use DB-backed config instead.

---

### Bifrost

| | |
|---|---|
| **Repo** | https://github.com/maximhq/bifrost |
| **Language** | Go |
| **Stars** | 2K+ |
| **License** | MIT |

**What it does:** High-performance LLM gateway. Claims 50x faster than LiteLLM under load.

**Why study it:**
- Go's concurrency model makes it extremely fast
- Minimal dependencies
- Good for understanding performance trade-offs

**Where it falls short:**
- Very minimal feature set
- No observability, no compliance, no security features
- Small community

**Key insight:** Performance matters at scale. If you hit throughput limits with Python/FastAPI, Go is the migration path.

---

### Helicone AI Gateway

| | |
|---|---|
| **Repo** | https://github.com/Helicone/helicone |
| **Language** | TypeScript (Cloudflare Workers) |
| **Stars** | 3K+ |
| **License** | Apache 2.0 |

**What it does:** LLM observability proxy. Every request goes through Helicone's Cloudflare Worker, which logs it to ClickHouse and passes it to the real provider. They track cost, latency, time-to-first-token, and errors per request.

**Why study it:**
- Best-in-class observability model — copy their data schema
- `ProxyRequestHandler.ts` shows the cleanest async streaming log pattern
- `timeToFirstToken` tracking is explicit and correct
- ClickHouse usage confirms: PostgreSQL is not the right DB for request analytics at scale

**Where it falls short:**
- Runs on **Cloudflare Workers** — not on-prem deployable as-is
- No PII detection, no compliance features
- TypeScript/Cloudflare ecosystem is not portable to Python/FastAPI

**What the code actually looks like (read these files):**
```
helicone/worker/src/
├── lib/HeliconeProxyRequest/
│   ├── ProxyRequestHandler.ts   ← THE most important file. Async log pattern.
│   └── ProxyForwarder.ts        ← How they forward to providers
├── lib/dbLogger/DBLoggable.ts   ← Log object structure — copy the field names
└── lib/db/ClickhouseWrapper.ts  ← ClickHouse client for analytics
```

**Real code-level findings:**
- `ProxyRequestHandler.ts` uses a `ReadableInterceptor` to wrap the response stream: the client gets chunks immediately, while the interceptor also buffers them. After the stream ends, the buffered body is logged — **zero latency added to the proxy response**.
- `timeToFirstToken` = `chunk.firstChunkTimeUnix - requestStartTime`. Track this from day one.
- **ClickHouse is their primary analytics store.** Supabase (PostgreSQL) handles users/orgs/keys only.
- Negative status codes: `-2` = timeout, `-3` = cancelled, `-4` = blocked by policy, `-100` = unknown. Adopt this convention.
- Response headers they add: `Helicone-Id`, `Helicone-Status`, `Helicone-Provider`, `Helicone-Model`. Use `X-OpenProxyAI-Request-Id`, `X-OpenProxyAI-Provider`, `X-OpenProxyAI-Model` instead.

**Key insight:** The data plane / control plane separation is the right architecture for production. Your FastAPI proxy is the data plane; your admin dashboard is the control plane.

---

### Envoy AI Gateway

| | |
|---|---|
| **Repo** | https://github.com/envoyproxy/ai-gateway |
| **Language** | Go / C++ |
| **Stars** | CNCF project |
| **License** | Apache 2.0 |

**What it does:** CNCF-backed AI gateway built on top of Envoy Proxy. Enterprise-grade, designed for Kubernetes.

**Why study it:**
- The enterprise standard for API gateways
- WASM plugin system (extensible without recompiling)
- Excellent observability (Prometheus, Jaeger, Zipkin)
- Service mesh integration (Istio, Linkerd)

**Where it falls short:**
- Complex to deploy and configure
- Overkill for early-stage startups
- No LLM-specific features (PII, cost tracking) out of the box

**Key insight:** This is what your enterprise customers' infrastructure teams will want to integrate with eventually. Design your API to be Envoy-compatible.

---

### ProxyGPT

| | |
|---|---|
| **Repo** | https://github.com/proxygpt/proxygpt |
| **Language** | Python |
| **Stars** | 500+ |
| **License** | MIT |

**What it does:** The simplest possible LLM proxy. Minimal code, easy to understand.

**Why study it:**
- Best starting point for understanding the basics
- Read the entire codebase in an afternoon
- Good mental model before diving into LiteLLM

---

## 2. Tier 2: Traditional Proxy Infrastructure

These are the battle-tested tools your enterprise customers already have. Understanding them helps you integrate with existing infrastructure.

### HAProxy

| | |
|---|---|
| **Docs** | https://www.haproxy.org/download/2.8/doc/configuration.txt |
| **Use case** | TCP/HTTP load balancing, SNI routing, health checks |

**Relevant for OpenProxyAI:**
- Load balancing across multiple proxy instances
- SNI-based routing (route by AI provider without TLS termination)
- Health check and failover configuration
- Rate limiting at the TCP level

**Key config patterns:**
```haproxy
# SNI-based routing without TLS termination
frontend ai_passthrough
    bind *:443
    mode tcp
    tcp-request inspect-delay 5s
    use_backend openai_backend if { req_ssl_sni -i api.openai.com }

backend openai_backend
    mode tcp
    server openai api.openai.com:443 ssl verify required
```

---

### Traefik

| | |
|---|---|
| **Docs** | https://doc.traefik.io/traefik/ |
| **Use case** | Cloud-native reverse proxy, Docker/K8s integration |

**Relevant for OpenProxyAI:**
- Auto-discovery of services in Docker Compose / Kubernetes
- Automatic TLS certificate management (Let's Encrypt)
- Middleware plugins (rate limiting, auth, headers)
- Dashboard for route visualization

**Key advantage:** Zero-config with Docker labels — great for your development environment.

---

### nginx

| | |
|---|---|
| **Docs** | https://nginx.org/en/docs/ |
| **Use case** | Reverse proxy, SSL termination, static file serving |

**Relevant for OpenProxyAI:**
- SSL termination for your proxy endpoint
- Rate limiting with `limit_req_zone`
- Upstream load balancing
- Serving your admin dashboard static files

---

### Kong Gateway

| | |
|---|---|
| **Docs** | https://docs.konghq.com/ |
| **Use case** | API gateway with plugin ecosystem |

**Relevant for OpenProxyAI:**
- Plugin model (auth, rate limiting, logging) — good reference for your own plugin system
- Admin API pattern — reference for your management API design
- Enterprise customers may already have Kong deployed

---

## 3. Tier 3: Observability Stack

### Langfuse

| | |
|---|---|
| **Repo** | https://github.com/langfuse/langfuse |
| **Language** | TypeScript |
| **Stars** | 8K+ |

**What it does:** LLM observability platform. Traces, evals, cost tracking, prompt management.

**Why it matters:**
- Your customers will ask "can I use Langfuse with OpenProxyAI?" — the answer should be yes
- Study their data model for LLM traces (spans, generations, scores)
- Consider building Langfuse-compatible export

**Integration approach:**
```python
# Your proxy can emit Langfuse-compatible events
from langfuse import Langfuse

langfuse = Langfuse(
    public_key="pk-...",
    secret_key="sk-...",
    host="https://cloud.langfuse.com"
)

# Log each proxied request
trace = langfuse.trace(name="proxied-completion")
generation = trace.generation(
    name="openai-gpt4o",
    model="gpt-4o",
    input=messages,
    output=response,
    usage={"prompt_tokens": 100, "completion_tokens": 50}
)
```

---

### Prometheus + Grafana

**What they do:** Industry-standard metrics collection (Prometheus) and visualization (Grafana).

**Metrics to expose from your proxy:**
```python
# FastAPI + prometheus-fastapi-instrumentator
from prometheus_fastapi_instrumentator import Instrumentator

app = FastAPI()
Instrumentator().instrument(app).expose(app)

# Custom metrics
from prometheus_client import Counter, Histogram, Gauge

requests_total = Counter(
    "openproxyai_requests_total",
    "Total proxied requests",
    ["provider", "model", "org_id", "status"]
)

token_usage = Counter(
    "openproxyai_tokens_total",
    "Total tokens processed",
    ["provider", "model", "org_id", "token_type"]
)

request_latency = Histogram(
    "openproxyai_request_duration_seconds",
    "Request latency",
    ["provider", "model"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0]
)

cost_usd = Counter(
    "openproxyai_cost_usd_total",
    "Total cost in USD",
    ["provider", "model", "org_id"]
)
```

**Grafana dashboard panels to build:**
- Requests per minute by provider
- Token usage by org/department
- Cost per day/week/month by org
- P50/P95/P99 latency by model
- Error rate by provider
- Active API keys

---

## 4. Tier 4: Browser Extension Resources

### Key Repos

| Repo | Description |
|---|---|
| `PlasmoHQ/plasmo` | Full-stack browser extension framework with React support |
| `fregante/browser-extension-template` | Minimal MV3 boilerplate |
| `nicholasgasior/chrome-extension-boilerplate` | Simple redirect extension example |
| `mozilla/web-ext` | Firefox extension build/sign/run tooling |

### Key Docs

- [Chrome Extensions MV3 Migration Guide](https://developer.chrome.com/docs/extensions/develop/migrate)
- [Firefox Extension Workshop](https://extensionworkshop.com/)
- [Chrome Enterprise Extension Management](https://support.google.com/chrome/a/answer/9296680)

### Key APIs

```javascript
// Manifest V3 — Declarative Net Request (preferred, more performant)
chrome.declarativeNetRequest.updateDynamicRules({
  addRules: [{
    id: 1,
    action: { type: "redirect", redirect: { transform: { host: "openproxai.yourdomain.com" } } },
    condition: { requestDomains: ["api.openai.com"] }
  }]
});

// Manifest V2 — webRequest (more flexible, being deprecated in Chrome)
browser.webRequest.onBeforeRequest.addListener(
  (details) => ({ redirectUrl: "https://openproxai.yourdomain.com" + new URL(details.url).pathname }),
  { urls: ["https://api.openai.com/*"] },
  ["blocking"]
);
```

---

## 5. Recommended Tech Stack

Based on analysis of the ecosystem, here is the recommended stack for OpenProxyAI:

### Backend (Proxy Engine)

| Layer | Technology | Rationale |
|---|---|---|
| **Framework** | FastAPI (Python) | Async, OpenAPI docs auto-generated, huge ecosystem |
| **LLM Abstraction** | LiteLLM | Handles 100+ providers, token counting, cost tracking |
| **Database** | PostgreSQL | Reliable, ACID, great for audit logs and analytics |
| **Cache / Rate Limit** | Redis | Sub-millisecond rate limiting, session storage |
| **Auth** | Custom API keys → Auth0/Supabase | Start simple, add SSO later |
| **PII Detection** | Microsoft Presidio | Best open-source PII/NER library |
| **Task Queue** | Celery + Redis | Async log processing, report generation |
| **Containerization** | Docker + Docker Compose | Dev parity, easy customer deployment |
| **Orchestration** | Kubernetes (Phase 3+) | Scale when needed |

### Frontend (Admin Dashboard)

| Layer | Technology | Rationale |
|---|---|---|
| **Framework** | React + TypeScript | Already used in marketing site |
| **Build** | Vite | Fast dev server, already configured |
| **UI Components** | shadcn/ui + Radix | Already installed, accessible |
| **Charts** | Recharts | Already installed, good for cost/usage dashboards |
| **State** | Zustand or React Query | Lightweight, sufficient for dashboard |
| **Auth** | Supabase Auth or Auth0 | SSO, SAML support for enterprise |

### Observability

| Layer | Technology | Rationale |
|---|---|---|
| **LLM Tracing** | Langfuse | Industry standard, open source |
| **Metrics** | Prometheus + Grafana | Industry standard |
| **Logs** | Structured JSON → PostgreSQL | Queryable, compliant |
| **Alerts** | Grafana Alerting | Integrated with metrics |

### Deployment

| Environment | Stack |
|---|---|
| **Development** | Docker Compose (all services local) |
| **Staging** | Single VPS (DigitalOcean / Hetzner) |
| **Production (early)** | Docker Compose on dedicated server |
| **Production (scale)** | Kubernetes (EKS / GKE) |

---

## 6. Phase 1: Study & Setup

**Duration:** Weeks 1–2  
**Goal:** Understand the ecosystem, set up dev environment, make your first proxied request

### Week 1: Study

- [ ] Clone and run LiteLLM proxy locally
  ```bash
  pip install litellm[proxy]
  litellm --model gpt-4o --port 8000
  curl http://localhost:8000/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{"model": "gpt-4o", "messages": [{"role": "user", "content": "Hello"}]}'
  ```
- [ ] Clone and run Portkey Gateway locally
  ```bash
  git clone https://github.com/Portkey-AI/gateway
  cd gateway && npm install && npm run dev
  ```
- [ ] Read LiteLLM's `proxy/` folder — understand the FastAPI structure
- [ ] Read Portkey's middleware pipeline — understand request/response transformation
- [ ] Read ProxyGPT — understand the minimal viable proxy

### Week 2: Setup

- [ ] Set up dev environment:
  ```bash
  # Python environment
  python -m venv venv
  source venv/bin/activate  # or venv\Scripts\activate on Windows
  pip install fastapi uvicorn litellm redis psycopg2-binary presidio-analyzer

  # Docker Compose for local services
  docker-compose up -d postgres redis
  ```
- [ ] Create project structure:
  ```
  backend/
  ├── app/
  │   ├── main.py           ← FastAPI app
  │   ├── routers/
  │   │   ├── proxy.py      ← /v1/chat/completions
  │   │   └── admin.py      ← Management API
  │   ├── middleware/
  │   │   ├── auth.py       ← API key validation
  │   │   ├── rate_limit.py ← Redis rate limiting
  │   │   └── audit.py      ← Request logging
  │   ├── models/
  │   │   ├── request.py    ← Pydantic models
  │   │   └── audit_log.py  ← DB models
  │   └── services/
  │       ├── llm.py        ← LiteLLM wrapper
  │       └── pii.py        ← Presidio wrapper
  ├── tests/
  ├── docker-compose.yml
  └── requirements.txt
  ```
- [ ] Make your first proxied request through your own FastAPI app

---

## 7. Phase 2: Build MVP

**Duration:** Weeks 3–10  
**Goal:** Working proxy with API keys, logging, multi-provider routing, rate limiting

### Core Proxy Endpoint

```python
# app/routers/proxy.py
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
import litellm
from app.middleware.auth import validate_api_key
from app.middleware.audit import log_request
from app.middleware.rate_limit import check_rate_limit

router = APIRouter()

@router.post("/v1/chat/completions")
async def chat_completions(
    request: Request,
    api_key_data = Depends(validate_api_key)
):
    body = await request.json()

    # Rate limiting
    await check_rate_limit(api_key_data["org_id"])

    # Route to correct provider based on model
    try:
        response = await litellm.acompletion(**body)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

    # Async audit log (don't block the response)
    await log_request(
        org_id=api_key_data["org_id"],
        user_id=api_key_data["user_id"],
        request=body,
        response=response,
        cost=litellm.completion_cost(response)
    )

    return response
```

### API Key System

```python
# app/middleware/auth.py
import hashlib
import secrets
from fastapi import HTTPException, Header
from app.db import get_db

def generate_api_key() -> tuple[str, str]:
    """Returns (raw_key, hashed_key). Store only the hash."""
    raw = "oai-" + secrets.token_urlsafe(32)
    hashed = hashlib.sha256(raw.encode()).hexdigest()
    return raw, hashed

async def validate_api_key(authorization: str = Header(...)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    raw_key = authorization[7:]
    hashed = hashlib.sha256(raw_key.encode()).hexdigest()

    async with get_db() as db:
        key_data = await db.fetchrow(
            "SELECT org_id, user_id, permissions, rate_limit "
            "FROM api_keys WHERE key_hash = $1 AND revoked = false",
            hashed
        )

    if not key_data:
        raise HTTPException(status_code=401, detail="Invalid API key")

    return dict(key_data)
```

### Token & Cost Logging

```python
# app/middleware/audit.py
import asyncio
from datetime import datetime
from app.db import get_db

async def log_request(org_id, user_id, request, response, cost):
    """Async audit log — does not block the proxy response."""
    async with get_db() as db:
        await db.execute("""
            INSERT INTO audit_logs (
                org_id, user_id, model, provider,
                prompt_tokens, completion_tokens, total_tokens,
                cost_usd, latency_ms, created_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        """,
            org_id,
            user_id,
            response.model,
            response.model.split("/")[0] if "/" in response.model else "openai",
            response.usage.prompt_tokens,
            response.usage.completion_tokens,
            response.usage.total_tokens,
            cost,
            response.response_ms,
            datetime.utcnow()
        )
```

### PostgreSQL Schema

```sql
-- API Keys
CREATE TABLE api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id),
    user_id UUID REFERENCES users(id),
    key_hash VARCHAR(64) UNIQUE NOT NULL,
    name VARCHAR(255),
    permissions JSONB DEFAULT '{}',
    rate_limit_rpm INTEGER DEFAULT 60,
    revoked BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_used_at TIMESTAMPTZ
);

-- Audit Logs (append-only, never update)
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL,
    user_id UUID,
    model VARCHAR(100) NOT NULL,
    provider VARCHAR(50) NOT NULL,
    prompt_tokens INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    cost_usd DECIMAL(10, 8) NOT NULL DEFAULT 0,
    latency_ms INTEGER,
    status_code INTEGER DEFAULT 200,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for dashboard queries
CREATE INDEX idx_audit_logs_org_date ON audit_logs(org_id, created_at DESC);
CREATE INDEX idx_audit_logs_model ON audit_logs(model, created_at DESC);

-- Organizations
CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    plan VARCHAR(50) DEFAULT 'trial',
    monthly_budget_usd DECIMAL(10, 2),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### Redis Rate Limiting

```python
# app/middleware/rate_limit.py
import redis.asyncio as redis
import time
from fastapi import HTTPException

r = redis.from_url("redis://localhost:6379")

async def check_rate_limit(org_id: str, limit_rpm: int = 60):
    """Sliding window rate limiter using Redis sorted sets."""
    key = f"rate_limit:{org_id}"
    now = time.time()
    window_start = now - 60  # 1 minute window

    pipe = r.pipeline()
    pipe.zremrangebyscore(key, 0, window_start)  # Remove old entries
    pipe.zadd(key, {str(now): now})              # Add current request
    pipe.zcard(key)                               # Count requests in window
    pipe.expire(key, 60)                          # TTL cleanup
    results = await pipe.execute()

    request_count = results[2]
    if request_count > limit_rpm:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded: {limit_rpm} requests/minute",
            headers={"Retry-After": "60"}
        )
```

### MVP Milestones

- [ ] Week 3: `/v1/chat/completions` endpoint working, proxies to OpenAI
- [ ] Week 4: API key system (create, validate, revoke)
- [ ] Week 5: Audit logging to PostgreSQL
- [ ] Week 6: Multi-provider routing (OpenAI + Anthropic + Mistral)
- [ ] Week 7: Redis rate limiting per org
- [ ] Week 8: Basic admin API (list keys, usage stats)
- [ ] Week 9: Docker Compose deployment (proxy + postgres + redis)
- [ ] Week 10: First design partner using it in production

---

## 8. Phase 3: Production Hardening

**Duration:** Ongoing (Months 3–6)  
**Goal:** Enterprise-ready features, compliance, admin dashboard

### Admin Dashboard

```
Admin Dashboard Features (Priority Order):
1. Usage charts (tokens/cost per day by model)
2. API key management (create, revoke, set limits)
3. Audit log viewer (searchable, filterable)
4. Budget alerts (email when X% of monthly budget used)
5. User management (add/remove org members)
6. SSO configuration (SAML, OAuth)
7. Policy editor (content filters, model allowlist)
```

### PII Detection with Presidio

```python
# app/services/pii.py
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine

analyzer = AnalyzerEngine()
anonymizer = AnonymizerEngine()

def detect_pii(text: str) -> list:
    """Returns list of PII entities found in text."""
    results = analyzer.analyze(
        text=text,
        entities=["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER",
                  "CREDIT_CARD", "US_SSN", "IBAN_CODE"],
        language="en"
    )
    return results

def anonymize_pii(text: str) -> str:
    """Replace PII with placeholders before sending to LLM."""
    results = detect_pii(text)
    if not results:
        return text

    anonymized = anonymizer.anonymize(
        text=text,
        analyzer_results=results
    )
    return anonymized.text

# Usage in proxy middleware
async def pii_middleware(request_body: dict, policy: dict) -> dict:
    if policy.get("pii_detection") == "block":
        for message in request_body.get("messages", []):
            pii = detect_pii(message["content"])
            if pii:
                raise HTTPException(
                    status_code=400,
                    detail=f"PII detected in request: {[e.entity_type for e in pii]}"
                )

    elif policy.get("pii_detection") == "anonymize":
        for message in request_body.get("messages", []):
            message["content"] = anonymize_pii(message["content"])

    return request_body
```

### SSO Integration (Auth0)

```python
# app/middleware/sso.py
from authlib.integrations.starlette_client import OAuth
from starlette.config import Config

config = Config(".env")
oauth = OAuth(config)

oauth.register(
    name="auth0",
    server_metadata_url=f'https://{AUTH0_DOMAIN}/.well-known/openid-configuration',
    client_kwargs={"scope": "openid email profile"},
)

# SAML for enterprise customers
# Use python-saml or pysaml2
```

### Docker Compose (Production)

```yaml
# docker-compose.prod.yml
version: "3.9"

services:
  proxy:
    image: openproxyai/proxy:latest
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:pass@postgres:5432/openproxyai
      - REDIS_URL=redis://redis:6379
      - SECRET_KEY=${SECRET_KEY}
    depends_on:
      - postgres
      - redis
    restart: unless-stopped

  postgres:
    image: postgres:16-alpine
    volumes:
      - postgres_data:/var/lib/postgresql/data
    environment:
      - POSTGRES_DB=openproxyai
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/conf.d/default.conf
      - ./certs:/etc/nginx/certs
    depends_on:
      - proxy
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
```

### Phase 3 Milestones

- [ ] PII detection and anonymization
- [ ] Admin dashboard (React, cost charts, key management)
- [ ] SSO / SAML integration
- [ ] SOC 2 Type I audit preparation
- [ ] Kubernetes deployment manifests
- [ ] Multi-region deployment
- [ ] SLA monitoring and alerting

---

## 9. Key Architecture Decisions

### Decision 1: Python vs. Go vs. Rust

**Choose Python (FastAPI) for Phase 1-2.**

Rationale:
- LiteLLM is Python — deep integration is easier
- Presidio (PII detection) is Python
- Fastest to iterate on
- Hire Python engineers more easily

**Migrate hot paths to Go in Phase 3 if needed.**

Benchmark threshold: If you're handling >1,000 RPS and Python becomes the bottleneck, extract the core proxy path to Go (like Bifrost does).

---

### Decision 2: LiteLLM vs. Direct Provider SDKs

**Use LiteLLM as the abstraction layer.**

Rationale:
- 100+ providers with one interface
- Handles token counting and cost calculation
- Active maintenance and community
- You can always drop down to direct SDKs for specific providers

**Risk:** LiteLLM is a dependency you don't control. Mitigate by:
- Pinning versions
- Wrapping it in your own `LLMService` class
- Having a fallback path for critical providers

---

### Decision 3: Audit Log Storage

**PostgreSQL for audit logs (not a separate log aggregator).**

Rationale:
- SQL queries for compliance reports (SOC 2, HIPAA)
- ACID guarantees for immutability
- Customers can export to their SIEM later
- Simpler stack (no Elasticsearch to manage)

**At scale:** Add TimescaleDB extension for time-series performance, or migrate to ClickHouse for analytics.

---

### Decision 4: Streaming Support

**Implement SSE streaming from day one.**

Most LLM use cases require streaming (token-by-token responses). FastAPI supports this natively:

```python
from fastapi.responses import StreamingResponse

@router.post("/v1/chat/completions")
async def chat_completions_stream(request: Request):
    body = await request.json()

    async def generate():
        async for chunk in await litellm.acompletion(**body, stream=True):
            yield f"data: {chunk.model_dump_json()}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
```

---

*Last Updated: February 2026 | OpenProxyAI Founder Reference*
