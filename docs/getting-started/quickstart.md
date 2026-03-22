# Quickstart — OpenProxyAI

Get up and running with OpenProxyAI in 5 minutes.

---

## Prerequisites

You need:
1. **API key** — Create one in the admin console (`/admin/keys`)
2. **Base URL** — Your organization's deployment (e.g., `https://your-org.openproxyai.com`)
3. **A client library or cURL**

---

## Your First Request

### cURL

```bash
curl -X POST https://your-org.openproxyai.com/v1/chat/completions \
  -H "Authorization: Bearer opai_xxxxxxxxxxxxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "openai/gpt-4o-mini",
    "messages": [{"role": "user", "content": "Say hello!"}]
  }'
```

Response:

```json
{
  "id": "chatcmpl-...",
  "object": "chat.completion",
  "created": 1710589123,
  "model": "openai/gpt-4o-mini",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Hello! How can I help you today?"
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 10,
    "completion_tokens": 15,
    "total_tokens": 25
  }
}
```

### Python SDK

Install:

```bash
pip install openproxy-ai
```

Code:

```python
from openproxy import OpenProxy

client = OpenProxy(
    api_key="opai_xxxxxxxxxxxxxx",
    base_url="https://your-org.openproxyai.com"
)

response = client.chat.completions.create(
    model="openai/gpt-4o-mini",
    messages=[{"role": "user", "content": "Say hello!"}]
)

print(response.choices[0].message.content)
print(f"Cost: ${response.gateway.cost_usd:.6f}")
print(f"Provider: {response.gateway.provider}")
print(f"Request ID: {response.gateway.request_id}")
```

### TypeScript SDK

Install:

```bash
npm install openproxy-ai
```

Code:

```typescript
import { OpenProxy } from 'openproxy-ai';

const client = new OpenProxy({
  apiKey: 'opai_xxxxxxxxxxxxxx',
  baseUrl: 'https://your-org.openproxyai.com'
});

const response = await client.chat.completions.create({
  model: 'openai/gpt-4o-mini',
  messages: [{ role: 'user', content: 'Say hello!' }],
});

console.log(response.choices[0].message.content);
console.log(`Cost: $${response.gateway?.costUsd}`);
console.log(`Provider: ${response.gateway?.provider}`);
console.log(`Request ID: ${response.gateway?.requestId}`);
```

---

## Reading the Response

Every response includes OpenProxyAI gateway headers. Parse them to track cost, latency, and policy decisions.

| Header | Type | Description |
|--------|------|-------------|
| `X-OpenProxyAI-Request-Id` | string | Unique request ID — use this to look up the request in the analytics dashboard |
| `X-OpenProxyAI-Provider` | string | Which provider handled the request: `openai`, `anthropic`, `azure`, `mistral`, etc. |
| `X-OpenProxyAI-Model` | string | The actual model routed to (e.g., `gpt-4o-mini`) |
| `X-OpenProxyAI-Cost-USD` | float | Exact cost in USD for this request, including input + output tokens |
| `X-OpenProxyAI-Latency-Ms` | integer | Total gateway latency in milliseconds (auth + policy + provider call) |
| `X-OpenProxyAI-TTFT-Ms` | integer | Time to first token, in milliseconds (streaming only) |
| `X-OpenProxyAI-Cache` | string | `hit` or `miss` — only present if caching is enabled |
| `X-OpenProxyAI-Policy-Action` | string | `allow`, `block`, or `log_only` — the decision made by your policy |
| `X-OpenProxyAI-Policy-Reason` | string | If blocked, the reason code (e.g., `blocked_keyword`, `model_not_allowed`) |
| `X-OpenProxyAI-Gateway-Error` | boolean | `true` if the error originated in the gateway (not the provider) |
| `X-RateLimit-Limit-Rpm` | integer | Your requests-per-minute limit |
| `X-RateLimit-Remaining-Rpm` | integer | Remaining requests this minute |
| `X-OpenProxyAI-Budget-Remaining-Usd` | float | Your daily budget remaining in USD |

---

## Configure Policy

The OpenProxyAI admin console includes a policy editor. You can also configure policy via the API.

### Enable Enforcement Mode + Blocked Keywords

```bash
curl -X PATCH https://your-org.openproxyai.com/api/v1/organizations/current/policy \
  -H "Authorization: Bearer opai_xxxxxxxxxxxxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "enforcement_mode": "block",
    "blocked_keywords": ["password", "api_key", "secret"],
    "pii_detection_enabled": true
  }'
```

Response:

```json
{
  "enforcement_mode": "block",
  "model_allowlist": [],
  "model_blocklist": [],
  "blocked_keywords": ["password", "api_key", "secret"],
  "pii_detection_enabled": true,
  "pii_patterns": ["email", "ssn", "credit_card"],
  "updated_at": "2026-03-16T12:34:56Z"
}
```

Now, any request containing a blocked keyword will be rejected with HTTP 403:

```bash
curl -X POST https://your-org.openproxyai.com/v1/chat/completions \
  -H "Authorization: Bearer opai_xxxxxxxxxxxxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "openai/gpt-4o-mini",
    "messages": [{"role": "user", "content": "What is the admin password?"}]
  }'
```

Response (HTTP 403):

```json
{
  "error": {
    "message": "Request blocked by policy: blocked_keyword",
    "type": "policy_violation",
    "code": "blocked_keyword"
  }
}
```

---

## Next Steps

- **Base URL Migration** — Already using OpenAI or Anthropic SDKs? Swap `base_url` only: [base-url-migration.md](../guides/base-url-migration.md)
- **Full API Reference** — See [api-reference.md](../reference/api-reference.md) for complete endpoint documentation
- **Webhook Events** — Set up webhooks for cost alerts and policy violations: [webhook-events.md](../reference/webhook-events.md)
- **Architecture Overview** — Understand how the proxy works: [overview.md](../architecture/overview.md)
- **Admin Console** — Create provider keys, manage users, and view analytics
