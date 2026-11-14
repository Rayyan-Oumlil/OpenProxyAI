---
title: API Reference Overview
description: Base URL, authentication, conventions, headers and health endpoints, plus a map of every API group.
---

# API Reference Overview

The OpenProxyAI API has two surfaces: OpenAI-compatible **proxy endpoints** that your applications call to reach a model, and **management endpoints** under `/api/v1/` that configure your organization. This page covers what they share (base URL, authentication, errors, headers, pagination), the health endpoints for your load balancer, and where to find each group.

## Base URL

```
https://api.openproxy.ai
```

For a self-hosted deployment, use your own host; paths are identical. See [Deployment](/guides/deployment).

## Two API surfaces

| Surface | Paths | Used for | Credential |
|---|---|---|---|
| Proxy | `/v1/...` | Calling models from your applications | API key |
| Management | `/api/v1/...` | Configuring the organization, reading analytics, admin tasks | Session token |

Proxy endpoints:

```
POST /v1/chat/completions
POST /v1/embeddings
POST /v1/rerank
POST /v1/images/generations
POST /v1/audio/transcriptions
POST /v1/audio/speech
POST /v1/responses
GET  /v1/models
```

## Authentication

Both surfaces use `Authorization: Bearer <token>`, but the tokens are different and not interchangeable.

| Surface | Token | How you get it |
|---|---|---|
| Proxy | An API key starting with `opai_` | Created in the admin console or with `POST /api/v1/api-keys`; shown once. |
| Management | A short-lived session token | `POST /api/v1/auth/login`, renewed with `POST /api/v1/auth/refresh`. |

```bash
# Proxy call with an API key
curl https://api.openproxy.ai/v1/models \
  -H "Authorization: Bearer $OPENPROXY_API_KEY"

# Management call with a session token
curl https://api.openproxy.ai/api/v1/organizations/current \
  -H "Authorization: Bearer $OPENPROXY_SESSION_TOKEN"
```

A missing or invalid token returns 401. Some management endpoints need the `admin` role and return 403 for other users; each page says which. Everything you read or write is scoped to your own organization. See [Authentication](/getting-started/authentication).

## Request and response conventions

- **JSON in, JSON out.** Send `Content-Type: application/json`. The exceptions are audio transcription (multipart upload), speech (audio bytes back) and CSV or JSONL exports.
- **Proxy errors** are `{"error": "<code>", "detail": "<text>"}`. A policy block (HTTP 446) adds `reason_code` and a one-sentence `explanation`.
- **Management errors** use `{"detail": "<text>"}`. A validation failure is 422 with a `detail` list naming the bad fields.
- **Gateway status codes.** 446 is a policy or routing block. 429 is a rate or budget limit, with a `limit_type` in the body; 402 appears only for a streamed request whose estimate exceeds the remaining budget. Full list in [Errors and status codes](/api-reference/errors-and-status-codes).
- **OpenAI compatibility.** Request and response bodies on proxy endpoints follow the OpenAI shapes, so existing SDKs work by changing the base URL and key. See [OpenAI SDK and frameworks](/integrations/openai-sdk-and-frameworks).

## Headers

### Response headers

| Header | Sent on | Meaning |
|---|---|---|
| `X-OpenProxyAI-Request-Id` | Every response | Unique id for the request. Use it to find the entry in the audit log and to send [feedback](/api-reference/feedback). |
| `X-OpenProxyAI-Latency-Ms` | Every response | Total time spent in the gateway and upstream. |
| `X-OpenProxyAI-Provider`, `X-OpenProxyAI-Model` | Successful proxy calls | The provider and the model that served the request. |
| `X-OpenProxyAI-Cost-Usd` | Successful proxy calls | The cost charged for the call, to six decimals. |
| `X-OpenProxyAI-Ttft-Ms` | Streamed chat | Time to the first token. |
| `X-OpenProxyAI-Cache` | Chat | Which cache tier answered, or `miss`. See [Caching](/core-concepts/caching). |
| `X-OpenProxyAI-Data-Class` | Proxy calls that passed classification, and routing refusals | The data class the request was given. |
| `X-OpenProxyAI-Route-Model`, `X-OpenProxyAI-Route-Reason` | When routing is on | The model routing chose (or `none`) and why. |
| `X-OpenProxyAI-Policy-Action`, `X-OpenProxyAI-Policy-Reason` | Policy refusals (446) | The action taken (`block`) and the reason code. The routing refusal carries the action only. |
| `X-OpenProxyAI-Behavior`, `X-OpenProxyAI-Behavior-Clamped` | When behavior settings apply | The settings that took effect, and which were lowered by your organization's ceiling. See [Behavior settings](/core-concepts/behavior-settings). |
| `X-OpenProxyAI-Gateway-Error` | Proxy calls | `true` when the gateway itself produced the error or refusal, `false` on success, so you can tell it from a provider error. |
| `X-RateLimit-*` | Proxy calls that passed the rate limiter | Requests, tokens and daily budget limit and remaining, and the reset time. |

