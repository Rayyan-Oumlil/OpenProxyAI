---
title: Webhooks API
description: Full endpoint reference for configuring and monitoring webhook delivery.
---

# Webhooks API

See [Webhooks](/guides/webhooks) for a conceptual overview. This page is the endpoint reference.

```
GET  /api/v1/organizations/current/webhooks
POST /api/v1/organizations/current/webhooks
```

## Delivery history

```
GET /api/v1/organizations/current/webhooks/deliveries
```

Returns delivery attempts, their status, and response codes from your endpoint.

## Retrying a failed delivery

```
POST /api/v1/organizations/current/webhooks/deliveries/{delivery_id}/retry
```

Failed deliveries also retry automatically on a background schedule (exponential backoff, up to 3 attempts) — manual retry is for triggering an attempt immediately rather than waiting for the next scheduled one.
