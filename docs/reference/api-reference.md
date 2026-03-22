# API Reference — OpenProxyAI

Complete reference for OpenProxyAI proxy and management endpoints.

---

## Authentication

All requests to the proxy and management API require an API key in the `Authorization` header.

```
Authorization: Bearer opai_xxxxxxxxxxxxxx
```

API keys are created in the admin console and are stored as SHA-256 hashes on the server. The plaintext key is shown only once during creation.

---

## Proxy Endpoints

### POST /v1/chat/completions

Send a message to an LLM and receive a response. Fully compatible with OpenAI's API.

**Request (messages)**

```json
{
  "model": "openai/gpt-4o-mini",
  "messages": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "What is 2+2?"}
  ],
  "temperature": 0.7,
  "max_tokens": 100,
  "stream": false,
  "top_p": 1.0,
  "frequency_penalty": 0.0,
  "presence_penalty": 0.0
}
```

**Request (prompt_id) — alternative to messages**

Use a saved prompt template from the Playground instead of raw messages. The template is resolved server-side; `prompt_id` and `messages` are mutually exclusive.

```json
{
  "model": "openai/gpt-4o-mini",
  "prompt_id": "550e8400-e29b-41d4-a716-446655440000",
  "variables": {
    "company": "Acme Corp",
    "message": "How do I reset my password?"
  }
}
```

Template variables use `{{name}}` placeholders; missing keys become empty strings. The template's `system_message` (if present) and `user_template` are substituted and built into messages before policy/model selection.

**Query Parameters**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `model` | string | yes | Provider-prefixed model ID: `openai/gpt-4o-mini`, `anthropic/claude-opus`, `azure/gpt-4`, `mistral/mistral-large`, etc. |
| `messages` | array | yes* | Array of message objects with `role` (system/user/assistant) and `content` (string) |
| `prompt_id` | UUID | yes* | ID of a saved prompt template (from Playground). Mutually exclusive with `messages`. |
| `variables` | object | no | Key/value pairs for template substitution when `prompt_id` is used. All values must be strings. |
| `temperature` | float | no | Randomness (0.0–2.0), default 0.7 |
| `max_tokens` | integer | no | Maximum tokens in the response |
| `stream` | boolean | no | Enable server-sent events streaming, default false |
| `top_p` | float | no | Nucleus sampling (0.0–1.0), default 1.0 |
| `frequency_penalty` | float | no | Penalty for repeated tokens (−2.0 to 2.0), default 0.0 |
| `presence_penalty` | float | no | Penalty for new tokens (−2.0 to 2.0), default 0.0 |

\* Provide either `messages` or `prompt_id`, not both. Invalid combinations return HTTP 400.

**Response (non-streaming)**

```json
{
  "id": "chatcmpl-abc123xyz",
  "object": "chat.completion",
  "created": 1710589123,
  "model": "gpt-4o-mini",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "2+2 equals 4."
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 25,
    "completion_tokens": 8,
    "total_tokens": 33
  }
}
```

**Response Headers**

