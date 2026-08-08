---
title: Organizations
description: Org configuration, policy defaults, and webhook settings.
---

# Organizations

```
GET /api/v1/organizations/current
```

Returns your organization's configuration — plan, data residency settings, and general metadata.

## Policy configuration

```
GET  /api/v1/organizations/current/policy
GET  /api/v1/organizations/current/policy/templates
POST /api/v1/organizations/current/policy/apply-template
```

See [Policies & Guardrails](/core-concepts/policies-and-guardrails) and [Compliance Templates](/guides/compliance-templates).

## Webhooks

```
GET  /api/v1/organizations/current/webhooks
POST /api/v1/organizations/current/webhooks
GET  /api/v1/organizations/current/webhooks/deliveries
POST /api/v1/organizations/current/webhooks/deliveries/{delivery_id}/retry
```

See [Webhooks](/guides/webhooks).
