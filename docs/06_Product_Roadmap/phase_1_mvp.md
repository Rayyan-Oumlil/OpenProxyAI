# Phase 1: MVP Roadmap (Months 1-4)

**Goal:** Ship a working secure LLM proxy with first paying customer

**Timeline:** 12-16 weeks  
**Target:** First $5K-10K ARR by week 16

---

## 🎯 MVP Success Criteria

### Must Have
- ✅ LLM proxy for OpenAI, Anthropic, Azure OpenAI
- ✅ API key authentication
- ✅ Token counting and cost tracking
- ✅ Basic audit logs
- ✅ Admin dashboard (read-only analytics)
- ✅ Docker + Docker Compose deployment
- ✅ Documentation site

### Nice to Have (Phase 2)
- ⏭️ SSO / OAuth
- ⏭️ Multi-tenancy UI
- ⏭️ Policy engine
- ⏭️ Advanced analytics

### Explicitly Out of Scope
- ❌ RAG orchestration
- ❌ Web search integration
- ❌ Mobile app
- ❌ Voice features
- ❌ Kubernetes deployment

---

## 📅 Week-by-Week Breakdown

### **Week 1-2: Foundation & Setup**

#### Week 1: Project Setup
**Time allocation: 40 hours**

**Day 1-2: Repository & Infrastructure**
- [ ] Create GitHub repo (public from day 1)
- [ ] Set up development environment
- [ ] Create Docker Compose stack (Postgres + Redis)
- [ ] Basic FastAPI project structure
- [ ] CI/CD with GitHub Actions (lint, test, build)

```bash
openproxyai/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── models/
│   │   ├── routes/
│   │   ├── services/
│   │   └── utils/
│   ├── tests/
│   ├── alembic/
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   ├── public/
│   ├── package.json
│   └── vite.config.ts
├── docker-compose.yml
├── README.md
└── LICENSE (MIT)
```

**Day 3-4: Database Schema**
- [ ] Design core tables (users, orgs, api_keys, requests)
- [ ] Set up Alembic migrations
- [ ] Create seed data for testing
- [ ] Write database tests

> **Note from reference code study:** Design the `request_logs` table to match ClickHouse's columnar schema from day one (see system architecture doc). When you migrate from PostgreSQL to ClickHouse in Phase 3, the schema will be identical — migration is just a copy. Key fields: `request_id`, `org_id`, `user_id`, `model`, `provider`, `prompt_tokens`, `completion_tokens`, `cost_usd`, `latency_ms`, `ttft_ms` (time-to-first-token), `status_code` (use negative values: -2=timeout, -3=cancel, -4=blocked).

**Day 5: Basic API Structure**
- [ ] Health check endpoint (`/health`)
- [ ] Authentication middleware
- [ ] Error handling
- [ ] Logging setup (structured logs)

**Deliverable:** Working API skeleton that starts and responds

---

#### Week 2: Core Proxy Logic
**Time allocation: 40 hours**

**Day 1-2: LLM Proxy Core**
- [ ] Install LiteLLM (`pip install litellm`)
- [ ] Implement proxy endpoint `/v1/chat/completions` — handler must stay under ~50 lines
- [ ] OpenAI API compatibility (drop-in replacement)
- [ ] Streaming response support with `ReadableInterceptor` pattern (log AFTER stream ends, never block response)
- [ ] Track `time_to_first_token_ms` from the first streamed chunk
- [ ] Add response headers: `X-OpenProxyAI-Request-Id`, `X-OpenProxyAI-Provider`, `X-OpenProxyAI-Model`
- [ ] Basic error handling with structured error responses

> **Pattern from Helicone:** Streaming log must be non-blocking. Wrap the generator in a function that captures chunks AND yields them simultaneously, then schedules the DB log as a background task after the stream completes. See `ProxyRequestHandler.ts` in `references/helicone/worker/src/lib/HeliconeProxyRequest/`.

```python
# Example implementation
from fastapi import FastAPI
from litellm import completion

app = FastAPI()

@app.post("/v1/chat/completions")
async def chat_completion(request: ChatRequest):
    # Validate request
    # Route to provider
    response = await completion(
        model=request.model,
        messages=request.messages,
        stream=request.stream
    )
    # Count tokens
    # Log request
    return response
```

**Day 3: Provider Integration**
- [ ] OpenAI integration
- [ ] Anthropic integration
- [ ] Azure OpenAI integration
- [ ] Provider failover logic