See the [Response Headers](#response-headers) section below.

**Streaming**

Set `stream: true` to receive responses as server-sent events (one JSON object per line).

```
data: {"choices":[{"index":0,"delta":{"content":"Hello"},"finish_reason":null}]}
data: {"choices":[{"index":0,"delta":{"content":" world"},"finish_reason":null}]}
data: [DONE]
```

---

### POST /v1/embeddings

Generate embeddings for text.

**Request**

```json
{
  "model": "openai/text-embedding-3-small",
  "input": "The quick brown fox jumps over the lazy dog."
}
```

**Query Parameters**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `model` | string | yes | Provider-prefixed model ID (e.g., `openai/text-embedding-3-small`, `mistral/mistral-embed`) |
| `input` | string or array | yes | Text or array of texts to embed |

**Response**

```json
{
  "object": "list",
  "data": [
    {
      "object": "embedding",
      "index": 0,
      "embedding": [0.1, -0.2, 0.3, ...]
    }
  ],
  "model": "text-embedding-3-small",
  "usage": {
    "prompt_tokens": 12,
    "total_tokens": 12
  }
}
```

**Response Headers**

All standard OpenProxyAI headers apply (request ID, cost, latency, policy action).

---

### GET /v1/models

List available models for your organization, aggregated from configured provider keys and their `model_patterns`.

**Response (200 OK)**

```json
{
  "object": "list",
  "data": [
    {
      "id": "openai/gpt-4o",
      "object": "model",
      "created": 0,
      "owned_by": "openai"
    },
    {
      "id": "anthropic/claude-3-5-sonnet",
      "object": "model",
      "created": 0,
      "owned_by": "anthropic"
    }
  ]
}
```

Models are derived by expanding `model_patterns` on active provider keys using `litellm.models_by_provider`. If a key has no patterns, all models for that provider are included. Duplicates are removed.

---

### Optional proxy request headers

Send these on `POST /v1/chat/completions` and `POST /v1/embeddings` (gateway **API key** auth — same as `Authorization: Bearer opai_...`).

| Header | Values / format | Purpose |
|--------|-----------------|--------|
| `x-openproxy-cache` | `skip`, `no-store`, `no-cache` | Override cache behavior when caching is enabled (`skip` = bypass read/write; `no-store` = don’t write; `no-cache` = bypass read, still write). |
| `x-openproxy-labels` | JSON object, string keys/values (≤64 chars each, max 10 keys) | Departmental or chargeback labels; stored on request logs / metadata. |
| `x-openproxy-team-id` | UUID | Optional team context; team must exist in the org and the API key’s user must be a member. |
| `x-openproxy-retries` | 0–5 | Per-request override for max provider fallback attempts (0 = no retry, 1–5 = max attempts). |
| `x-openproxy-fallback-model` | `provider/model` (e.g. `openai/gpt-4o-mini`) | When all provider keys fail for the primary model, retry with this alternate model. Must be allowed by org policy. |
| `x-openproxy-session-id` | UUID or opaque string (≤64 chars) | Session/trace ID for grouping related LLM calls; stored in request metadata and filterable in analytics. |

---

## Playground Endpoints

### POST /api/v1/playground/compare

Run the same prompt against multiple models side-by-side. Requires admin or developer role.

**Request**

```json
{
  "models": ["openai/gpt-4o", "anthropic/claude-3-5-sonnet"],
  "messages": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Explain quantum computing in 2 sentences."}
  ],
  "temperature": 0.7,
  "max_tokens": 200
}
```

**Response (200 OK)**

```json
{
  "results": [
    {
      "model": "openai/gpt-4o",
      "content": "Quantum computing uses...",
      "prompt_tokens": 28,
      "completion_tokens": 45,
      "cost_usd": 0.000234,
      "latency_ms": 1250,
      "ttft_ms": 420
    },
    {
      "model": "anthropic/claude-3-5-sonnet",
      "content": "Quantum computers leverage...",
      "prompt_tokens": 28,
      "completion_tokens": 42,
      "cost_usd": 0.000189,
      "latency_ms": 980,
      "ttft_ms": 310
    }
  ]
}
```

Policy evaluation runs for each model before comparison begins. If any model is blocked by policy, the request returns HTTP 403.

### Prompt Template CRUD

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/playground/templates` | List all templates for your org |
| `POST` | `/api/v1/playground/templates` | Create a template |
| `GET` | `/api/v1/playground/templates/{id}` | Get a specific template |
| `PATCH` | `/api/v1/playground/templates/{id}` | Update a template |
| `DELETE` | `/api/v1/playground/templates/{id}` | Soft-delete a template |

**Create Template Request**

```json
{
  "name": "Customer Support",
  "description": "Standard support response template",
  "system_message": "You are a helpful customer support agent for {{company}}.",
  "user_template": "Customer says: {{message}}\n\nRespond helpfully.",
  "variables_schema": [
    {"name": "company", "type": "string", "default": "Acme Corp"},
    {"name": "message", "type": "string"}
  ]
}
```

---

## Compliance Template Endpoints

### GET /api/v1/organizations/current/policy/templates

List available compliance templates.

**Response (200 OK)**

```json
{
  "templates": [
    {
      "id": "healthcare_hipaa",
      "name": "Healthcare — HIPAA",
      "description": "HIPAA-ready policy: PHI keyword blocking, PII detection for SSN/MRN, model allowlist, 7-year audit retention",
      "industry": "healthcare",
      "regulation": "HIPAA"
    },
    {
      "id": "finance_pci",
      "name": "Finance — PCI-DSS",
      "description": "PCI-compliant policy: credit card detection, trade compliance keywords, SOX audit format",
      "industry": "finance",
      "regulation": "PCI-DSS"
    },
    {
      "id": "government_fedramp",
      "name": "Government — FedRAMP",
      "description": "FedRAMP-aligned policy: US-only models, classified keyword blocking, strict enforcement",
      "industry": "government",
      "regulation": "FedRAMP"
    }
  ]
}
```

### POST /api/v1/organizations/current/policy/apply-template

Apply a compliance template to your organization's policy. Uses merge semantics: the template's settings are applied on top of existing policy, preserving your current `allowed_models` and `model_rate_limits`.

**Request**

```json
{
  "template_id": "healthcare_hipaa"
}
```

**Response (200 OK)** — Returns the merged policy configuration.

---

## Response Headers

Every response from the proxy includes the following headers:

| Header | Type | Description |
|--------|------|-------------|
| `X-OpenProxyAI-Request-Id` | string | Unique request ID for log lookup in the admin console |
| `X-OpenProxyAI-Provider` | string | Provider name (`openai`, `anthropic`, `azure`, `mistral`, etc.) |
| `X-OpenProxyAI-Model` | string | Model name routed to |
| `X-OpenProxyAI-Cost-USD` | float | Exact cost in USD (input + output tokens) |
| `X-OpenProxyAI-Latency-Ms` | integer | Total gateway latency in milliseconds |
| `X-OpenProxyAI-TTFT-Ms` | integer | Time to first token (streaming only) |
| `X-OpenProxyAI-Cache` | string | `hit` or `miss` (only if caching is enabled) |
| `X-OpenProxyAI-Policy-Action` | string | Policy decision: `allow`, `block`, or `log_only` |
| `X-OpenProxyAI-Policy-Reason` | string | Reason code if blocked (e.g., `blocked_keyword`, `model_not_allowed`) |
| `X-OpenProxyAI-Gateway-Error` | boolean | `true` if error originated in gateway (not the provider) |
| `X-RateLimit-Limit-Rpm` | integer | Your requests-per-minute limit |
| `X-RateLimit-Remaining-Rpm` | integer | Remaining requests this minute |
| `X-OpenProxyAI-Budget-Remaining-Usd` | float | Daily budget remaining in USD |

---

## Error Codes

| HTTP Code | Meaning | When | Example |
|-----------|---------|------|---------|
| 400 | Bad Request | Invalid request schema, missing required field | Missing `model` or malformed `messages` array |
| 401 | Unauthorized | Missing or invalid API key | `Authorization` header missing or invalid |
| 402 | Payment Required | Daily budget exceeded | Spend today >= daily budget limit |
| 403 | Forbidden | Request blocked by policy | Blocked keyword detected, model not allowed, or PII found |
| 429 | Too Many Requests | Rate limit exceeded | Exceeded RPM or TPM limit |
| 502 | Bad Gateway | Provider returned an error | OpenAI API error, Anthropic API error, etc. |
| 503 | Service Unavailable | No active provider key | No configured provider key for the requested provider |
| 504 | Gateway Timeout | Provider timeout | Provider did not respond within timeout window |

---

## Management API authentication

Endpoints under `/api/v1/` (except the proxy’s `/v1/chat/*` and `/v1/embeddings`) expect a **JWT access token** from email/password (or SSO) login in the admin console — not the gateway API key:

```
Authorization: Bearer <jwt_access_token>
```

The gateway OpenAI-compatible surface (`/v1/chat/completions`, `/v1/embeddings`, `/v1/models`) uses **API keys** (`opai_...`) as documented in [Authentication](#authentication) above.

---

## Teams API

Prefix: `/api/v1/teams`. **JWT required.** **Admin role only** for every endpoint (list, get, create, update, delete, add/remove members).

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/teams` | List teams with member counts |
| `POST` | `/api/v1/teams` | Create team (`name`, optional `budget_monthly_usd`) |
| `GET` | `/api/v1/teams/{team_id}` | Team detail + members |
| `PATCH` | `/api/v1/teams/{team_id}` | Update name / budget |
| `DELETE` | `/api/v1/teams/{team_id}` | Delete team |
| `POST` | `/api/v1/teams/{team_id}/members/{user_id}` | Add user to team |
| `DELETE` | `/api/v1/teams/{team_id}/members/{user_id}` | Remove user from team |

---

## Experiments (A/B testing) API

Prefix: `/api/v1/experiments`. **JWT required.**

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/experiments` | List experiments |
| `POST` | `/api/v1/experiments` | Create (admin) — `name`, `target_model`, `variants[]` with `model` + `traffic_weight` |
| `GET` | `/api/v1/experiments/{id}` | Get one |
| `PATCH` | `/api/v1/experiments/{id}` | Update (admin) |
| `DELETE` | `/api/v1/experiments/{id}` | Delete (admin) |
| `POST` | `/api/v1/experiments/{id}/start` | Activate (admin) |
| `POST` | `/api/v1/experiments/{id}/stop` | Deactivate (admin) |
| `GET` | `/api/v1/experiments/{id}/results` | Aggregated metrics per variant from logs |

When the org policy **`allowed_models`** list is non-empty, create/update reject models not on the allowlist (HTTP 400).

Traffic routing happens on **`POST /v1/chat/completions`** when the request `model` matches an active experiment’s `target_model`. See [Experiments & teams guide](../guides/experiments-and-teams.md).

**Results with quality scores:** `GET /api/v1/experiments/{id}/results` returns per-variant metrics (latency, cost, tokens, policy violations) and **scores** (avg, count per score name) when scores have been submitted via the Request Scores API.

---

## Request Scores API

Prefix: `/api/v1/requests`. **JWT required.** Submit quality scores per request for experiment evaluation (LLM-as-judge, external evals).

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/requests/{request_id}/scores` | Submit quality scores for a request |

**Submit scores request**

```json
{
  "scores": [
    {"name": "coherence", "value": 4.5},
    {"name": "relevance", "value": 3.8}
  ]
}
```

- `request_id`: Gateway request UUID from `X-OpenProxyAI-Request-Id` response header
- Request must exist in `request_logs` and belong to the caller's org (404 if not found)
- For experiment requests, `experiment_id` and `variant_id` are derived from `request_metadata` and stored with the score
- Scores are upserted by `(request_id, score_name)` — re-POSTing the same name updates the value
- `GET /api/v1/experiments/{id}/results` includes `scores` per variant when present

**Response (200 OK)**

```json
{"submitted": 2}
```

---

## Billing API (Stripe)

Prefix: `/api/v1/billing`. **JWT required.** Checkout/portal: **admin** only. Webhook: Stripe signature, no JWT.

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/billing/checkout` | Body `{ "plan": "starter" \| "growth" \| "metered" }` → Stripe Checkout URL |
| `POST` | `/api/v1/billing/portal` | Customer Portal URL for subscription self-service |
| `POST` | `/api/v1/billing/webhook` | Stripe events (`checkout.session.completed`, invoices, subscriptions, …) |

Metered usage and env vars: [Stripe setup guide](../guides/stripe-setup.md#9-usage-based-metered-plan-optional).

---

## Management Endpoints

### GET /api/v1/organizations/current

Get your organization's profile.

**Response**

```json
{
  "id": "org_abc123xyz",
  "name": "Acme Corp",
  "slug": "acme-corp",
  "plan": "enterprise",
  "budget_monthly_usd": 5000,
  "settings": {
    "policy": {
      "enforcement_mode": "block",
      "model_allowlist": ["openai/gpt-4o-mini", "anthropic/claude-opus"],
      "blocked_keywords": ["password", "secret"],
      "pii_detection_enabled": true
    }
  },
  "created_at": "2026-01-15T10:00:00Z",
  "updated_at": "2026-03-16T12:34:56Z"
}
```

---

### PATCH /api/v1/organizations/current/policy

Update your organization's policy configuration. Merge-updates the existing policy (only provided fields are changed).

**Request**

```json
{
  "enforcement_mode": "block",
  "blocked_keywords": ["password", "api_key"],
  "pii_detection_enabled": true,
  "pii_patterns": ["email", "ssn"]
}
```

**Response**

```json
{
  "enforcement_mode": "block",
  "model_allowlist": [],
  "model_blocklist": [],
  "blocked_keywords": ["password", "api_key"],
  "pii_detection_enabled": true,
  "pii_patterns": ["email", "ssn", "credit_card"],
  "updated_at": "2026-03-16T12:35:00Z"
}
```

---

### GET /api/v1/analytics/logs

List all requests for your organization. Paginated and filterable.

**Query Parameters**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `page` | integer | 1 | Page number |
| `limit` | integer | 50 | Results per page (max 200) |
| `model` | string | — | Filter by model (e.g., `gpt-4o-mini`) |
| `status` | string | — | Filter by HTTP status (e.g., `200`, `403`) |
| `policy_action` | string | — | Filter by policy action (`allow`, `block`, `log_only`) |

**Response**

```json
{
  "data": [
    {
      "id": "log_abc123xyz",
      "request_id": "req_123abc",
      "model": "gpt-4o-mini",
      "provider": "openai",
      "status": 200,
      "cost_usd": 0.000234,
      "latency_ms": 1250,
      "ttft_ms": 450,
      "tokens_in": 25,
      "tokens_out": 8,
      "policy_action": "allow",
      "policy_reason": null,
      "user_id": "user_xyz789",
      "created_at": "2026-03-16T12:30:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 50,
    "total": 12450,
    "pages": 249
  }
}
```

---

### GET /api/v1/analytics/overview

Get aggregated usage metrics for your organization.

**Query Parameters**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `period_days` | integer | 7 | Days of history (1–90) |

**Response**

```json
{
  "period_days": 7,
  "total_requests": 1243,
  "total_cost_usd": 12.45,
  "total_tokens_in": 450000,
  "total_tokens_out": 120000,
  "avg_latency_ms": 1205,
  "by_model": {
    "gpt-4o-mini": {
      "requests": 950,
      "cost_usd": 8.20,
      "tokens_in": 340000,
      "tokens_out": 90000
    },
    "claude-opus": {
      "requests": 293,
      "cost_usd": 4.25,
      "tokens_in": 110000,
      "tokens_out": 30000
    }
  },
  "by_provider": {
    "openai": {
      "requests": 950,
      "cost_usd": 8.20
    },
    "anthropic": {
      "requests": 293,
      "cost_usd": 4.25
    }
  }
}
```

---

### GET /health

Health check endpoint. Used for liveness and readiness probes.

**Response (200 OK)**

```json
{
  "status": "healthy",
  "database": "connected",
  "redis": "connected"
}
```

**Response (503 Service Unavailable)**

```json
{
  "status": "unhealthy",
  "database": "disconnected",
  "redis": "connected"
}
```

---

## Rate Limits

The proxy enforces three types of rate limits (configurable per organization):

| Limit Type | Default | Description |
|-----------|---------|-------------|
| RPM (Requests Per Minute) | 1000 | Max requests per minute |
| TPM (Tokens Per Minute) | 100000 | Max tokens per minute (input + output) |
| Daily Budget | $100 | Max spend per day (USD) |

Hitting a rate limit returns HTTP 429 with `Retry-After` header:

```
HTTP/1.1 429 Too Many Requests
Retry-After: 45
X-RateLimit-Limit-Rpm: 1000
X-RateLimit-Remaining-Rpm: 0
Content-Type: application/json

{
  "error": {
    "message": "Rate limit exceeded: requests per minute",
    "type": "rate_limit_exceeded"
  }
}
```

---

## Examples

### Example: Chat with Streaming

```bash
curl -X POST https://your-org.openproxyai.com/v1/chat/completions \
  -H "Authorization: Bearer opai_xxxxxxxxxxxxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "openai/gpt-4o-mini",
    "messages": [{"role": "user", "content": "Tell me a joke"}],
    "stream": true
  }' \
  -N
```

### Example: Create an Embedding

```bash
curl -X POST https://your-org.openproxyai.com/v1/embeddings \
  -H "Authorization: Bearer opai_xxxxxxxxxxxxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "openai/text-embedding-3-small",
    "input": "Hello world"
  }'
```

### Example: Get Organization Info

```bash
curl https://your-org.openproxyai.com/api/v1/organizations/current \
  -H "Authorization: Bearer opai_xxxxxxxxxxxxxx"
```

---

## SDK Support

OpenProxyAI provides official SDKs for popular languages. All endpoints are accessible via the SDKs with type safety and idiomatic error handling.

- **Python** — `openproxy-ai` on PyPI (sync + async)
- **TypeScript/JavaScript** — `openproxy-ai` on npm (ESM + CJS)

See [quickstart.md](../getting-started/quickstart.md) for SDK usage examples.