Header names are case-insensitive. Only the request id and latency headers appear on management endpoints too.

### Request headers (proxy)

| Header | Purpose |
|---|---|
| `x-openproxy-team-id` | Attributes the request to a team's limits and budget (not needed when the key is tied to a team). |
| `x-openproxy-data-class` | Raises the request's data class; it can never lower it. |
| `x-openproxy-labels` | A JSON object of up to 10 string key-value pairs, stored on the request log. |
| `x-openproxy-session-id` | Groups requests into a session (up to 64 characters). |
| `x-openproxy-behavior` | Provider-neutral model settings. |
| `x-openproxy-cache` | `skip`, `no-store` or `no-cache` to bypass the cache for this request. |
| `x-openproxy-fallback-model` | A backup model to try if the first fails. |
| `x-openproxy-retries` | The most fallback attempts for this request (0 to 5). |
| `X-OpenProxy-MCP-Tools` | On MCP calls, a comma-separated list of tool patterns that narrows the request's scope. See [MCP gateway](/guides/mcp-gateway). |

The full list with limits is on the [chat completions](/api-reference/chat-completions) page.

## Pagination and filtering

List endpoints are not all paged the same way, so check each page. The request log is the typical case: `page` (from 1) and `page_size` (default 50, maximum 200), answered with this envelope.

```json
{"items": [], "total": 0, "page": 1, "page_size": 50, "total_pages": 0}
```

Some lists take `limit` instead (datasets, for example), and analytics endpoints take `period_days` or a date range. Exports can be capped; when a result is cut short, the response carries `X-Result-Truncated: true`.

## API groups

| Group | Paths | Reference |
|---|---|---|
| Chat | `/v1/chat/completions` | [Chat completions](/api-reference/chat-completions) |
| Embeddings, rerank, images, audio, Responses, model list | `/v1/embeddings`, `/v1/rerank`, `/v1/images/generations`, `/v1/audio/*`, `/v1/responses`, `/v1/models` | [Other endpoints](/api-reference/other-endpoints) |
| Realtime | Realtime audio sessions | [Realtime](/api-reference/realtime) |
| Batches | `/v1` batch and file calls, `/api/v1/batch-jobs` | [Batches](/api-reference/batches) |
| Feedback | `/v1/feedback`, `/api/v1/scores` | [Feedback](/api-reference/feedback) |
| Datasets | `/api/v1/datasets` | [Datasets](/api-reference/datasets) |
| Evaluations | `/api/v1/evaluators`, `/api/v1/eval-runs` | [Eval runs](/api-reference/eval-runs) |
| Analytics | `/api/v1/analytics/*` | [Analytics](/api-reference/analytics) |
| Conversations | `/api/v1/conversations`, `/api/v1/spaces` | [Conversations](/api-reference/conversations) |
| Keys | `/api/v1/api-keys`, `/api/v1/provider-keys` | [Keys](/api-reference/keys) |
| Organization, teams, users | `/api/v1/organizations`, `/api/v1/teams`, `/api/v1/users` | [Organizations, teams and users](/api-reference/organizations-teams-users) |
| MCP gateway | `/api/v1/mcp-servers`, `/api/v1/mcp-grants`, `/api/v1/mcp-bundles`, `/api/v1/mcp-trust-rules` | [MCP admin](/api-reference/mcp-admin) |
| Auth | `/api/v1/auth/*` | [Authentication](/getting-started/authentication) |

Other management paths exist for experiments, prompt templates, policy plugins, the model registry, invitations, billing and the admin audit log. They are used by the [admin console](/admin-console/overview); the matching guides ([Adaptive experiments](/guides/adaptive-experiments), [Prompts](/guides/prompts), [Policy plugins](/guides/policy-plugins)) describe them.

## Health and readiness

Neither endpoint needs authentication, and neither is under `/api/v1`.

| Endpoint | Use it as | What it checks |
|---|---|---|
| `GET /health` | Liveness probe | The process is up. Always `200`; it checks no other service. |
| `GET /ready` | Readiness probe | Postgres and Redis both answer. |

```bash
curl -i https://api.openproxy.ai/ready
```

```json
{"status": "ready", "postgres": "ok", "redis": "ok"}
```

`/health` answers `{"status": "healthy", "app": "<name>", "version": "0.1.0"}`.

If either service is down, `/ready` answers **503** with `"status": "not ready"` and the failing one marked `"unavailable"`. A load balancer should stop sending traffic to that instance until it recovers. Do not restart the process on a readiness failure: the process is fine and a restart does not fix a database or cache outage. The Helm chart already points its probes at these paths; see [Deployment](/guides/deployment).

## Next steps

- [Quickstart](/getting-started/quickstart) for a first request
- [Errors and status codes](/api-reference/errors-and-status-codes)
- [Request pipeline](/core-concepts/request-pipeline) for what happens to each call