**Day 4: Token Counting & First-Chunk Error Detection**
- [ ] **Do NOT use tiktoken directly** — `litellm.completion_cost(completion_response)` handles all token counting and cost calculation for every provider automatically
- [ ] Implement `response.usage.prompt_tokens` extraction from LiteLLM response
- [ ] Implement first-chunk error detection: peek at first SSE chunk before returning `StreamingResponse`. If it contains an error, return `JSONResponse(status_code=502)` instead — prevents clients receiving `200 OK` with an error body
- [ ] Verify cost calculation: `litellm.completion_cost(model="gpt-4o", prompt_tokens=100, completion_tokens=50)` returns a float in USD

**Day 5: Testing & Docs**
- [ ] Integration tests for each provider
- [ ] Load testing (100 req/sec)
- [ ] API documentation (OpenAPI spec)

**Deliverable:** Working proxy that can call 3 providers

---

### **Week 3-4: Authentication & Data Layer**

#### Week 3: Authentication
**Time allocation: 40 hours**

**Day 1-2: API Key System**
- [ ] API key generation
- [ ] Key hashing (bcrypt)
- [ ] Key validation middleware
- [ ] Key prefix for display (sk-proj-...)

**Day 3-4: User & Organization Model**
- [ ] User registration endpoint
- [ ] Organization creation
- [ ] User-to-org relationship
- [ ] Basic RBAC (admin vs user)

**Day 5: Security Hardening + Provider Key Rotation**
- [ ] Rate limiting (per API key) — stub that returns 429 correctly (full implementation in Week 4)
- [ ] Request validation (model field required, messages array non-empty)
- [ ] SQL injection prevention tests
- [ ] Security headers (`X-Content-Type-Options`, `X-Frame-Options`, `Strict-Transport-Security`)
- [ ] **Provider key rotation**: create `llm_provider_keys` table with columns `(org_id, provider, key_id, api_key_encrypted, weight, is_active)`. The `LLMService` uses weighted random selection to pick a key per call. This enables zero-downtime key rotation from day one.

**Deliverable:** Secure authentication system + provider key management

---

#### Week 4: Rate Limiting & Cost Tracking
**Time allocation: 40 hours**

**Day 1-2: Three-Dimensional Rate Limiting**
- [ ] Implement Redis-based rate limiter with three counters per org: `requests/minute`, `tokens/minute`, `dollars/day`
- [ ] Check all three limits before forwarding to LLM — return 429 with `limit_type` field indicating which limit was hit
- [ ] Store limits in org config table (not hardcoded) — each org has custom limits
- [ ] Return all three limit headers on every response: `X-RateLimit-Requests-Remaining`, `X-RateLimit-Tokens-Remaining`, `X-RateLimit-Budget-Remaining-USD`
- [ ] **Token-based limiting is critical**: one request can use 100,000 tokens; request counting alone does not protect provider budget

> **Pattern from Envoy AI Gateway & Helicone:** Token-per-minute limits are the real cost control mechanism. A bank on Starter tier may allow 60 req/min but cap at 100,000 tokens/min to prevent accidental runaway spend from long-context calls.

**Day 3-4: Cost Tracking & Materialized Views**
- [ ] Write cost to `request_logs` via background task (never block the response)
- [ ] After logging: update `rl:usd:{org_id}:{day}` Redis key with `INCRBYFLOAT`
- [ ] Create three PostgreSQL materialized views from day one: `mv_daily_spend`, `mv_model_usage`, `mv_key_spend`
- [ ] Dashboard queries hit the views — never the raw `request_logs` table

```sql
-- Refresh every 5 minutes (pg_cron or background task)
CREATE MATERIALIZED VIEW mv_daily_spend AS
SELECT org_id, date_trunc('day', created_at) AS day, model, provider,
       SUM(cost_usd) AS total_cost_usd, COUNT(*) AS total_requests,
       AVG(latency_ms) AS avg_latency_ms
FROM request_logs GROUP BY org_id, day, model, provider;
```

**Day 5: Budget Cap & Alert**
- [ ] Budget exceeded → return 429 with `limit_type: "budget_daily_usd"` (not 402 — budget is a rate limit, not a billing error)
- [ ] Email alert at 80% of daily budget (simple SMTP via SendGrid or similar)
- [ ] Admin dashboard shows current spend vs. budget with color-coded warning

**Deliverable:** Complete rate limiting + cost tracking system

---

### **Week 5-6: Admin Dashboard (Backend)**

#### Week 5: Analytics APIs
**Time allocation: 40 hours**

**Day 1-2: Core Stats API**
```python
GET /api/v1/analytics/overview
{
  "total_requests_today": 1234,
  "total_cost_today": 45.67,
  "total_cost_month": 890.12,
  "top_users": [...],
  "top_models": [...]
}
```

