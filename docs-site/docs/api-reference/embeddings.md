---
title: Embeddings
description: POST /v1/embeddings — OpenAI-compatible embeddings endpoint.
---

# Embeddings

```
POST /v1/embeddings
```

OpenAI-compatible request and response shape.

## Request

```json
{
  "model": "text-embedding-3-small",
  "input": "The text to embed"
}
```

Accepts the same headers as [Chat Completions](/api-reference/chat-completions) — `x-op-team` and `x-op-policy` apply here too, and requests pass through the same [pipeline](/core-concepts/request-pipeline) (auth, rate limit, policy, cache, route, log).

## Response

Standard OpenAI-shaped embedding vector response, plus `x-openproxyai-*` gateway headers — see [API Reference Overview](/api-reference/overview).

## Caching

Embedding requests are cache-eligible at the L1/L2 exact-match tiers. They are not matched by the L3 semantic tier, since semantic matching itself depends on embeddings — see [Caching](/core-concepts/caching).
