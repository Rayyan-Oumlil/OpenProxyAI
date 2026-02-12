# API Design - OpenProxyAI

## 🎯 API Philosophy

**Principles:**
1. **OpenAI Compatible** - Drop-in replacement for existing code
2. **RESTful** - Standard HTTP methods, predictable URLs
3. **Versioned** - Explicit versions in URL (`/v1/`)
4. **Well-Documented** - OpenAPI spec with examples
5. **Consistent** - Same patterns everywhere

---

## 🔌 Core Endpoints

### LLM Proxy API (OpenAI-Compatible)

#### POST /v1/chat/completions

**OpenAI-compatible chat completions endpoint**

```http
POST https://api.openproxyai.com/v1/chat/completions
Authorization: Bearer sk-proj-abc123...
Content-Type: application/json

{
  "model": "gpt-4",
  "messages": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "What is 2+2?"}
  ],
  "temperature": 0.7,
  "max_tokens": 150,
  "stream": false
}
```

**Response:**
```json
{
  "id": "chatcmpl-abc123",
  "object": "chat.completion",
  "created": 1707739245,
  "model": "gpt-4",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "2 + 2 equals 4."
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 20,
    "completion_tokens": 8,
    "total_tokens": 28
  },
  "x_openproxyai": {
    "request_id": "req_xyz789",
    "provider": "openai",
    "cost_usd": 0.00084,
    "latency_ms": 1250,
    "cached": false
  }
}
```

**Streaming Response:**
```http
POST /v1/chat/completions
{
  "model": "gpt-4",
  "messages": [...],
  "stream": true
}
```

```
data: {"id":"chatcmpl-abc","choices":[{"delta":{"role":"assistant"}}]}

data: {"id":"chatcmpl-abc","choices":[{"delta":{"content":"2"}}]}

data: {"id":"chatcmpl-abc","choices":[{"delta":{"content":" +"}}]}

data: {"id":"chatcmpl-abc","choices":[{"delta":{"content":" 2"}}]}

data: [DONE]
```

---

#### POST /v1/completions

**Text completions (legacy OpenAI format)**

```http
POST /v1/completions
{
  "model": "gpt-3.5-turbo-instruct",
  "prompt": "Once upon a time",
  "max_tokens": 50
}
```

---

#### POST /v1/embeddings

**Generate embeddings**

```http
POST /v1/embeddings
{
  "model": "text-embedding-ada-002",
  "input": "The quick brown fox jumps over the lazy dog"
}
```

**Response:**
```json
{
  "object": "list",
  "data": [
    {
      "object": "embedding",
      "embedding": [0.0023, -0.0021, ...],
      "index": 0
    }
  ],
  "model": "text-embedding-ada-002",
  "usage": {
    "prompt_tokens": 10,
    "total_tokens": 10
  },
  "x_openproxyai": {
    "cost_usd": 0.00001,
    "provider": "openai"
  }
}
```

---

### Management API (OpenProxyAI-Specific)

#### Authentication

All management APIs require Bearer token authentication:

```http
Authorization: Bearer opr_secret_abc123xyz...
```

---

#### GET /api/v1/organizations/{org_id}

**Get organization details**

```http
GET /api/v1/organizations/org_abc123
Authorization: Bearer opr_secret_...
```

**Response:**
```json
{
  "id": "org_abc123",
  "name": "Acme Corp",
  "slug": "acme-corp",
  "plan": "growth",
  "settings": {
    "default_model": "gpt-4",
    "enforce_budget_limits": true,
    "pii_detection_enabled": true
  },
  "usage": {
    "current_month_cost_usd": 1250.45,
    "current_month_requests": 15430,
    "monthly_budget_usd": 5000.00
  },
  "created_at": "2026-01-15T10:30:00Z"
}
```

---

#### GET /api/v1/users

**List users in organization**

```http
GET /api/v1/users?page=1&limit=50
Authorization: Bearer opr_secret_...
```

**Response:**
```json
{
  "data": [
    {
      "id": "usr_123",
      "email": "john@acme.com",
      "name": "John Doe",
      "role": "user",
      "department_id": "dept_abc",
      "budget_daily_usd": 50.00,
      "budget_monthly_usd": 1000.00,
      "is_active": true,
      "created_at": "2026-01-20T14:22:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 50,
    "total": 127,
    "pages": 3
  }
}
```

---

#### POST /api/v1/users

**Create new user**

