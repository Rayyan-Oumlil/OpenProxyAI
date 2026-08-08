---
title: OpenAI SDK Compatibility
description: OpenProxyAI is OpenAI-API-compatible — point your existing SDK at it and nothing else changes.
---

# OpenAI SDK Compatibility

OpenProxyAI exposes an OpenAI-compatible API surface — `/v1/chat/completions`, `/v1/embeddings`, `/v1/models`. If your application already uses the official OpenAI SDK, switching to OpenProxyAI is a `base_url` change, not a rewrite.

```python
from openai import OpenAI

client = OpenAI(
    base_url="https://api.openproxy.ai/v1",
    api_key=os.environ["OPENPROXY_KEY"],
)

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "hi"}],
)
```

Same for the TypeScript/JavaScript `openai` package — pass `baseURL` in the client constructor.

## Adding OpenProxyAI-specific headers

Optional headers extend the request without breaking compatibility with the underlying OpenAI client:

```
x-op-team:   eng-platform
x-op-policy: pii_redact,topic_guard
```

See [Rate Limiting & Budgets](/core-concepts/rate-limiting-and-budgets) for `x-op-team`, and [Policies & Guardrails](/core-concepts/policies-and-guardrails) for `x-op-policy`.

## Calling non-OpenAI models

The same OpenAI-shaped request works for any provider behind OpenProxyAI — set `model` to the target model name (for example `claude-3-5-sonnet` or `gemini-1.5-pro`) and OpenProxyAI routes it to the right provider. See [Provider Routing](/core-concepts/provider-routing).

## Using the dedicated SDKs instead

For richer error types and typed gateway metadata (cost, latency, policy decisions) on every response, see the [Python SDK](/integrations/python-sdk) and [TypeScript SDK](/integrations/typescript-sdk).
