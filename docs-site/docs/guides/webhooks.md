---
title: Webhooks
description: Send policy and budget events to an HTTPS endpoint you control, verify signatures, and inspect or retry deliveries.
---

# Webhooks

OpenProxyAI can post an event to an HTTPS endpoint you control when something needs attention, for example to send policy blocks or budget alerts into your own alerting. This page covers the events, the payload, signature verification, the management API, delivery and retry behavior, and troubleshooting. All webhook endpoints require an organization admin.

## How it works

An organization has one webhook configuration: a URL, an optional signing secret, a list of events, and an enabled flag. When a subscribed event happens, the gateway sends a JSON `POST` to the URL and records the outcome in a delivery log. Delivery runs after the triggering request, so a failing endpoint never blocks or slows the request that caused the event.

## Events

| Event | Fires when | `data` fields |
|---|---|---|
| `policy.violation` | A request is blocked by policy (HTTP 446) | `request_id`, `reason_code`, `triggered_rules`, `model`, `user_id`, `detail` |
| `budget.alert` | Daily spend reaches 80% of the daily budget; at most once per day | `spend_usd`, `budget_usd`, `percent_used` |

Only these two names are accepted in `events`. Any other value is rejected with a validation error.

### Payload

Every delivery has the same envelope:

```json
{
  "event": "budget.alert",
  "timestamp": "2026-11-13T14:02:11.482913+00:00",
  "org_id": "0b6f3c1e-8d54-4a52-9e0f-2f6a5f3d9c11",
  "data": {
    "spend_usd": 41.2,
    "budget_usd": 50.0,
    "percent_used": 82.4
  }
}
```

The request has `Content-Type: application/json`, and a signature header when a secret is set.

## Set up

```bash
curl -X PATCH https://your-gateway/api/v1/organizations/current/webhooks \
  -H "Authorization: Bearer $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://alerts.example.com/openproxy",
    "secret": "a-long-random-string",
    "events": ["policy.violation", "budget.alert"],
    "enabled": true
  }'
```

```json
{
  "url": "https://alerts.example.com/openproxy",
  "events": ["policy.violation", "budget.alert"],
  "enabled": true
}
```

| Field | Type | Default | Notes |
|---|---|---|---|
| `url` | string | required | Must be `https://` and resolve to a public address |
| `secret` | string | `""` | Used to sign deliveries; never returned by the API |
| `events` | list | both events | `policy.violation`, `budget.alert` |
| `enabled` | boolean | `true` | `false` stops all deliveries |

`PATCH` replaces the whole configuration, it does not merge. **Omitting `secret` clears the stored secret**, and deliveries become unsigned. Always send the secret again when you change another field. `GET /api/v1/organizations/current/webhooks` returns `url`, `events` and `enabled` (`enabled` is `false` until you configure it). Each change is recorded in the audit log.

Webhook settings cannot be changed through the general organization update endpoint; it rejects a `webhooks` key.

### URL rules

The URL is checked when you save it and again on every delivery. It must use HTTPS, and every address it resolves to must be public. Loopback, private, link-local and carrier-grade NAT ranges are refused, and the connection goes only to an address the gateway has checked itself, so a hostname that later resolves to a private address cannot be used to reach your network. For local testing, expose your receiver through a public HTTPS tunnel.

## Verify the signature

When a secret is configured, each delivery carries `X-OpenProxy-Signature: sha256=<hex>`: the HMAC-SHA256 of the raw request body, keyed with your secret. Recompute it over the exact bytes you received, before any JSON parsing, and compare in constant time.

```python
import hmac, hashlib

def is_authentic(secret: str, raw_body: bytes, header: str) -> bool:
    expected = "sha256=" + hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header)
```

```typescript
import { createHmac, timingSafeEqual } from "node:crypto";

export function isAuthentic(secret: string, rawBody: Buffer, header: string): boolean {
  const expected = "sha256=" + createHmac("sha256", secret).update(rawBody).digest("hex");
  const a = Buffer.from(expected);
  const b = Buffer.from(header);
  return a.length === b.length && timingSafeEqual(a, b);
}
```

Without a secret there is no signature header, so anyone who learns your URL could post to it. Set a secret in production.

## Delivery and retries

A delivery succeeds when your endpoint answers with a 2xx status within 10 seconds. Otherwise the gateway tries again inside the same delivery, up to 3 attempts in total, waiting 1 second and then 2 seconds between them. If all three fail, the delivery is stored as `failed`. Fix your endpoint, then retry it yourself with the API below.

Your endpoint should answer quickly with a 2xx and do slow work afterwards. A retry sends the original payload again, so receivers should tolerate duplicates; for `policy.violation`, `data.request_id` identifies the event.

### Delivery history

```bash
curl "https://your-gateway/api/v1/organizations/current/webhooks/deliveries?status=failed&page=1&page_size=20" \
  -H "Authorization: Bearer $ADMIN_KEY"
```

```json
{
  "items": [
    {
      "id": "7d1c4a0e-3b9f-4c1d-a2c8-5e7f0a9b6d21",
      "event_type": "policy.violation",
      "url": "https://alerts.example.com/openproxy",
      "status": "failed",
      "http_status": 503,
      "attempt_count": 3,
      "last_attempted_at": "2026-11-13T14:02:14.100000Z",
      "created_at": "2026-11-13T14:02:11.700000Z"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20,
  "total_pages": 1
}
```

| Query parameter | Default | Notes |
|---|---|---|
| `page` | 1 | 1 or more |
| `page_size` | 20 | 1 to 100 |
| `status` | none | Filter, for example `failed` or `delivered` |

Newest deliveries come first. `http_status` is `null` when no response was received, for example on a timeout or connection error.

### Retry a delivery

```bash
curl -X POST \
  https://your-gateway/api/v1/organizations/current/webhooks/deliveries/7d1c4a0e-3b9f-4c1d-a2c8-5e7f0a9b6d21/retry \
  -H "Authorization: Bearer $ADMIN_KEY"
```

The response is the updated delivery, with the stored `payload` added. A retry resends the stored payload to the stored URL, signed with the current secret, and adds 1 to `attempt_count`.

| Status | Meaning |
|---|---|
| 200 | Retried; check `status` in the body for the new outcome |
| 400 | The stored URL no longer passes the URL rules |
| 403 | Caller is not an admin |
| 404 | No such delivery in your organization |
| 409 | The delivery already succeeded |

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Save fails with a URL error | Not HTTPS, or resolves to a private or local address | Use a public HTTPS URL |
| Save fails with an event error | Unknown event name | Use `policy.violation` or `budget.alert` |
| No deliveries appear | `enabled` is `false`, the event is not in `events`, or the event has not happened | Check `GET .../webhooks`; remember `budget.alert` fires once per day |
| Signature never matches | Parsed or re-serialized body, or the secret was cleared by a `PATCH` without `secret` | Hash the raw bytes; resend the secret |
| Signature header missing | No secret configured | Set `secret` |
| Deliveries `failed` with `http_status` null | Timeout, TLS error or unreachable host | Check the endpoint is reachable from the public internet with a valid certificate |
| Retry returns 400 | The hostname now resolves to a private address | Update the URL with `PATCH` |

## Next steps

- [Policies and guardrails](/core-concepts/policies-and-guardrails) for what triggers `policy.violation`.
- [Rate limiting and budgets](/core-concepts/rate-limiting-and-budgets) for budgets behind `budget.alert`.
- [Audit logging](/security/audit-logging) for the record of configuration changes.
- [Telemetry and SIEM](/guides/telemetry-and-siem) for streaming every request, not just alerts.
