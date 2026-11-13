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
| `x-openproxy-team-id` | If the key isn't tied to a team | The team's UUID. Attributes the request to that team's limits and budget. A value that is not a UUID is refused with 400 |
| `x-openproxy-data-class` | No | Raises the request's data class (`public`, `internal`, `confidential`, `secret`). It can raise the class, never lower it |
| `x-openproxy-cache` | No | `skip`, `no-store` or `no-cache`. `skip` bypasses the cache for this request in both directions — see [Caching](/core-concepts/caching) |
| `x-openproxy-fallback-model` | No | A backup model to try if the first fails. Under enforced routing it is ignored unless it is authorized for the request |
| `x-openproxy-retries` | No | An integer from 0 to 5: the most fallback attempts for this request |
| `x-openproxy-labels` | No | A JSON object of up to 10 string keys and values (each up to 64 characters), recorded on the request log and filterable there |
| `x-openproxy-session-id` | No | Groups requests into a session (up to 64 characters) |
| `x-openproxy-behavior` | No | Provider-neutral settings such as `creativity=low; max_response_length=short` (or a `behavior` field in the body) — see [Behavior Settings](/core-concepts/behavior-settings). The response reports what applied in `X-OpenProxyAI-Behavior`, and `X-OpenProxyAI-Behavior-Clamped` when your organization's ceiling lowered a request |

## Response

Standard OpenAI-shaped completion body, plus the `x-openproxyai-*` response headers documented in the [API Reference Overview](/api-reference/overview) — cost, latency, provider, cache status, and any policy action taken.

## Streaming

Set `"stream": true` for a server-sent-events stream of `ChatCompletionChunk` objects, identical in shape to OpenAI's own streaming format.

## Errors

See [Errors & Status Codes](/api-reference/errors-and-status-codes) — `429` (a rate or budget limit; the body's `limit_type` says which), `402` (a streamed request that would exceed the daily budget) and `446` (policy or routing block) are specific to OpenProxyAI; everything else follows standard HTTP semantics.
