# OpenProxyAI Architecture Overview

OpenProxyAI is an enterprise-grade LLM proxy and gateway for regulated industries. It sits between organizations and LLM providers (OpenAI, Anthropic, Azure, Mistral, etc.), providing unified authentication, policy enforcement, cost tracking, and audit logging.

## Core Architecture

The system comprises five main components:

1. **FastAPI Proxy Engine** — HTTP server handling incoming requests, orchestrating the pipeline
2. **PostgreSQL** — Persistent data store for orgs, users, keys, logs, and config
3. **Redis** — In-memory cache and rate limiter state
4. **LiteLLM Router** — Provider abstraction, model routing, and fallback handling
5. **Admin Console** — React UI for policy configuration, analytics, and team management

## Request Pipeline

Every request follows this order:

```
Incoming Request
    ↓
Auth (validate API key) [FAIL → 401]
    ↓
Rate Limit Check (RPM, TPM, daily budget) [FAIL → 429]
    ↓
Policy Evaluation (PII detection, keyword filtering, model allowlist) [FAIL → 403]
    ↓
LLM Forward (call provider via LiteLLM)
    ↓
Async Log (background task: PostgreSQL + Redis + webhooks + Langfuse + ClickHouse)
    ↓
Response to Client
```

All steps are synchronous except the final logging step, which fires in the background to avoid blocking the response.

### Authentication

API requests must include a Bearer token:

```bash
curl https://api.openproxy.ai/v1/chat/completions \
  -H "Authorization: Bearer sk_org_abc123_user_def456_hash789"
```

The token format is `sk_org_{org_id}_{user_id}_{hash_suffix}`. The `key_hash` column in `api_keys` table stores the SHA-256 hash for verification; the plaintext key is never persisted.

### Rate Limiting

Redis tracks three dimensions per organization:

- **Requests per Minute (RPM):** Sliding window stored as sorted set (`rl:req:{org_id}`)
- **Tokens per Minute (TPM):** Counter by minute bucket (`rl:tok:{org_id}:{minute_bucket}`)
- **Daily Budget (USD):** Hash incremented per request (`rl:usd:{org_id}:{YYYY-MM-DD}`)

Users can have per-user daily budgets that further constrain requests. If any limit is exceeded, the request is rejected with HTTP 429 (rate limit) or HTTP 402 (budget exceeded).

The rate limiter also supports per-model limits via `policy_config.model_rate_limits`, allowing orgs to cap specific models independently.

### Policy Enforcement

Before forwarding to the LLM provider, the request is evaluated against the organization's policy config:

- **Model Allowlist:** If configured, only requests for allowed models proceed
- **Blocked Keywords:** Text content is scanned for forbidden terms
- **PII Detection:** Uses Microsoft Presidio (optional) or regex fallback to detect emails, SSNs, credit cards, etc.
- **Prompt Injection Detection:** Regex patterns match common jailbreak attempts (optional, can be enabled per-org)

Violations return HTTP 403 with `X-OpenProxyAI-Policy-Action` header. The action can be:
- `block` — request is rejected
- `log_only` — request proceeds but violation is logged

### LLM Forward

The `LLMService` class wraps LiteLLM:

1. Selects the correct provider API key from `llm_provider_keys` table (supports weighted random rotation)
2. Calls `litellm.acompletion()` with the provider key
3. Handles streaming responses by peeking at the first chunk to detect provider errors
4. Calculates token counts and cost using LiteLLM's built-in pricing

Provider keys are encrypted at rest and decrypted only when needed. Multiple keys per provider are supported with `weight` field for probabilistic selection.

### Async Logging

After the response is streamed to the client, a background task logs the request:

```python
background_tasks.add_task(log_request, ...)
```

This task:

1. Inserts `RequestLog` row into PostgreSQL with full request details
2. Increments Redis daily spend counters for cost tracking
3. Fires webhook for policy violations (fire-and-forget)
4. Sends trace to Langfuse if enabled (fire-and-forget)
5. Checks for cost anomalies (fire-and-forget)
6. Writes to ClickHouse if enabled (Phase 3, fire-and-forget)
7. Records Prometheus metrics if enabled (synchronous)

