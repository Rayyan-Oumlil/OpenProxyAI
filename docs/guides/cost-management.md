# Cost Management

> **Applies to:** All plans

OpenProxyAI tracks LLM spending in real time and enforces budgets at the organization and user levels. This guide covers budget configuration, cost tracking, anomaly detection, and analytics.

## Budget Overview

Budgets are daily or monthly spending caps, enforced per request. When a budget is exceeded, the request is rejected with HTTP 402 (Payment Required).

### Budget Levels

| Level | Type | Scope | Field |
|-------|------|-------|-------|
| Organization | Daily | All users in org | `Organization.budget_monthly_usd` |
| Organization | Monthly | All users in org | `Organization.budget_monthly_usd` |
| User | Daily | Individual user | `User.budget_daily_usd` |
| User | Monthly | Individual user | `User.budget_monthly_usd` |

Currently implemented:

- **Organization daily budget:** Tracks `rl:usd:{org_id}:{YYYY-MM-DD}` in Redis
- **User daily budget:** Tracks `rl:usd:user:{user_id}:{YYYY-MM-DD}` in Redis
- **Organization monthly budget:** Configured but enforced by plan limits

## Setting Organization Budget

Set the organization's monthly budget:

```bash
curl -X PATCH https://api.openproxy.ai/api/v1/organizations/current \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "budget_monthly_usd": 10000.00
  }'
```

This budget applies to all users in the organization. Users can have individual daily budgets that supersede the org limit.

## Setting User Budget

Set a per-user daily budget (requires admin role):

```bash
curl -X PATCH https://api.openproxy.ai/api/v1/users/{user_id} \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "budget_daily_usd": 50.00,
    "budget_monthly_usd": 1000.00
  }'
```

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `budget_daily_usd` | decimal | Max spending per calendar day |
| `budget_monthly_usd` | decimal | Max spending per calendar month |

When both org and user budgets exist, the tighter limit applies.

## Cost Tracking

Each request is assigned a cost based on:

1. **Prompt tokens** used
2. **Completion tokens** returned
3. **Model** (different models have different rates)
4. **Provider** (OpenAI vs Anthropic pricing)

Costs are calculated using LiteLLM's `completion_cost()` function which includes current pricing for major providers.

### Real-Time Spending

Spending is tracked in Redis for fast lookups:

```
rl:usd:{org_id}:{YYYY-MM-DD}  → total USD spent today (org)
rl:usd:user:{user_id}:{YYYY-MM-DD}  → total USD spent today (user)
```

These keys expire daily at midnight UTC.

### Retrieving Current Spend

Use the analytics API to retrieve current spending:

```bash
curl -X GET https://api.openproxy.ai/api/v1/analytics/overview \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Response:**

```json
{
  "overview": {
    "period_days": 30,
    "total_requests": 12543,
    "successful_requests": 12491,
    "failed_requests": 52,
    "total_tokens": 5234000,
    "total_cost_usd": 1234.56,
    "avg_latency_ms": 245.3,
    "avg_ttft_ms": 850.2
  },
  "by_model": [
    {
      "model": "openai/gpt-4o",
      "provider": "openai",
      "requests": 5000,
      "tokens": 2500000,
      "cost_usd": 600.00
    },
    {
      "model": "anthropic/claude-3-sonnet",
      "provider": "anthropic",
      "requests": 7543,
      "tokens": 2734000,
      "cost_usd": 634.56
    }
  ],
  "by_user": [
    {
      "user_id": "550e8400-e29b-41d4-a716-446655440000",
      "email": "alice@example.com",
      "requests": 6000,
      "tokens": 2800000,
      "cost_usd": 700.00
    },
    {
      "user_id": "660e8400-e29b-41d4-a716-446655440001",
      "email": "bob@example.com",
      "requests": 6543,
      "tokens": 2434000,
      "cost_usd": 534.56
    }
  ],
  "daily_trend": [
    {
      "date": "2026-03-16",
      "requests": 450,
      "tokens": 185000,
      "cost_usd": 42.50,
      "avg_latency_ms": 240
    },
    {
      "date": "2026-03-17",
      "requests": 480,
      "tokens": 192000,
      "cost_usd": 45.80,
      "avg_latency_ms": 250
    }
  ],
  "generated_at": "2026-03-17T14:30:00Z"
}
```

## Budget Exceeded Response

When a budget is exceeded (daily or user), the request is rejected:

```
HTTP 402 Payment Required

