---
title: OpenAI SDKs and frameworks
description: Use the official OpenAI Python and Node SDKs and LangChain with OpenProxyAI by changing the base URL, and see which OpenAI routes the gateway serves.
---

# OpenAI SDKs and frameworks

OpenProxyAI exposes an OpenAI-compatible API, so an application that already uses the official OpenAI SDK, or LangChain's OpenAI integration, switches to the gateway by changing the base URL and the API key. No separate package is needed. Every request still goes through the full [request pipeline](/core-concepts/request-pipeline): policy, caching, budgets, routing and audit logging apply exactly as for any other client.

Two things differ from calling OpenAI directly, and they are the cause of most first-run problems: the model name must be `provider/model`, and a refused request returns gateway-specific status codes.

## Setup

| Setting | Value |
|---|---|
| Base URL | `https://api.openproxy.ai/v1` (or `https://<your-gateway>/v1` when self-hosted) |
| API key | A gateway API key, sent as `Authorization: Bearer <key>`. See [Authentication](/getting-started/authentication) |
| Model | `provider/model`, for example `openai/gpt-4o` |

### Model names

The gateway reads the provider from the part before the first slash. A bare name such as `gpt-4o` is refused with HTTP 400 `invalid_model` ("Model must be provider/model"). Use `GET /v1/models` to list the exact ids your organization can call; they are built from the provider keys you registered.

```bash
curl https://api.openproxy.ai/v1/models -H "Authorization: Bearer $OPENPROXY_KEY"
```

The same OpenAI-shaped request works for every provider behind the gateway: change `model` to, say, `anthropic/<model-name>` and the gateway routes it to that provider. See [Provider routing](/core-concepts/provider-routing).

## OpenAI Python SDK

```python
import os
from openai import OpenAI

client = OpenAI(
    base_url="https://api.openproxy.ai/v1",
    api_key=os.environ["OPENPROXY_KEY"],
)

response = client.chat.completions.create(
    model="openai/gpt-4o",
    messages=[{"role": "user", "content": "hi"}],
)
print(response.choices[0].message.content)
```

Streaming uses the SDK's normal `stream=True`; the gateway returns the standard server-sent-events chunks.

### Gateway request headers

Pass optional gateway headers with `default_headers` (for every call) or `extra_headers` (for one call):

```python
client = OpenAI(
    base_url="https://api.openproxy.ai/v1",
    api_key=os.environ["OPENPROXY_KEY"],
    default_headers={
        "x-openproxy-team-id": "00000000-0000-0000-0000-000000000000",  # your team's UUID
        "x-openproxy-labels": '{"app": "my-service"}',
    },
)
```

| Header | Use |
|---|---|
| `x-openproxy-team-id` | Attribute the request to a team's limits and budget. Needed only if the key is not tied to a team. A non-UUID value is refused with 400 |
| `x-openproxy-labels` | A JSON object (up to 10 string keys and values) recorded on the request log |
| `x-openproxy-session-id` | Group requests into a session |
| `x-openproxy-data-class` | Raise the request's data class (it can raise, never lower) |
| `x-openproxy-behavior` | Provider-neutral settings, see [Behavior settings](/core-concepts/behavior-settings) |

Caching, fallback and retries are controlled by `x-openproxy-cache`, `x-openproxy-fallback-model` and `x-openproxy-retries`; see [Chat completions](/api-reference/chat-completions) for the full list. Guardrails come from the organization's [policy](/core-concepts/policies-and-guardrails), never from a header.

### Reading the response headers

The raw response carries `x-openproxyai-request-id` (to find the request in the audit log), `x-openproxyai-latency-ms`, and `x-openproxyai-cache` (the cache result), plus `x-openproxyai-provider`, `x-openproxyai-model` and `x-openproxyai-cost-usd`. With the OpenAI SDK, read them through the raw-response API:

```python
raw = client.chat.completions.with_raw_response.create(
    model="openai/gpt-4o",
    messages=[{"role": "user", "content": "hi"}],
)
print(raw.headers.get("x-openproxyai-request-id"))
completion = raw.parse()
```

## OpenAI Node SDK

```typescript
import OpenAI from "openai";

const client = new OpenAI({
  baseURL: "https://api.openproxy.ai/v1",
  apiKey: process.env.OPENPROXY_KEY,
  defaultHeaders: {
    "x-openproxy-team-id": "00000000-0000-0000-0000-000000000000",
    "x-openproxy-labels": JSON.stringify({ app: "my-service" }),
  },
});

const response = await client.chat.completions.create({
  model: "openai/gpt-4o",
  messages: [{ role: "user", content: "hi" }],
});
console.log(response.choices[0].message.content);
```

## LangChain

There is no separate OpenProxyAI package for LangChain. Its existing OpenAI integration works against the gateway by overriding the base URL.

### Python

