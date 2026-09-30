---
title: Python SDK
description: The official openproxy-ai Python package — sync, async, and streaming.
---

# Python SDK

```bash
pip install "git+https://github.com/Rayyan-Oumlil/OpenProxyAI.git#subdirectory=sdk/python"
```

Requires Python 3.9+.

## Synchronous

```python
from openproxy import OpenProxy

client = OpenProxy(api_key="opai_your_key_here")

response = client.chat.completions.create(
    model="openai/gpt-4o",
    messages=[{"role": "user", "content": "Summarize this contract in plain English."}],
)
print(response.choices[0].message.content)
print(f"Cost: ${response.gateway.cost_usd:.6f} | Latency: {response.gateway.latency_ms}ms")
```

## Asynchronous

```python
import asyncio
from openproxy import AsyncOpenProxy

async def main():
    async with AsyncOpenProxy(api_key="opai_your_key_here") as client:
        response = await client.chat.completions.create(
            model="anthropic/claude-3-5-sonnet",
            messages=[{"role": "user", "content": "Hello!"}],
        )
        print(response.choices[0].message.content)

asyncio.run(main())
```

## Streaming

```python
from openproxy import OpenProxy

client = OpenProxy(api_key="opai_your_key_here")

with client.chat.completions.create(
    model="openai/gpt-4o",
    messages=[{"role": "user", "content": "Write a poem about APIs."}],
    stream=True,
) as stream:
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            print(delta, end="", flush=True)
```

Async streaming works the same way with `AsyncOpenProxy` and `async for`.

## Configuration

| Parameter | Default | Description |
|---|---|---|
| `api_key` | required | Your OpenProxyAI API key (`opai_...`) |
| `base_url` | `https://api.openproxyai.com` | Override for local dev (`http://localhost:8000`) |
| `timeout` | `60.0` | Request timeout in seconds |

```python
client = OpenProxy(api_key="opai_dev_key", base_url="http://localhost:8000")
```

## Error handling

```python
from openproxy import OpenProxy
from openproxy._exceptions import (
    AuthError,
    PolicyViolationError,
    RateLimitError,
    BudgetExceededError,
    ProviderError,
)

client = OpenProxy(api_key="opai_your_key_here")

try:
    response = client.chat.completions.create(
        model="openai/gpt-4o",
        messages=[{"role": "user", "content": "Hello"}],
    )
except AuthError:
    print("Invalid API key")
except PolicyViolationError as e:
    print(f"Blocked by policy: {e.reason_code} — rules: {e.triggered_rules}")
except BudgetExceededError as e:
    print(f"Daily budget exceeded. Retry after {e.retry_after}s")
except RateLimitError as e:
    print(f"Rate limited ({e.limit_type}). Retry after {e.retry_after}s")
except ProviderError as e:
    print(f"Upstream provider error ({e.provider})")
```

## Resources

**`client.chat.completions`**

| Method | Description |
|---|---|
| `.create(model, messages, stream=False, **kwargs)` | Create a chat completion |

**`client.embeddings`**

| Method | Description |
|---|---|
| `.create(model, input, **kwargs)` | Generate embeddings |

**`client.api_keys`**

| Method | Description |
|---|---|
| `.list()` | List all API keys |
| `.create(name, permissions=None, expires_at=None)` | Create a new API key |
| `.delete(key_id)` | Delete an API key |

**`client.analytics`**

| Method | Description |
|---|---|
| `.overview(period_days=30)` | Get usage overview |
| `.logs(page=1, page_size=50, **filters)` | Query request logs |

## Gateway metadata

Every `ChatCompletion` response includes a `.gateway` attribute with request-level telemetry:

```python
response.gateway.request_id    # str — unique request ID
response.gateway.cost_usd      # float — cost in USD
response.gateway.latency_ms    # int — total latency in milliseconds
response.gateway.provider      # str — upstream provider used
response.gateway.model         # str — model actually used
response.gateway.policy_action # str | None — e.g. "redacted", "flagged"
response.gateway.policy_reason # str | None — human-readable policy note
```