```http
POST /api/v1/users
{
  "email": "jane@acme.com",
  "name": "Jane Smith",
  "role": "user",
  "department_id": "dept_abc",
  "budget_daily_usd": 25.00,
  "budget_monthly_usd": 500.00
}
```

**Response:**
```json
{
  "id": "usr_456",
  "email": "jane@acme.com",
  "name": "Jane Smith",
  "role": "user",
  "department_id": "dept_abc",
  "budget_daily_usd": 25.00,
  "budget_monthly_usd": 500.00,
  "is_active": true,
  "created_at": "2026-02-12T16:45:00Z",
  "api_key_preview": "sk-proj-abc123...xyz"
}
```

---

#### GET /api/v1/api-keys

**List API keys for current user**

```http
GET /api/v1/api-keys
Authorization: Bearer opr_secret_...
```

**Response:**
```json
{
  "data": [
    {
      "id": "key_abc123",
      "name": "Production Key",
      "key_prefix": "sk-proj-abc1",
      "permissions": ["llm:chat", "llm:embed"],
      "last_used_at": "2026-02-12T10:30:00Z",
      "usage_7d": {
        "requests": 1234,
        "cost_usd": 45.67
      },
      "expires_at": null,
      "created_at": "2026-01-15T09:00:00Z"
    }
  ]
}
```

---

#### POST /api/v1/api-keys

**Generate new API key**

```http
POST /api/v1/api-keys
{
  "name": "Development Key",
  "permissions": ["llm:chat"],
  "expires_at": "2026-12-31T23:59:59Z"
}
```

**Response:**
```json
{
  "id": "key_xyz789",
  "name": "Development Key",
  "key": "sk-proj-xyz789abcdef...",
  "key_prefix": "sk-proj-xyz7",
  "permissions": ["llm:chat"],
  "expires_at": "2026-12-31T23:59:59Z",
  "created_at": "2026-02-12T16:50:00Z",
  "warning": "This is the only time you'll see the full key. Store it securely."
}
```

---

#### DELETE /api/v1/api-keys/{key_id}

**Revoke API key**

```http
DELETE /api/v1/api-keys/key_xyz789
Authorization: Bearer opr_secret_...
```

**Response:**
```json
{
  "id": "key_xyz789",
  "revoked": true,
  "revoked_at": "2026-02-12T17:00:00Z"
}
```

---

### Analytics API

#### GET /api/v1/analytics/overview

**Get high-level overview**

```http
GET /api/v1/analytics/overview?period=7d
Authorization: Bearer opr_secret_...
```

**Response:**
```json
{
  "period": "7d",
  "metrics": {
    "total_requests": 15430,
    "total_cost_usd": 234.56,
    "total_tokens": 1234567,
    "avg_latency_ms": 1250,
    "error_rate": 0.012
  },
  "top_models": [
    {"model": "gpt-4", "requests": 8430, "cost_usd": 189.23},
    {"model": "gpt-3.5-turbo", "requests": 7000, "cost_usd": 45.33}
  ],
  "top_users": [
    {"user_id": "usr_123", "name": "John Doe", "cost_usd": 89.45},
    {"user_id": "usr_456", "name": "Jane Smith", "cost_usd": 67.23}
  ],
  "cost_by_day": [
    {"date": "2026-02-06", "cost_usd": 32.45},
    {"date": "2026-02-07", "cost_usd": 28.90},
    {"date": "2026-02-08", "cost_usd": 41.20}
  ]
}
```

---

#### GET /api/v1/analytics/costs

**Detailed cost breakdown**

```http
GET /api/v1/analytics/costs?start_date=2026-02-01&end_date=2026-02-12&group_by=user,model
```

**Response:**
```json
{
  "start_date": "2026-02-01",
  "end_date": "2026-02-12",
  "total_cost_usd": 1234.56,
  "breakdown": [
    {
      "user_id": "usr_123",
      "user_name": "John Doe",
      "model": "gpt-4",
      "requests": 450,
      "input_tokens": 45000,
      "output_tokens": 90000,
      "cost_usd": 156.75
    }
  ]
}
```

---

#### GET /api/v1/analytics/usage

**Usage patterns and trends**

```http
GET /api/v1/analytics/usage?period=30d&metric=requests
```