```python
import os
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    model="openai/gpt-4o",
    base_url="https://api.openproxy.ai/v1",
    api_key=os.environ["OPENPROXY_KEY"],
    default_headers={
        "x-openproxy-team-id": "00000000-0000-0000-0000-000000000000",  # your team's UUID
        "x-openproxy-labels": '{"app": "langchain-demo"}',
    },
)

print(llm.invoke("Summarize this in one sentence.").content)
```

### JavaScript and TypeScript

`ChatOpenAI` from `@langchain/openai` accepts the same override: set the base URL under `configuration.baseURL` and the headers under `configuration.defaultHeaders`.

```typescript
import { ChatOpenAI } from "@langchain/openai";

const llm = new ChatOpenAI({
  model: "openai/gpt-4o",
  apiKey: process.env.OPENPROXY_KEY,
  configuration: {
    baseURL: "https://api.openproxy.ai/v1",
    defaultHeaders: { "x-openproxy-team-id": "00000000-0000-0000-0000-000000000000" },
  },
});
```

### What you get, and what you do not

Policy enforcement, caching, budgets and audit logging all apply to LangChain traffic. What the standard `ChatOpenAI` wrapper does not surface is the typed `gateway` metadata (provider, cost, latency, policy decision) that the dedicated [Python SDK](/integrations/python-sdk) attaches to every response. If you need it, use the dedicated SDK, or call the gateway directly for those requests.

## Compatibility table

Routes below were checked against the gateway's route list.

| OpenAI route | Gateway | Notes |
|---|---|---|
| `POST /v1/chat/completions` | Supported | Streaming supported. Other OpenAI fields (tools, response format and so on) are passed to the provider. `messages` or a stored `prompt_id`, not both |
| `GET /v1/models` | Supported | Returns `provider/model` ids built from your active provider keys |
| `POST /v1/embeddings` | Supported | Same pipeline as chat |
| `POST /v1/responses` | Supported, narrowed | No streaming, provider-run tools refused, `store` forced to false. See [Other endpoints](/api-reference/other-endpoints) |
| `POST /v1/images/generations` | Supported | Never cached |
| `POST /v1/audio/speech` | Supported | Returns audio bytes |
| `POST /v1/audio/transcriptions` | Supported | Multipart, 25 MB limit, `Content-Length` required |
| `POST /v1/rerank` | Supported | Not an OpenAI route; works for providers that offer rerank |
| `/v1/files`, `/v1/batches` | Supported | Chat requests only, run by the gateway. See [Batches](/api-reference/batches) |
| `WS /v1/realtime` | Supported | OpenAI models only. See [Realtime](/api-reference/realtime) |
| Legacy completions, moderations, assistants, fine-tuning | Not available | The gateway has no route for them; calls return 404 |

## Handling gateway errors in the SDKs

The OpenAI SDKs know standard statuses; gateway-specific ones surface as generic API errors.

| Status | Meaning | In the OpenAI SDK |
|---|---|---|
| 446 | Blocked by an enforcing policy. The body has `error`, `reason_code`, `detail` and an `explanation` safe to show a user | Generic status error; read the status and JSON body |
| 429 | A rate or budget limit; the body's `limit_type` says which | `RateLimitError` |
| 402 | A streamed request whose estimate exceeds the remaining daily budget | Generic status error |
| 400 `invalid_model` | The model is not `provider/model` | `BadRequestError` |

```python
import openai

try:
    client.chat.completions.create(model="openai/gpt-4o", messages=messages)
except openai.RateLimitError as e:
    print("limit:", e.response.json().get("limit_type"))
except openai.APIStatusError as e:
    if e.status_code == 446:
        print(e.response.json()["explanation"])
    else:
        raise
```

This is subtle because the OpenAI SDKs retry some failures automatically, including 429, by default. A budget limit will not clear in a couple of seconds, so lower `max_retries` if you want to see those errors immediately. A 446 is never retried and is not retryable as-is: the content or the policy must change. See [Errors and status codes](/api-reference/errors-and-status-codes).

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| 400 `invalid_model` | A bare model name such as `gpt-4o` | Use `openai/gpt-4o`; list valid ids with `GET /v1/models` |
| 401 | Missing or invalid gateway key | Send the gateway key, not a provider key |
| 400 about the team header | `x-openproxy-team-id` is not a UUID | Send the team's UUID |
| 446 on a normal prompt | The organization's policy blocked it | Read `explanation`; switch to `log_only` to measure |
| 429 right away | Team or key limit reached | Check `limit_type` in the body; see [Rate limiting and budgets](/core-concepts/rate-limiting-and-budgets) |
| Cost or latency missing in LangChain | The wrapper hides gateway metadata | Use the dedicated SDK, or read the response headers |

## Next steps

- [Python SDK](/integrations/python-sdk) and [TypeScript SDK](/integrations/typescript-sdk) for typed gateway metadata and error classes
- [Chat completions](/api-reference/chat-completions) for every request header
- [Quickstart](/getting-started/quickstart) to send a first request
