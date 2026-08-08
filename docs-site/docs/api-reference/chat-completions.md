---
title: Chat Completions
description: POST /v1/chat/completions — OpenAI-compatible, with OpenProxyAI-specific headers.
---

# Chat Completions

```
POST /v1/chat/completions
```

OpenAI-compatible request and response shape. Any field the OpenAI API accepts is passed through.

## Request

```json
{
  "model": "gpt-4o",
  "messages": [
    { "role": "user", "content": "Summarize for me@acme.com" }
  ],
  "stream": true
}
```

## Request headers

| Header | Required | Description |
|---|---|---|
| `Authorization` | Yes | `Bearer <api-key>` |
| `x-op-team` | If key isn't team-scoped | Attributes cost to a team's budget |
| `x-op-policy` | No | Comma-separated policy names to apply — see [Policies & Guardrails](/core-concepts/policies-and-guardrails) |

## Response

Standard OpenAI-shaped completion body, plus the `x-openproxyai-*` response headers documented in the [API Reference Overview](/api-reference/overview) — cost, latency, provider, cache status, and any policy action taken.

## Streaming

Set `"stream": true` for a server-sent-events stream of `ChatCompletionChunk` objects, identical in shape to OpenAI's own streaming format.

## Errors

See [Errors & Status Codes](/api-reference/errors-and-status-codes) — `402` (budget), `429` (rate limit), `446` (policy block) are specific to OpenProxyAI; everything else follows standard HTTP semantics.