**Response:**
```json
{
  "period": "30d",
  "metric": "requests",
  "data": [
    {"timestamp": "2026-01-13T00:00:00Z", "value": 450},
    {"timestamp": "2026-01-14T00:00:00Z", "value": 520},
    {"timestamp": "2026-01-15T00:00:00Z", "value": 610}
  ],
  "summary": {
    "total": 15430,
    "avg_per_day": 514,
    "peak_day": "2026-02-10",
    "peak_value": 890
  }
}
```

---

### Audit Log API

#### GET /api/v1/audit-logs

**Query audit logs**

```http
GET /api/v1/audit-logs?start_date=2026-02-01&user_id=usr_123&limit=100
Authorization: Bearer opr_secret_...
```

**Response:**
```json
{
  "data": [
    {
      "id": "log_abc123",
      "timestamp": "2026-02-12T10:30:45Z",
      "user_id": "usr_123",
      "user_email": "john@acme.com",
      "action": "llm_request",
      "model": "gpt-4",
      "provider": "openai",
      "input_tokens": 500,
      "output_tokens": 1500,
      "cost_usd": 0.105,
      "latency_ms": 2340,
      "status": "success",
      "metadata": {
        "ip_address": "10.0.1.5",
        "user_agent": "openproxyai-sdk/1.0"
      }
    }
  ],
  "pagination": {
    "limit": 100,
    "offset": 0,
    "total": 15430
  }
}
```

---

#### POST /api/v1/audit-logs/export

**Export audit logs (compliance)**

```http
POST /api/v1/audit-logs/export
{
  "start_date": "2026-01-01",
  "end_date": "2026-12-31",
  "format": "csv",
  "include_prompts": false
}
```

**Response:**
```json
{
  "export_id": "exp_abc123",
  "status": "processing",
  "estimated_completion": "2026-02-12T17:05:00Z",
  "download_url": null
}
```

**Check status:**
```http
GET /api/v1/audit-logs/exports/exp_abc123
```

**Response (when ready):**
```json
{
  "export_id": "exp_abc123",
  "status": "completed",
  "download_url": "https://s3.../audit-logs-2026.csv?signed=...",
  "expires_at": "2026-02-13T17:00:00Z",
  "size_bytes": 15234567
}
```

---

### Policy API (Enterprise)

#### GET /api/v1/policies

**List policies**

```http
GET /api/v1/policies
Authorization: Bearer opr_secret_...
```

**Response:**
```json
{
  "data": [
    {
      "id": "pol_abc123",
      "name": "PII Detection",
      "type": "content",
      "enabled": true,
      "config": {
        "action": "block",
        "patterns": ["ssn", "credit_card", "email"],
        "notify_admin": true
      },
      "created_at": "2026-01-15T10:00:00Z"
    },
    {
      "id": "pol_xyz789",
      "name": "Rate Limit - Users",
      "type": "rate_limit",
      "enabled": true,
      "config": {
        "limit": 100,
        "window": "1h",
        "scope": "user"
      },
      "created_at": "2026-01-15T10:05:00Z"
    }
  ]
}
```

---

#### POST /api/v1/policies

**Create policy**

```http
POST /api/v1/policies
{
  "name": "Budget Limit - Engineering Dept",
  "type": "budget",
  "enabled": true,
  "config": {
    "department_id": "dept_eng",
    "monthly_limit_usd": 10000.00,
    "alert_threshold": 0.8,
    "action": "block"
  }
}
```

---

## 🔐 Authentication

### API Key Format

```
sk-proj-{8_char_random}_{32_char_secret}

Example: sk-proj-abc12345_xyz789abcdef0123456789abcdef01
```

**Storage:** Only hash is stored (bcrypt), never plaintext

### Token Scopes

```json
{
  "scopes": [
    "llm:chat",           // Call chat completions
    "llm:completion",     // Call text completions
    "llm:embedding",      // Generate embeddings
    "analytics:read",     // View analytics
    "users:read",         // List users (admin)
    "users:write",        // Create/update users (admin)
    "policies:read",      // View policies (admin)
    "policies:write",     // Create/update policies (admin)
    "audit:read",         // View audit logs (admin)
    "audit:export"        // Export audit logs (admin)
  ]
}
```

---

## 📊 Rate Limiting

### Headers

Every response includes rate limit headers:

```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 87
X-RateLimit-Reset: 1707742800
X-RateLimit-Window: 3600
```

### Rate Limit Response