**Day 3-4: Detailed Analytics**
- [ ] Cost by user endpoint
- [ ] Cost by model endpoint
- [ ] Usage trends endpoint
- [ ] Audit log query endpoint

**Day 5: Testing**
- [ ] API tests
- [ ] Performance tests (query optimization)
- [ ] Data accuracy tests

**Deliverable:** Complete analytics API

---

#### Week 6: Audit Logging
**Time allocation: 40 hours**

**Day 1-3: Audit System**
- [ ] Audit log data model
- [ ] Async logging (don't block requests)
- [ ] Log retention policy
- [ ] Log query API

**Day 4-5: Compliance Features**
- [ ] Export audit logs (CSV)
- [ ] Filter by date range
-Filter by user
- [ ] Anonymization options (PII redaction)

**Deliverable:** SOC 2-ready audit logging

---

### **Week 7-8: Frontend (Admin Dashboard)**

#### Week 7: Dashboard Setup & Core Views
**Time allocation: 40 hours**

**Day 1: Project Setup**
- [ ] Create React + Vite project
- [ ] Tailwind CSS + shadcn/ui setup
- [ ] React Query for API calls
- [ ] Routing (React Router)

**Day 2-3: Dashboard View**
- [ ] Overview cards (requests, cost)
- [ ] Cost chart (last 30 days)
- [ ] Top models chart
- [ ] Top users table

**Day 4-5: Authentication Flow**
- [ ] Login page
- [ ] Token storage (httpOnly cookies)
- [ ] Protected routes
- [ ] Logout

**Deliverable:** Basic dashboard that shows data

---

#### Week 8: Management Views
**Time allocation: 40 hours**

**Day 1-2: User Management**
- [ ] User list view
- [ ] Add user form
- [ ] Edit user (budget limits)
- [ ] Delete user

**Day 3: API Key Management**
- [ ] Generate new API key
- [ ] List keys
- [ ] Revoke key
- [ ] Show key usage

**Day 4: Analytics Views**
- [ ] Detailed cost breakdown
- [ ] Usage by department
- [ ] Model comparison
- [ ] Export reports

**Day 5: Polish**
- [ ] Responsive design (mobile)
- [ ] Loading states
- [ ] Error handling
- [ ] Empty states

**Deliverable:** Full-featured admin dashboard

---

### **Week 9-10: Documentation & Developer Experience**

#### Week 9: Documentation Site
**Time allocation: 40 hours**

**Day 1-2: Docs Site Setup**
- [ ] Use Docusaurus or Mintlify
- [ ] Domain setup (docs.openproxyai.com)
- [ ] Custom theme with branding

**Day 3-4: Core Documentation**
- [ ] Quick start guide
- [ ] Installation (Docker)
- [ ] Configuration guide
- [ ] API reference (from OpenAPI spec)

**Day 5: Advanced Guides**
- [ ] Authentication guide
- [ ] Cost tracking guide
- [ ] Audit logging guide
- [ ] FAQ

**Deliverable:** Complete documentation site

---

#### Week 10: SDKs & Examples
**Time allocation: 40 hours**

**Day 1-2: Python SDK**
```python
# Make it drop-in compatible with OpenAI SDK
from openproxyai import OpenAI

client = OpenAI(
    api_key="sk-proj-...",
    base_url="https://api.openproxyai.com/v1"
)

response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Hello!"}]
)
```

**Day 3: Example Applications**
- [ ] Python chatbot example
- [ ] Next.js web app example
- [ ] FastAPI integration example

**Day 4-5: Video Tutorials**
- [ ] 5-minute quick start video
- [ ] Installation walkthrough
- [ ] Dashboard tour

**Deliverable:** Developer-friendly SDKs and examples

---

### **Week 11-12: Testing, Polish & Launch Prep**

#### Week 11: Testing & Optimization
**Time allocation: 40 hours**

**Day 1-2: End-to-End Testing**
- [ ] User registration → API key → LLM call flow
- [ ] Budget limit enforcement
- [ ] Cost tracking accuracy
- [ ] Audit log completeness

**Day 3: Load Testing**
- [ ] 100 requests/sec sustained
- [ ] 1000 concurrent users
- [ ] Database query optimization
- [ ] Redis cache tuning

**Day 4: Security Audit**
- [ ] SQL injection tests
- [ ] XSS tests
- [ ] Authentication bypass attempts
- [ ] Rate limit testing

**Day 5: Bug Fixes**
- [ ] Fix all critical bugs
- [ ] Fix all high-priority bugs
- [ ] Document known issues

**Deliverable:** Stable, tested system

---

#### Week 12: Launch Preparation
**Time allocation: 40 hours**

**Day 1: Production Setup**
- [ ] Set up production infrastructure (Azure/AWS)
- [ ] Domain setup (api.openproxyai.com)
- [ ] SSL certificates
- [ ] Monitoring (Prometheus + Grafana)

**Day 2: Launch Materials**
- [ ] Landing page (openproxyai.com)
- [ ] GitHub README
- [ ] Demo video
- [ ] Blog post announcement

**Day 3: Community Setup**
- [ ] GitHub Discussions enabled
- [ ] Discord server
- [ ] Twitter account
- [ ] Email newsletter

**Day 4-5: Soft Launch**
- [ ] Post on Hacker News
- [ ] Post on Reddit (r/selfhosted, r/MachineLearning)
- [ ] Tweet launch
- [ ] Email 10 potential design partners

**Deliverable:** Public launch! 🚀

---

## 🎯 Success Metrics (Week 12)

### Technical Metrics
- ✅ 99% uptime
- ✅ < 100ms proxy overhead (p95)
- ✅ 0 critical security issues
- ✅ 100% test coverage on core flows

### Community Metrics
- 🎯 500+ GitHub stars
- 🎯 100+ Discord members
- 🎯 50+ Docker pulls
- 🎯 10+ contributors

### Business Metrics
- 🎯 50+ sign-ups
- 🎯 5-10 active users
- 🎯 1-2 design partners
- 🎯 $0-5K ARR (not expected yet)

---

## 💰 Budget (Months 1-4)

### Development Costs
- **Your time:** $0 (sweat equity)
- **Cloud infrastructure:** ~$100/month × 4 = $400
  - Database (managed PostgreSQL)
  - Redis
  - Object storage
  - Load balancer
- **Domain & SSL:** $50
- **Tools & Services:** $100
  - GitHub (free for public repos)
  - Vercel (free for docs site)
  - Cloudflare (free tier)

**Total MVP Cost:** ~$550

### Time Investment
- **Total hours:** ~480 hours (12 weeks × 40 hours)
- **Realistic for solo founder:** Absolutely
- **Full-time equivalent:** 3 months

---

## 🚨 Risk Mitigation

### Common Pitfalls to Avoid

1. **Scope Creep**
   - ❌ "Let's add RAG real quick"
   - ✅ Say no to everything not in MVP

2. **Perfectionism**
   - ❌ "The dashboard needs to be beautiful"
   - ✅ Functional > beautiful for MVP

3. **Over-engineering**
   - ❌ "Let's use Kubernetes from day 1"
   - ✅ Docker Compose is enough

4. **No user feedback**
   - ❌ Build in isolation for 4 months
   - ✅ Get design partners by week 8

### Weekly Check-ins

**Every Friday, ask yourself:**
1. Am I on track for this week's deliverable?
2. Did scope creep happen? Cut it.
3. Did I talk to a potential user this week?
4. Is there a simpler way to build this?

---

## 🎉 Week 13: Celebrate & Pivot

**You did it! Now what?**

### Immediate Actions (Week 13)

1. **Gather Feedback**
   - Survey early users
   - Watch support Discord
   - Read GitHub issues

2. **Analyze Metrics**
   - What features are used?
   - What breaks often?
   - Where do users get stuck?

3. **Plan Phase 2**
   - If users love it → build enterprise features
   - If users confused → improve onboarding
   - If no users → pivot messaging/positioning

### Decision Tree

```
Do you have 10+ active users?
├── YES → Start Phase 2 (Enterprise Features)
│   └── Focus: SSO, Multi-tenancy, Policy Engine
├── NO → Analyze Why
    ├── No awareness → Marketing problem
    │   └── Fix: More content, HN, Reddit, Twitter
    ├── Try but don't adopt → Product problem
    │   └── Fix: User interviews, improve UX
    └── Try and complain → Documentation problem
        └── Fix: Better docs, videos, examples
```

---

## 📈Phase 1 → Phase 2 Transition

### When to Start Phase 2?

**Trigger Conditions (ANY of these):**
- ✅ 10+ active weekly users
- ✅ 2+ potential enterprise customers asking for SSO
- ✅ $5K+ ARR
- ✅ Community momentum (1000+ stars, active Discord)

### What to Build in Phase 2?

See [Phase 2 Roadmap](phase_2_enterprise.md)

---

*Next: [Solo Founder Playbook →](../15_Solo_Founder_Playbook/README.md)*
