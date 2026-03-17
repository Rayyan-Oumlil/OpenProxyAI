# Webhook Events — OpenProxyAI

Configure outbound webhooks to receive real-time notifications for compliance and cost events.

---

## Overview

OpenProxyAI can deliver signed webhook events to your endpoint when specific events occur (e.g., policy violations, budget alerts). Webhooks are fire-and-forget with 3-attempt exponential backoff retry.

### Setup

1. Go to the admin console: Settings → Webhooks
2. Enter your endpoint URL (must be HTTPS)
3. Copy your webhook signing secret (store it securely)
4. Select which events to subscribe to

All events are delivered as HTTPS POST requests with a JSON body and HMAC-SHA256 signature in the `X-OpenProxyAI-Signature` header.

---

## Signature Verification

Every webhook request includes an `X-OpenProxyAI-Signature` header. Verify it to confirm the request came from OpenProxyAI.

The signature is computed as `HMAC-SHA256(secret, body)` where `body` is the raw request body as bytes.

### Python

```python
import hmac
import hashlib
import json
from flask import request

def verify_webhook(secret: str):
    signature = request.headers.get('X-OpenProxyAI-Signature')
    body = request.get_data()

    expected_sig = hmac.new(
        secret.encode(),
        body,
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(signature, expected_sig):
        return False

    return True

@app.route('/webhooks/openproxy', methods=['POST'])
def webhook():
    if not verify_webhook(SECRET):
        return {'error': 'invalid signature'}, 401

    event = request.json
    print(f"Received: {event['event']}")
    return {}, 200
```

### Node.js

```javascript
import crypto from 'crypto';
import express from 'express';

const app = express();
app.use(express.raw({ type: 'application/json' }));

function verifyWebhook(secret, signature, body) {
  const expectedSig = crypto
    .createHmac('sha256', secret)
    .update(body)
    .digest('hex');

  return crypto.timingSafeEqual(signature, expectedSig);
}

app.post('/webhooks/openproxy', (req, res) => {
  const signature = req.headers['x-openproxy-signature'];

  if (!signature || !verifyWebhook(SECRET, signature, req.body)) {
    return res.status(401).json({ error: 'invalid signature' });
  }

  const event = JSON.parse(req.body);
  console.log(`Received: ${event.event}`);
  res.json({});
});

app.listen(3000);
```

---

## Event Types

### cost.alert

Fired when your organization's daily spend reaches a configurable threshold (default: 80% of daily budget).

**Payload**

```json
{
  "event": "cost.alert",
  "timestamp": "2026-03-16T12:45:30Z",
  "org_id": "org_abc123xyz",
  "data": {
    "spend_usd": 80.00,
    "budget_usd": 100.00,
    "threshold_pct": 80,
    "remaining_usd": 20.00,
    "period": "today"
  }
}
```

**When Fired**

- Once per day when daily spend >= 80% of daily budget
- Also fired when daily spend >= 90%, >= 100%, etc. (every 10% increment)

---

### cost.anomaly

Fired when today's spend exceeds 3x the 7-day rolling average. Useful for detecting unusual spikes.

**Payload**

```json
{
  "event": "cost.anomaly",
  "timestamp": "2026-03-16T14:20:15Z",
  "org_id": "org_abc123xyz",
  "data": {
    "today_spend_usd": 150.50,
    "baseline_avg_usd": 45.20,
    "multiplier": 3.33,
    "threshold_multiplier": 3.0
  }
}
```

**When Fired**

- Once when daily spend crosses 3x the 7-day average
- Not fired again until the next day

---

### policy.violation

Fired when a request is blocked by policy (enforce mode only).

**Payload**

```json
{
  "event": "policy.violation",
  "timestamp": "2026-03-16T13:50:45Z",
  "org_id": "org_abc123xyz",
  "data": {
    "request_id": "req_xyz789abc",
    "user_id": "user_123abc",
    "model": "openai/gpt-4o-mini",
    "reason_code": "blocked_keyword",
    "detail": "Request matched blocked keyword: password",
    "triggered_rules": ["blocked_keyword"],
    "http_status": 403
  }
}
```

