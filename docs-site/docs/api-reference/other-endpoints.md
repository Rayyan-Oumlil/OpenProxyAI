---
title: Embeddings, models and other endpoints
description: Reference for GET /v1/models and the non-chat proxy endpoints (embeddings, rerank, images, audio and Responses), which all run under the same policy, routing and audit as chat.
---

# Embeddings, models and other endpoints

Besides [chat completions](/api-reference/chat-completions), the proxy serves a model list and five other model calls: embeddings, rerank, image generation, audio (transcription and speech) and a narrowed Responses API. Use this page when your application needs any of them. Every call goes through the same [request pipeline](/core-concepts/request-pipeline) as chat, so you get the same controls and the same audit trail without extra setup.

## What they share

All endpoints on this page use an API key (`Authorization: Bearer opai_...`, see [Authentication](/getting-started/authentication)) and return the gateway headers described in the [overview](/api-reference/overview).

| Behavior | What happens |
|---|---|
| Model name | Every call except `GET /v1/models` needs `provider/model`, for example `openai/text-embedding-3-small`. A name without a provider is refused with 400 `invalid_model`. |
| Policy | The organization policy scans **everything the provider will read**, not only the main field: for rerank the query and every document, for Responses the input, instructions, tool definitions and output format. In `enforce` mode a violation returns HTTP 446. |
| Data class and routing | The request is classified (`public`, `internal`, `confidential` or `secret`) and, when [routing](/core-concepts/provider-routing) is enforced, only an authorized model and key can serve it. |
| Limits | Rate limits and budgets apply. A limit returns 429 with a `limit_type`. |
| Team | `x-openproxy-team-id` attributes the call to a team unless the key is already tied to one. Also accepted: `x-openproxy-data-class`, `x-openproxy-labels`, `x-openproxy-session-id`, `x-openproxy-fallback-model` and `x-openproxy-retries`, as described for [chat](/api-reference/chat-completions). |
| Fallback | If the chosen provider key fails, other authorized keys are tried. |
| Caching | None of these endpoints is cached. |
| Audit | Each call is written to the [audit log](/security/audit-logging). Image bytes are never written to it. |

An error from the gateway has the shape `{"error": "<code>", "detail": "<text>"}`. A 446 body adds `reason_code` and `explanation`; see [Errors and status codes](/api-reference/errors-and-status-codes).

## List models

```bash
curl https://api.openproxy.ai/v1/models \
  -H "Authorization: Bearer $OPENPROXY_API_KEY"
```

```json
{
  "object": "list",
  "data": [
    {"id": "anthropic/claude-3-5-sonnet-20241022", "object": "model", "owned_by": "anthropic"},
    {"id": "openai/gpt-4o", "object": "model", "owned_by": "openai"}
  ]
}
```

The list is built from your organization's **active provider keys** and each key's model patterns, not from a global catalog. A key with no patterns contributes every model known for its provider; a key with patterns contributes only the matching ones. Ids are `provider/model` and sorted, and `owned_by` is the provider part. A model appears only if a configured key can serve it, so an empty list usually means no active provider key (see [Provider routing](/core-concepts/provider-routing)). Tools that discover models with the standard OpenAI list call work unmodified.

## Embeddings

```
POST /v1/embeddings
```

| Field | Type | Notes |
|---|---|---|
| `model` | string | `provider/model`. |
| `input` | string or list of strings | The text to embed. |
| `encoding_format` | string | Default `float`. |

```bash
curl https://api.openproxy.ai/v1/embeddings \
  -H "Authorization: Bearer $OPENPROXY_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model": "openai/text-embedding-3-small", "input": ["first text", "second text"]}'
```

The response is the provider's OpenAI-shaped embedding body (a `data` list of vectors plus `usage`). Embeddings are not cached, including at the exact-match tiers described in [Caching](/core-concepts/caching).

## Rerank

```
POST /v1/rerank
```

Orders documents by relevance to a query. It works with the providers that support rerank (Cohere, Jina, Voyage and similar), not with OpenAI-compatible custom endpoints.

```json
{"model": "cohere/rerank-english-v3.0", "query": "which is best?", "documents": ["a", {"text": "b"}], "top_n": 3}
```

| Field | Notes |
|---|---|
| `query` | Up to 10,000 characters. |
| `documents` | 1 to 1,000 items, each a string or `{"text": "..."}`, up to 50,000 characters each and 1,000,000 in all. |
| `top_n` | Optional, 1 to 1,000. |
| `return_documents` | Default `true`. |

Unknown fields are rejected with 422.

## Image generation

```
POST /v1/images/generations
```

```json
{"model": "openai/dall-e-3", "prompt": "A lighthouse at dusk", "n": 1, "size": "1024x1024", "response_format": "url"}
```

| Field | Notes |
|---|---|
| `prompt` | Up to 4,000 characters. Scanned like any prompt. |
| `n` | 1 to 4, default 1. |
| `size` | `auto`, `256x256`, `512x512`, `1024x1024`, `1024x1536`, `1536x1024`, `1024x1792` or `1792x1024`. |
| `quality` | `standard`, `hd`, `low`, `medium`, `high` or `auto`. |
| `style` | `vivid` or `natural`. |
| `response_format` | `url` or `b64_json`. |
| `user` | Optional, up to 200 characters. |

