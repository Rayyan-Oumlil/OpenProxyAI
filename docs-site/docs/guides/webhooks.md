---
title: Webhooks
description: Subscribe to OpenProxyAI events and receive delivery retries automatically.
---

# Webhooks

OpenProxyAI can deliver events to an HTTPS endpoint you control — for example, to pipe policy blocks or budget alerts into your own alerting system.

## Managing webhooks

```
GET  /api/v1/organizations/current/webhooks
POST /api/v1/organizations/current/webhooks
```

## Delivery and retries

Webhook delivery is treated as a sidecar: a failed delivery never blocks or delays the request that triggered it. Failed deliveries are retried automatically with exponential backoff, up to 3 attempts, on a 5-minute background schedule. You can view delivery history and manually retry a specific failed delivery:

```
GET  /api/v1/organizations/current/webhooks/deliveries
POST /api/v1/organizations/current/webhooks/deliveries/{delivery_id}/retry
```

## Verifying webhook authenticity

Every delivery with a configured secret carries an `X-OpenProxy-Signature: sha256=<hex>` header: the HMAC-SHA256 of the raw request body, keyed with your webhook secret. Recompute it over the exact bytes you received and compare in constant time.

```python
import hmac, hashlib

expected = "sha256=" + hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
ok = hmac.compare_digest(expected, request.headers["X-OpenProxy-Signature"])
```