All fire-and-forget operations use `asyncio.create_task()` and swallow exceptions to ensure that logging failures never affect the main request pipeline.

## Core Distinction: Sidecars vs. Core

### Core Services (Fail Hard)

These services are critical to the proxy's function and failures must block the request:

- PostgreSQL (users, orgs, API keys, policies)
- Redis (rate limiting, session state)
- LLM provider connectivity (the whole point)
- Policy enforcement (security boundary)
- Audit logging to PostgreSQL (compliance)

### Sidecar Services (Fail Silently)

These are observability/analytics integrations that enhance the system but are not essential:

- Langfuse (tracing)
- ClickHouse (historical analytics)
- Prometheus (metrics)
- Webhooks (notifications)
- Cost anomaly detection

If a sidecar service becomes unavailable, the background task logs a warning but does not retry. The main request is unaffected.

## Security Headers

Every HTTP response includes SOC 2 / HIPAA-compliant headers via `SecurityHeadersMiddleware`:

```
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Strict-Transport-Security: max-age=31536000; includeSubDomains
Content-Security-Policy: default-src 'none'; frame-ancestors 'none'
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: geolocation=(), microphone=(), camera=()
```

## Response Headers

The proxy returns custom headers to help clients:

```
X-OpenProxyAI-Request-Id: {uuid}
X-OpenProxyAI-Provider: openai
X-OpenProxyAI-Model: gpt-4o
X-OpenProxyAI-Cost-USD: 0.105000
X-OpenProxyAI-Latency-Ms: 2340
X-OpenProxyAI-TTFT-Ms: 450 (streaming only)
X-OpenProxyAI-Gateway-Error: false (true if proxy error, false if provider error)
X-OpenProxyAI-Policy-Action: allow (or block/log_only)
X-OpenProxyAI-Cache: miss (or hit for cached responses)
X-RateLimit-Requests-Remaining: 95
X-RateLimit-Tokens-Remaining: 45000
X-RateLimit-Budget-Remaining-USD: 123.45
X-RateLimit-Reset: 1710604260
```

## Environment Variables

### Essential Configuration

```
# Database (required)
DATABASE_URL=postgresql://user:pass@localhost:5432/openproxyai

# Redis (required)
REDIS_URL=redis://localhost:6379/0

# Secret key for signing tokens
SECRET_KEY=your-secret-key-min-32-chars

# LLM provider API keys (at least one required)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
AZURE_API_KEY=...
```

### Optional: Observability

```
# Langfuse tracing
LANGFUSE_PUBLIC_KEY=...
LANGFUSE_SECRET_KEY=...
LANGFUSE_HOST=https://cloud.langfuse.com

# Prometheus metrics
PROMETHEUS_ENABLED=true

# ClickHouse (Phase 3)
CLICKHOUSE_URL=http://localhost:8123/default
```

### Optional: Policy & Compliance

```
# PII Detection (Microsoft Presidio)
PRESIDIO_ENABLED=true
PRESIDIO_ENTITIES=PERSON,EMAIL_ADDRESS,PHONE_NUMBER
PRESIDIO_SCORE_THRESHOLD=0.5

# Cost tracking thresholds
COST_ANOMALY_THRESHOLD_PERCENT=150
DEFAULT_BUDGET_DAILY_USD=100.00
DEFAULT_RATE_LIMIT_RPM=100
DEFAULT_RATE_LIMIT_TPM=100000

# Policy enforcement
POLICY_ENFORCEMENT_MODE=off|log_only|block
POLICY_ALLOWED_MODELS=gpt-4o,claude-3-5-sonnet
POLICY_BLOCKED_KEYWORDS=delete_user,drop_table
POLICY_PII_DETECTION_ENABLED=true
```

### Optional: Network & CORS

```
CORS_ORIGINS=https://app.example.com,https://dev.example.com
ALLOWED_ORIGINS_JSON=["https://app.example.com"]
```

## Data Flow Diagram