**Reason Codes**

| Code | Meaning |
|------|---------|
| `blocked_keyword` | Request contains a blocked keyword |
| `model_not_allowed` | Model not in allowlist |
| `pii_detected` | PII detected (email, SSN, credit card) |
| `policy_eval_error` | Error evaluating policy (logged but allowed) |

---

## Retry Policy

Failed deliveries are retried with exponential backoff:

1. **Attempt 1** — Immediate
2. **Attempt 2** — After 5 seconds
3. **Attempt 3** — After 30 seconds

A delivery is considered successful (2xx HTTP status code). Any other status (4xx, 5xx, timeout) is treated as a failure and triggers a retry.

All delivery attempts are logged in the admin console under Settings → Webhook Deliveries.

---

## Handling Webhooks Idempotently

Webhook events can be delivered multiple times (e.g., if your endpoint returns an error). Use the `request_id` (for policy violations) or `timestamp` + `event` type to deduplicate.

### Example: Deduplication in PostgreSQL

```sql
-- Table to track processed webhooks
CREATE TABLE webhook_events_processed (
  event_id TEXT PRIMARY KEY,
  event_type TEXT,
  request_id TEXT,
  processed_at TIMESTAMP DEFAULT NOW()
);

-- Before processing
INSERT INTO webhook_events_processed (event_id, event_type, request_id)
VALUES (...) ON CONFLICT (event_id) DO NOTHING;

-- Only process if it's a new row
IF (affected rows) > 0 THEN
  -- Process the event
END IF;
```

---

## Testing Webhooks

Use the admin console's webhook test feature to send a sample event to your endpoint.

Alternatively, use curl:

```bash
curl -X POST https://your-webhook-endpoint.com/webhooks/openproxy \
  -H "Content-Type: application/json" \
  -H "X-OpenProxyAI-Signature: <computed-signature>" \
  -d '{
    "event": "cost.alert",
    "timestamp": "2026-03-16T12:45:30Z",
    "org_id": "org_abc123xyz",
    "data": {
      "spend_usd": 80.00,
      "budget_usd": 100.00,
      "threshold_pct": 80,
      "remaining_usd": 20.00,
      "period": "today"
    }
  }'
```

---

## Webhook Payload Size

Individual webhook payloads are limited to 10 KB. Very large events are truncated with a note in the `detail` field.

---

## Troubleshooting

### Webhook Not Delivered

1. Check the webhook URL in Settings → Webhooks — must be HTTPS
2. Verify your endpoint is responding with 2xx status code
3. Check the webhook delivery log (Settings → Webhook Deliveries) for error details
4. Ensure your firewall allows HTTPS connections from OpenProxyAI's IP range

### Signature Verification Failed

1. Confirm you're using the correct secret from Settings → Webhooks
2. Ensure you're verifying against the raw request body (not parsed JSON)
3. Use `hmac.compare_digest()` (Python) or `crypto.timingSafeEqual()` (Node.js) for timing-safe comparison

### Duplicate Events

Webhooks may be delivered multiple times. Implement idempotent processing using `request_id` or `timestamp` to deduplicate.

---

## Webhook Delivery Log

All webhook deliveries are logged and viewable in the admin console:

- **Delivered** — 2xx response received
- **Failed** — 4xx/5xx response or timeout after 3 retries
- **Pending** — Currently being retried

---

## Best Practices

1. **Verify signatures** — Always verify the `X-OpenProxyAI-Signature` header
2. **Respond quickly** — Return 2xx within 5 seconds; long operations should queue a background job
3. **Handle duplicates** — Assume webhooks may arrive multiple times and implement idempotent processing
4. **Monitor delivery** — Check the webhook delivery log in the admin console
5. **Set alerts** — Alert on `cost.anomaly` events to catch unusual spend spikes
6. **Log everything** — Log all webhook events for audit purposes
