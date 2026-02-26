# OpenProxyAI — Resources & Build Plan

**Founder's Technical Reference**

> A curated map of the open-source ecosystem you're entering, the tools you'll use, and a concrete 3-phase build plan to go from zero to production.

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

**Key files to read:**
```
litellm/
├── proxy/           ← The proxy server (FastAPI)
├── main.py          ← Core completion() function
├── utils.py         ← Token counting, cost calculation
└── integrations/    ← Provider-specific adapters
```

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
- Node.js (not Python — harder to integrate with ML tools like Presidio)
- No enterprise compliance features
- Limited audit logging

**Key patterns to steal:**
- The middleware pipeline pattern for request processing
- Provider config schema (how they abstract provider differences)
- Retry/fallback logic

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
| **Language** | Rust + TypeScript |
| **Stars** | 3K+ |
| **License** | Apache 2.0 |

**What it does:** Positioned as "the NGINX of LLMs." Extremely fast Rust core with a TypeScript management layer.

**Why study it:**
- Rust performance characteristics
- Good observability model (they track cost, latency, errors per request)
- Clean separation between data plane (Rust) and control plane (TS)

**Where it falls short:**
- Rust is harder to extend for non-Rust developers
- No enterprise compliance features

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