Each image counts as 1,000 tokens against the rate limit, because an image is far heavier than its prompt. The image is returned to you but never stored in the audit log.

## Audio

### Transcription

```
POST /v1/audio/transcriptions
```

```bash
curl https://api.openproxy.ai/v1/audio/transcriptions \
  -H "Authorization: Bearer $OPENPROXY_API_KEY" \
  -F model=openai/whisper-1 \
  -F file=@meeting.mp3 \
  -F response_format=verbose_json
```

| Field | Notes |
|---|---|
| `model`, `file` | Required. One file only. |
| `language` | Optional, such as `en` or `fr`. |
| `prompt` | Optional hint, up to 1,000 characters. Scanned like any prompt. |
| `response_format` | `json` (default), `text`, `srt`, `verbose_json` or `vtt`. |
| `temperature` | Optional, 0 to 1. |

Limits: 25 MB, extensions `flac`, `m4a`, `mp3`, `mp4`, `mpeg`, `mpga`, `oga`, `ogg`, `wav`, `webm`. A `Content-Length` header is required (411 without one) and an oversized file is refused with 413 before the body is read. The check runs after authentication.

The gateway cannot read audio, so the request is classified as **uninspected**: confidential unless your class map says otherwise. Under enforced routing only a model cleared for that class may receive it. This is deliberate. To let a speech-to-text model take your recordings, register it as cleared for confidential data. The transcript, including every segment and word of a verbose transcript, goes through your response guardrails.

### Speech

```
POST /v1/audio/speech
```

```json
{"model": "openai/tts-1", "input": "Hello from the gateway.", "voice": "alloy", "response_format": "mp3", "speed": 1.0}
```

| Field | Notes |
|---|---|
| `input` | Up to 4,096 characters. Scanned. |
| `voice` | 1 to 40 letters, digits, `_` or `-`. |
| `response_format` | `mp3` (default), `opus`, `aac`, `flac`, `wav` or `pcm`. |
| `speed` | Optional, 0.25 to 4. |

The reply is audio bytes with the matching content type, not JSON.

## Responses

```
POST /v1/responses
```

A narrowed version of the OpenAI Responses API. The narrowing is the point: the full API keeps state at the provider and can run tools there, which would put data where your organization's rules do not reach.

```json
{
  "model": "openai/gpt-4o",
  "input": "Summarize this ticket in one sentence.",
  "instructions": "Answer in plain language.",
  "max_output_tokens": 200
}
```

Accepted fields: `model`, `input` (a string up to 500,000 characters, or 1 to 500 items), `instructions` (up to 50,000 characters), `max_output_tokens`, `temperature`, `top_p`, `tools`, `tool_choice`, `parallel_tool_calls`, `text` (the output format), `metadata`, `user` and `truncation`. Unknown fields are rejected.

What differs from the provider's API:

- **`store` is always sent as `false`**, because the provider's default is to keep the response.
- `store: true`, `previous_response_id`, `item_reference` items and file ids are refused with 400 `provider_state_not_allowed` unless an admin turns on **Allow requests to keep state at the provider** (`allow_provider_response_state`, under Policy, Data and routing). Send the full input each time instead.
- Only client-side `function` tools are accepted. Provider-run tools (web search, file search, code interpreter, remote MCP) are refused with 422.
- Images, files, audio, encrypted reasoning and any input part the gateway does not recognize make the request **uninspected**, with the routing consequence described under transcription. The whole input is checked, not only `content`.
- `stream` is not supported yet (422).
- With response guardrails on, every string the model produced is checked and redacted: message text, refusals, function-call arguments and reasoning summaries.
- A request too large to scan completely is refused with 446 `scan_limit_exceeded`, never scanned in part.

## Cost

Each call is priced as what it is (embedding, rerank, image, transcription, speech or Responses). If a model cannot be priced, the call still returns its answer and is charged `UNPRICED_CALL_COST_USD` (default 0.01) per unit, per image for images. The charge is recorded as an estimate in the audit metadata, so an unpriced model still counts against budgets.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| 400 `invalid_model` | The model has no `provider/` prefix. | Use `openai/text-embedding-3-small`, not `text-embedding-3-small`. |
| `GET /v1/models` returns an empty list | No active provider key, or its model patterns match nothing. | Add or activate a provider key and check its patterns. |
| 446 on a transcription or an image-bearing Responses call | The request is uninspected, so it is treated as confidential and no authorized model can take it. | Register the model as cleared for that data class. |
| 400 `provider_state_not_allowed` | `store`, `previous_response_id`, an item reference or a file id was sent. | Send the full input with `store` false, or have an admin allow provider state. |
| 411 or 413 on transcription | No `Content-Length`, or the file is over 25 MB. | Send a sized upload under the limit. |
| 422 on rerank or Responses | An unknown field, or a provider-run tool. | Remove the field; use `function` tools only. |
| 429 | A rate or budget limit; the body's `limit_type` says which. | See [Rate limiting and budgets](/core-concepts/rate-limiting-and-budgets). |

## Next steps

- [Chat completions](/api-reference/chat-completions) for the main model call
- [Request pipeline](/core-concepts/request-pipeline) for the order of checks
- [Policies and guardrails](/core-concepts/policies-and-guardrails) and [Provider routing](/core-concepts/provider-routing)
- [Errors and status codes](/api-reference/errors-and-status-codes)
