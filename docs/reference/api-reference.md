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

**Request**

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

**Query Parameters**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `model` | string | yes | Provider-prefixed model ID: `openai/gpt-4o-mini`, `anthropic/claude-opus`, `azure/gpt-4`, `mistral/mistral-large`, etc. |
| `messages` | array | yes | Array of message objects with `role` (system/user/assistant) and `content` (string) |
| `temperature` | float | no | Randomness (0.0–2.0), default 0.7 |
| `max_tokens` | integer | no | Maximum tokens in the response |
| `stream` | boolean | no | Enable server-sent events streaming, default false |
| `top_p` | float | no | Nucleus sampling (0.0–1.0), default 1.0 |
| `frequency_penalty` | float | no | Penalty for repeated tokens (−2.0 to 2.0), default 0.0 |
| `presence_penalty` | float | no | Penalty for new tokens (−2.0 to 2.0), default 0.0 |

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

See [quickstart.md](./quickstart.md) for SDK usage examples.
