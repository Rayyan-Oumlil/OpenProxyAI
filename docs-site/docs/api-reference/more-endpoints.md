---
title: Rerank, images, audio and Responses
description: POST /v1/rerank, /v1/images/generations, /v1/audio/transcriptions, /v1/audio/speech and /v1/responses, all under the same policy, routing and audit as chat.
---

# Rerank, images, audio and Responses

Every endpoint here runs through the same sequence as [embeddings](/api-reference/embeddings): your org's policy, data classification, [routing](/guides/conversations) (when enforced), rate limits, key choice with fallback, metering and the audit log. Authenticate with an API key as for chat. A refusal is the usual HTTP 446; the response headers carry `X-OpenProxyAI-Data-Class` and the route decision.

What is scanned is **everything the provider will read**, not only the main field: for rerank the query and every document, for Responses the input, instructions, tool definitions and output format.

| Endpoint | Model needs | Notes |
|---|---|---|
| `POST /v1/rerank` | `provider/model` | Works with the providers LiteLLM supports for rerank (Cohere, Jina, Voyage and similar), not OpenAI-compatible custom endpoints. |
| `POST /v1/images/generations` | `provider/model` | Never cached. The image is returned but never written to the audit log. Each image counts as 1,000 tokens against the rate limit. |
| `POST /v1/audio/transcriptions` | `provider/model` | Multipart upload. See below. |
| `POST /v1/audio/speech` | `provider/model` | The reply is audio bytes with the matching content type. |
| `POST /v1/responses` | `provider/model` | See below. |

## Rerank

```json
{"model": "cohere/rerank-english-v3.0", "query": "which is best?", "documents": ["a", {"text": "b"}], "top_n": 3}
```

Up to 1,000 documents, 50,000 characters each and 1,000,000 in all; query up to 10,000. Unknown fields are rejected (422).

## Images

`prompt` up to 4,000 characters, `n` 1 to 4, `size` from a fixed list, `response_format` `url` or `b64_json`.

## Audio

**Transcription** takes `multipart/form-data` with `model`, `file` and optional `language`, `prompt`, `response_format`, `temperature`. Audio cannot be read by the gateway, so the request is classified as **uninspected** (confidential unless your class map says otherwise), and under enforced routing only a model cleared for that class may receive it. That is deliberate: if you want a speech-to-text model to take your recordings, register it as cleared for confidential data. The optional `prompt` text is scanned like any prompt, and the transcript, including every segment and word of a verbose transcript, goes through your response guardrails.

Limits: 25 MB, one file, extensions flac, m4a, mp3, mp4, mpeg, mpga, oga, ogg, wav, webm. A `Content-Length` header is required (411 without) and a file over the limit is refused (413) before the body is read. The check runs after authentication.

**Speech** takes JSON: `model`, `input` (up to 4,096 characters, scanned), `voice`, `response_format` (`mp3`, `opus`, `aac`, `flac`, `wav`, `pcm`), optional `speed` (0.25 to 4).

## Responses

A narrowed version of the Responses API. The narrowing is the point: this API keeps state at the provider and can run tools there.

- **`store` is always sent explicitly as `false`.** The provider's default is to keep the response.
- `store: true`, `previous_response_id`, `item_reference` items and file ids are refused (400 `provider_state_not_allowed`) unless an admin turns on **Allow requests to keep state at the provider** (`allow_provider_response_state`, Policy, Data and routing). Send the full input each time instead.
- Only client-side `function` tools are accepted. Provider-run tools (web search, file search, code interpreter, remote MCP) are refused (422).
- Images, files, audio, encrypted reasoning and any input part the gateway does not recognise make the request **uninspected**, with the routing consequence above. The whole input is walked, not only `content`.
- Unknown fields are rejected. `stream` is not supported yet (422).
- With response guardrails on, every string the model produced is checked and redacted: message text, refusals, function-call arguments and reasoning summaries.
- A request too large to scan completely is refused (446 `scan_limit_exceeded`), not scanned in part.

## Cost

Costs are priced as what the call is (embedding, rerank, image, transcription, speech, responses). If LiteLLM cannot price a model, the call still returns its answer and is charged `UNPRICED_CALL_COST_USD` (default 0.01) per unit (per image for images), recorded as an estimate in the audit metadata, so an unpriced model still counts against budgets.