```http
HTTP/1.1 429 Too Many Requests
Content-Type: application/json
Retry-After: 3600

{
  "error": {
    "type": "rate_limit_exceeded",
    "message": "Rate limit exceeded. Limit: 100 requests per hour.",
    "limit": 100,
    "window": "1h",
    "reset_at": "2026-02-12T18:00:00Z"
  }
}
```

---

## ❌ Error Handling

### Error Response Format

```json
{
  "error": {
    "type": "invalid_request_error",
    "message": "The 'model' field is required.",
    "param": "model",
    "code": "missing_required_field"
  }
}
```

### Error Types

| HTTP Status | Error Type | Description |
|-------------|------------|-------------|
| 400 | `invalid_request_error` | Invalid request parameters |
| 401 | `authentication_error` | Invalid or missing API key |
| 403 | `permission_error` | Insufficient permissions |
| 402 | `budget_exceeded_error` | Budget limit reached |
| 429 | `rate_limit_exceeded` | Too many requests |
| 500 | `internal_error` | Server error |
| 503 | `service_unavailable` | Temporary outage |

---

## 📝 OpenAPI Specification

Full OpenAPI 3.0 spec available at:
```
https://api.openproxyai.com/openapi.json
```

Import into Postman, Insomnia, or any API client.

---

## 🔌 SDKs

### Official SDKs

**Python:**
```python
from openproxyai import OpenProxyAI

client = OpenProxyAI(api_key="sk-proj-...")

response = client.chat.completions.create(
    model="gpt-4",
    messages=[
        {"role": "user", "content": "Hello!"}
    ]
)

print(response.choices[0].message.content)
```

**TypeScript/JavaScript:**
```typescript
import { OpenProxyAI } from 'openproxyai';

const client = new OpenProxyAI({
  apiKey: 'sk-proj-...'
});

const response = await client.chat.completions.create({
  model: 'gpt-4',
  messages: [
    { role: 'user', content: 'Hello!' }
  ]
});

console.log(response.choices[0].message.content);
```

### Community SDKs

- Go (coming soon)
- Ruby (coming soon)
- Java (community-maintained)

---

## 🚀 Migration Guide

### From OpenAI Direct → OpenProxyAI

**Before:**
```python
from openai import OpenAI

client = OpenAI(api_key="sk-...")  # OpenAI key

response = client.chat.completions.create(
    model="gpt-4",
    messages=[...]
)
```

**After (Option 1: SDK):**
```python
from openproxyai import OpenAI  # Changed import

client = OpenAI(api_key="sk-proj-...")  # OpenProxyAI key

response = client.chat.completions.create(
    model="gpt-4",
    messages=[...]
)
```

**After (Option 2: Base URL):**
```python
from openai import OpenAI

client = OpenAI(
    api_key="sk-proj-...",  # OpenProxyAI key
    base_url="https://api.openproxyai.com/v1"  # Added
)

response = client.chat.completions.create(
    model="gpt-4",
    messages=[...]
)
```

**That's it! No other code changes needed.**

---

## 📚 API Best Practices

### 1. Use Streaming for Chat

```python
# ✅ Good: Streaming
for chunk in client.chat.completions.create(
    model="gpt-4",
    messages=[...],
    stream=True
):
    print(chunk.choices[0].delta.content)

# ❌ Bad: Blocking wait for full response
response = client.chat.completions.create(
    model="gpt-4",
    messages=[...],
    stream=False  # User waits 10+ seconds
)
```

### 2. Handle Rate Limits

```python
import time
from openproxyai import OpenProxyAI
from openproxyai.errors import RateLimitError

client = OpenProxyAI(api_key="...")

def call_with_retry(max_retries=3):
    for attempt in range(max_retries):
        try:
            return client.chat.completions.create(...)
        except RateLimitError as e:
            if attempt == max_retries - 1:
                raise
            time.sleep(2 ** attempt)  # Exponential backoff
```

### 3. Set Budget Alerts

```python
# Set up budget alerts via API
client.organizations.update_settings(
    budget_monthly_usd=1000.00,
    alert_threshold=0.8,  # Alert at 80%
    alert_email="admin@company.com"
)
```

### 4. Tag Requests for Analytics

```python
response = client.chat.completions.create(
    model="gpt-4",
    messages=[...],
    user="user_123",  # For per-user tracking
    metadata={
        "feature": "chatbot",
        "department": "support"
    }
)
```

---

*Next: [Business Model & Pricing →](../13_Business_Model/pricing_strategy.md)*
