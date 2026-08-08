---
title: API Reference Overview
description: Base URL, authentication, and how the API is organized.
---

# API Reference Overview

## Base URL

```
https://api.openproxy.ai
```

## Two API surfaces

**Proxy endpoints** — OpenAI-compatible, used to actually call a model:

```
POST /v1/chat/completions
POST /v1/embeddings
GET  /v1/models
```

**Management endpoints** — used to configure your organization, under `/api/v1/`:

```
/api/v1/auth/*
/api/v1/api-keys
/api/v1/provider-keys
/api/v1/organizations/current
/api/v1/teams
/api/v1/analytics/*
/api/v1/prompt-templates
/api/v1/experiments
```

## Authentication

Both surfaces use a bearer token, but different tokens: proxy endpoints take an API key (`Authorization: Bearer sk_live_...` or `opai_...` depending on how it was issued), management endpoints take a session token issued by `/api/v1/auth/login`. See [Authentication](/getting-started/authentication).

## Response headers on proxy requests

Every proxy response includes gateway metadata as response headers, regardless of which client you use to call it:

| Header | Meaning |
|---|---|
| `x-openproxyai-request-id` | Unique ID for this request, for correlating with the audit log |
| `x-openproxyai-provider` | Upstream provider actually used |
| `x-openproxyai-model` | Model actually used |
| `x-openproxyai-cost-usd` | Cost of this request in USD |
| `x-openproxyai-latency-ms` | Total latency including proxy overhead |
| `x-openproxyai-ttft-ms` | Time to first token (streaming requests) |
| `x-openproxyai-cache` | Which cache tier served this response, if any |
| `x-openproxyai-policy-action` | Policy action taken, if any (e.g. `redacted`) |
| `x-openproxyai-policy-reason` | Human-readable reason for the policy action |

## Sections

- [Errors & Status Codes](/api-reference/errors-and-status-codes)
- [Chat Completions](/api-reference/chat-completions)
- [Embeddings](/api-reference/embeddings)
- [Models](/api-reference/models)
- [API Keys](/api-reference/api-keys)
- [Provider Keys](/api-reference/provider-keys)
- [Organizations](/api-reference/organizations)
- [Teams](/api-reference/teams)
- [Analytics](/api-reference/analytics)
- [Webhooks API](/api-reference/webhooks-api)