{
  "error": "budget_exceeded",
  "detail": {
    "reason": "budget_daily_usd",
    "current_spend_usd": 50.00,
    "budget_usd": 50.00,
    "reset_at": "2026-03-18T00:00:00Z"
  }
}
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `reason` | string | Which budget was exceeded: `budget_daily_usd` or `user_budget_daily_usd` |
| `current_spend_usd` | decimal | Current spending for the period |
| `budget_usd` | decimal | Budget limit |
| `reset_at` | datetime | When the budget resets (next day at UTC midnight) |

The response includes standard rate limit headers:

```
X-RateLimit-Budget-Daily-USD: 50.00
X-RateLimit-Budget-Remaining-USD: 0.00
Retry-After: 14400  (seconds until reset)
```

## Budget Alert Webhook

When spend reaches 80% of the daily budget, a `budget.alert` webhook is fired (once per day).

**Configuration:**

1. Enable webhooks in organization settings
2. Subscribe to `budget.alert` event

See [Cost Management](#webhook-configuration) below for webhook setup.

**Webhook Payload:**

```json
{
  "event_type": "budget.alert",
  "org_id": "550e8400-e29b-41d4-a716-446655440000",
  "data": {
    "spend_usd": 40.00,
    "budget_usd": 50.00,
    "percent_used": 80.0
  }
}
```

The alert is fired only once per calendar day, even if spending continues to increase.

## Cost Anomaly Detection

Detect abnormally high spending compared to a 7-day baseline. When enabled, a `cost.anomaly` webhook is fired if:

**Today's spend > (7-day average × multiplier)**

Default multiplier: **3x** (configurable via `COST_ANOMALY_MULTIPLIER` environment variable)

### Configuration

```bash
export COST_ANOMALY_MULTIPLIER=3
export COST_ANOMALY_MIN_BASELINE_DAYS=3
```

| Setting | Default | Description |
|---------|---------|-------------|
| `COST_ANOMALY_MULTIPLIER` | 3 | Threshold multiplier above baseline |
| `COST_ANOMALY_MIN_BASELINE_DAYS` | 3 | Minimum days before anomaly detection kicks in |

### How It Works

1. **Baseline collection:** Last 7 days of spending stored in Redis (`cost:baseline:{org_id}`)
2. **Daily check:** After each request, compare today's spend to 7-day average
3. **Threshold:** If today > avg × multiplier, fire webhook
4. **Rate limit:** At most one webhook per hour (per organization and user)

### Webhook Payload

```json
{
  "event_type": "cost.anomaly",
  "org_id": "550e8400-e29b-41d4-a716-446655440000",
  "data": {
    "today_spend_usd": 150.00,
    "baseline_avg_usd": 45.00,
    "multiplier": 3.33,
    "org_id": "550e8400-e29b-41d4-a716-446655440000"
  }
}
```

**Fields:**

| Field | Description |
|-------|-------------|
| `today_spend_usd` | Total spending so far today |
| `baseline_avg_usd` | Average spending over last 7 days |
| `multiplier` | Today's spend / baseline (e.g., 3.33 means 3.33x higher) |

### Example Scenario

**7-day baseline:** [10, 12, 11, 13, 10, 12, 11] USD = 79 USD average = 11.29 USD/day

**Today:** Spending is now 40 USD

**Check:** 40 > 11.29 × 3 (33.87)?  Yes!

**Result:** Anomaly detected, webhook fired.

## Webhook Configuration

Enable webhooks to receive budget and anomaly alerts:

```bash
curl -X PATCH https://api.openproxy.ai/api/v1/organizations/current/webhooks \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://yourapp.example.com/webhooks/openproxy",
    "secret": "your-webhook-secret",
    "events": ["budget.alert", "cost.anomaly"],
    "enabled": true
  }'
```

**Request Fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `url` | string | Yes | HTTPS endpoint to receive webhooks |
| `secret` | string | No | Shared secret for HMAC signature (optional) |
| `events` | array | Yes | List of event types to subscribe to |
| `enabled` | boolean | Yes | Whether webhooks are active |

**Supported Events:**

- `budget.alert` — Spending reached 80% of daily budget
- `cost.anomaly` — Spending spike detected
- `policy.violation` — Policy rule triggered (see policy configuration)

### Webhook Signature

Webhooks include an `X-Signature` header with HMAC-SHA256 signature:

```
X-Signature: sha256=abcd1234...
```

To verify:

```python
import hmac
import hashlib

def verify_webhook(payload_bytes, signature, secret):
    expected = hmac.new(
        secret.encode(),
        payload_bytes,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(signature, expected)
```

## ClickHouse Analytics (Phase 3)

For scale (>1M requests/day), enable ClickHouse to store and query detailed analytics:

```bash
export CLICKHOUSE_URL=http://clickhouse:8123
export CLICKHOUSE_ENABLED=true
```

When enabled:

- Request logs are written to ClickHouse asynchronously (non-blocking)
- Analytics queries use ClickHouse for fast aggregations
- PostgreSQL continues to store only recent logs (archival window)
- Fallback: If ClickHouse is unavailable, logging continues (PostgreSQL only)

ClickHouse provides:

- Columnar storage (better compression)
- Sub-second query latency for large time ranges
- Advanced analytics: time-series, distributions, percentile calculations
- Integration with Grafana for real-time dashboards

## Rate Limit Headers

All successful responses include budget and rate limit headers:

```
X-RateLimit-Requests-Limit: 100
X-RateLimit-Requests-Remaining: 45
X-RateLimit-Tokens-Limit: 100000
X-RateLimit-Tokens-Remaining: 62000
X-RateLimit-Budget-Daily-USD: 50.00
X-RateLimit-Budget-Remaining-USD: 12.34
X-RateLimit-Reset: 1679577600
```

**Headers:**

| Header | Description |
|--------|-------------|
| `X-RateLimit-Requests-Limit` | RPM limit |
| `X-RateLimit-Requests-Remaining` | Requests left this minute |
| `X-RateLimit-Tokens-Limit` | TPM limit |
| `X-RateLimit-Tokens-Remaining` | Tokens left this minute |
| `X-RateLimit-Budget-Daily-USD` | Daily budget (USD) |
| `X-RateLimit-Budget-Remaining-USD` | Budget remaining today |
| `X-RateLimit-Reset` | Unix timestamp of next minute reset |

When a limit is exceeded, `Retry-After` is included:

```
Retry-After: 300
```

Wait at least 300 seconds before retrying.

## Cost Calculation Details

Costs are calculated by LiteLLM using official provider pricing:

**OpenAI (GPT-4o):**

```
$0.005 per 1K input tokens
$0.015 per 1K output tokens
```

**Anthropic (Claude 3 Sonnet):**

```
$0.003 per 1K input tokens
$0.015 per 1K output tokens
```

Prices are updated when LiteLLM releases new versions. Check the LiteLLM documentation for current rates.

## Invoicing

Organizations on paid plans can retrieve usage for invoicing:

```bash
curl -X GET "https://api.openproxy.ai/api/v1/analytics/overview?period_days=30" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

Export the `by_user` array to charge back users or departments.

## Best Practices

1. **Set organization budget** to cap total monthly spending
2. **Assign user budgets** for per-team cost control
3. **Monitor anomalies** — investigate sudden spikes
4. **Archive logs** — use ClickHouse for historical analysis (Phase 3)
5. **Use webhooks** — integrate alerts with Slack, PagerDuty, etc.
6. **Review daily** — check analytics dashboard each morning
7. **Tag requests** — use custom headers to correlate costs with projects

## Troubleshooting

### Budget Resets at Unexpected Time

Budget resets at **UTC midnight** (00:00 UTC). Check your timezone conversion.

### Cost Not Updating

Costs are updated **after the response** is streamed back to the user. Wait ~5 seconds then refresh analytics.

### Anomaly Alert Not Firing

1. Check that baseline has 3+ days of data (COST_ANOMALY_MIN_BASELINE_DAYS)
2. Confirm webhook URL is reachable (check logs)
3. Verify multiplier threshold (default 3x)

### ClickHouse Not Writing

1. Confirm CLICKHOUSE_URL is reachable
2. Check database logs for connection errors
3. Verify schema tables exist (created automatically on first write)
4. Falls back to PostgreSQL if unavailable (non-critical)