```
┌─────────────────┐
│  SDK / Client   │
└────────┬────────┘
         │ POST /v1/chat/completions
         ↓
    ┌────────────────────────────────┐
    │  FastAPI App                   │
    │  ├─ RequestIdMiddleware        │
    │  ├─ TimingMiddleware           │
    │  ├─ SecurityHeadersMiddleware  │
    └────────────────────────────────┘
         │
         ├─→ auth_router.validate_key()
         │   ├─ Query PostgreSQL: api_keys
         │   └─ Load User + Org context
         │
         ├─→ llm_service.chat_completion()
         │   ├─ policy_service.evaluate(request, policy_config)
         │   │  ├─ [BLOCKED] → return 403
         │   │  └─ [ALLOWED] → continue
         │   │
         │   ├─ rate_limiter_service.check_limits()
         │   │  ├─ Query Redis: RPM, TPM, daily spend
         │   │  ├─ [EXCEEDED] → return 429 or 402
         │   │  └─ [OK] → consume and continue
         │   │
         │   ├─ Select provider key from llm_provider_keys
         │   │  └─ Decrypt api_key_encrypted
         │   │
         │   ├─ litellm.acompletion(**kwargs)
         │   │  └─ Forward to OpenAI / Anthropic / Azure / etc.
         │   │
         │   └─ background_tasks.add_task(log_request, ...)
         │      ├─ Insert RequestLog to PostgreSQL
         │      ├─ Increment Redis spend counters
         │      ├─ Fire webhooks (fire-and-forget)
         │      ├─ Send to Langfuse (fire-and-forget)
         │      ├─ Write to ClickHouse (fire-and-forget)
         │      └─ Record Prometheus metrics
         │
         └─→ StreamingResponse / JSONResponse to client
             ├─ Response headers (X-OpenProxyAI-*, X-RateLimit-*)
             └─ LLM provider's response body
```

## Materialized View: mv_daily_spend

For fast dashboard queries, a materialized view aggregates daily spending:

```sql
CREATE MATERIALIZED VIEW mv_daily_spend AS
SELECT
    org_id,
    user_id,
    model,
    provider,
    DATE_TRUNC('day', created_at) AS day,
    SUM(cost_usd) AS total_cost_usd,
    SUM(prompt_tokens) AS total_prompt_tokens,
    SUM(completion_tokens) AS total_completion_tokens,
    COUNT(*) AS total_requests,
    AVG(latency_ms) AS avg_latency_ms
FROM request_logs
WHERE status_code >= 0
GROUP BY org_id, user_id, model, provider, day;
```

This view is refreshed every 5 minutes via `AsyncIOScheduler` (`REFRESH MATERIALIZED VIEW CONCURRENTLY`). Dashboard queries hit this view, not the raw `request_logs` table, ensuring sub-second response times even when logs grow to millions of rows.

## Error Handling

The proxy distinguishes between two types of errors:

### Gateway Errors (Proxy Bugs)

These are failures inside OpenProxyAI and are always critical:

- Auth failure (invalid key, expired key)
- Database unreachable
- Redis unreachable
- Policy evaluation crash
- Configuration invalid

**Header:** `X-OpenProxyAI-Gateway-Error: true`

**Status codes (negative in logs):** -2 (timeout), -3 (cancelled), -4 (policy blocked)

### Provider Errors (Upstream Issues)

These are failures from LLM providers and may be transient:

- OpenAI returns 429 (rate limit)
- Anthropic returns 500 (server error)
- Azure times out

**Header:** `X-OpenProxyAI-Gateway-Error: false`

**Status codes:** HTTP codes from provider (429, 500, 502, 503, 504)

This distinction is critical for alerting and SLA handling. Gateway errors indicate bugs in the proxy; provider errors indicate upstream outages.

## Lifespan Events

The FastAPI app uses the `lifespan()` context manager to:

1. **Startup:** Connect to Redis, initialize SQLAlchemy engine, start APScheduler
2. **Background Jobs:**
   - `refresh_materialized_view()` every 5 minutes (non-blocking concurrent refresh)
   - `archive_old_logs()` every 1 hour (marks logs older than plan retention as archived)
3. **Shutdown:** Close Redis, dispose engine, stop scheduler

All scheduled jobs have `max_instances=1` and `coalesce=True` to prevent concurrent runs if a job takes longer than its interval.
