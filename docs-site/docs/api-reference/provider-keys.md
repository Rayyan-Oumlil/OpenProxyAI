---
title: Provider Keys
description: Register and rotate the upstream provider keys OpenProxyAI routes to.
---

# Provider Keys

Provider keys are the credentials OpenProxyAI holds for each upstream provider (OpenAI, Anthropic, Azure, Mistral, etc.) — distinct from the [API keys](/api-reference/api-keys) your applications use to call OpenProxyAI itself.

```
GET    /api/v1/provider-keys
POST   /api/v1/provider-keys
PATCH  /api/v1/provider-keys/{key_id}
DELETE /api/v1/provider-keys/{key_id}
POST   /api/v1/provider-keys/{key_id}/rotate
```

## Create

```json
POST /api/v1/provider-keys
{
  "provider": "openai",
  "key": "sk-...",
  "weight": 0.7,
  "data_region": "us-east"
}
```

`weight` controls this key's share of weighted rotation relative to other keys for the same provider. `data_region` is used for [data residency](/guides/data-residency) filtering.

## Rotate

```
POST /api/v1/provider-keys/{key_id}/rotate
```

Issues a replacement and invalidates the old key without a gap in routing — traffic shifts to the new key.

See [Provider Routing](/core-concepts/provider-routing) for how weight and region interact with failover.
