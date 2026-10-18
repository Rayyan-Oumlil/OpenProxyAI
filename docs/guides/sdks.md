# SDKs — OpenProxyAI

Both Python and TypeScript SDKs provide a simple, OpenAI-compatible interface to the OpenProxyAI gateway. Both support streaming, async operations, and automatic retry logic.

---

## Installation

### Python

> The SDKs are not published to PyPI or npm yet — install them from source as shown.

```bash
pip install "git+https://github.com/Rayyan-Oumlil/OpenProxyAI.git#subdirectory=sdk/python"
```

Requires Python 3.8+.

### TypeScript / JavaScript

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI.git
cd OpenProxyAI/sdk/typescript && npm install && npm run build
# then, from your project:
npm install /path/to/OpenProxyAI/sdk/typescript
```

Supports both ESM and CommonJS.

---

## Python SDK

### Initialization

```python
from openproxy import OpenProxy

client = OpenProxy(
    api_key="opai_xxxxxxxxxxxxxx",
    base_url="https://your-org.openproxyai.com"
)
```

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `api_key` | string | yes | Your organization's API key, prefixed with `opai_` |
| `base_url` | string | no | Gateway URL; defaults to `https://api.openproxyai.com` |
| `timeout` | float | no | Request timeout in seconds; defaults to 60.0 |

### Non-Streaming Chat Completion

Request a response and receive it all at once:

```python
response = client.chat.completions.create(
    model="openai/gpt-4o-mini",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Explain quantum computing"}
    ],
    temperature=0.7,
    max_tokens=200
)

print(response.choices[0].message.content)
print(f"Cost: ${response.gateway.cost_usd:.6f}")
print(f"Provider: {response.gateway.provider}")
print(f"Request ID: {response.gateway.request_id}")
print(f"Latency: {response.gateway.latency_ms}ms")
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique completion ID |
| `object` | string | Always `"chat.completion"` |
| `created` | int | Unix timestamp |
| `model` | string | The model that processed the request |
| `choices` | array | List of completion choices |
| `choices[].message.role` | string | Always `"assistant"` |
| `choices[].message.content` | string | The generated response |
| `choices[].finish_reason` | string | `"stop"`, `"length"`, `"content_filter"`, etc. |
| `usage.prompt_tokens` | int | Tokens in the user message |
| `usage.completion_tokens` | int | Tokens in the response |
| `usage.total_tokens` | int | Sum of prompt + completion |

**Gateway Metadata** (`response.gateway`):

| Field | Type | Description |
|-------|------|-------------|
| `request_id` | string | Unique ID for audit trail and analytics |
| `cost_usd` | float | Exact cost of this request in USD |
| `latency_ms` | int | Total gateway latency in milliseconds |
| `provider` | string | Which LLM provider handled the request (e.g., `openai`, `anthropic`) |
| `model` | string | The actual model routed to (e.g., `gpt-4o-mini`) |
| `policy_action` | string | `"allow"`, `"block"`, or `"log_only"` |
| `policy_reason` | string | Reason for block if `policy_action` is `"block"` (e.g., `blocked_keyword`, `model_not_allowed`) |
| `ttft_ms` | int | Time to first token in milliseconds (streaming only) |
| `cache` | string | `"hit"` or `"miss"` (if caching is enabled) |

### Streaming Chat Completion

Receive responses token-by-token in real time:

```python
with client.chat.completions.stream(
    model="openai/gpt-4o-mini",
    messages=[{"role": "user", "content": "Write a haiku"}],
    stream=True
) as stream:
    for chunk in stream:
        # Each chunk is a ChatCompletionChunk
        if chunk.choices[0].delta.content:
            print(chunk.choices[0].delta.content, end="", flush=True)

    # Access gateway metadata after streaming completes
    print(f"\nRequest ID: {chunk.gateway.request_id}")
    print(f"Cost: ${chunk.gateway.cost_usd:.6f}")
```

The `stream()` context manager returns a stream that yields `ChatCompletionChunk` objects. Gateway metadata is available on each chunk and accumulates across the stream.

### Async Client

For async/await applications:

```python
from openproxy import AsyncOpenProxy

async def main():
    client = AsyncOpenProxy(
        api_key="opai_xxxxxxxxxxxxxx",
        base_url="https://your-org.openproxyai.com"
    )

    # Non-streaming
    response = await client.chat.completions.create(
        model="openai/gpt-4o-mini",
        messages=[{"role": "user", "content": "Hello"}]
    )
    print(response.choices[0].message.content)

    # Streaming
    async with client.chat.completions.stream(
        model="openai/gpt-4o-mini",
        messages=[{"role": "user", "content": "Hello"}],
        stream=True
    ) as stream:
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                print(chunk.choices[0].delta.content, end="", flush=True)

    await client.close()

import asyncio
asyncio.run(main())
```

### Error Handling

The Python SDK raises typed exceptions for different error conditions:

```python
from openproxy import (
    OpenProxy,
    AuthError,
    PolicyViolationError,
    RateLimitError,
    BudgetExceededError,
    ProviderError,
)

try:
    response = client.chat.completions.create(
        model="openai/gpt-4o-mini",
        messages=[{"role": "user", "content": "..."}]
    )
except AuthError as e:
    print(f"Invalid API key: {e}")
except PolicyViolationError as e:
    print(f"Request blocked by policy: {e.reason_code}")
    print(f"Triggered rules: {e.triggered_rules}")
except BudgetExceededError as e:
    print(f"Daily budget exhausted; retry after {e.retry_after}s")
except RateLimitError as e:
    print(f"Rate limit exceeded ({e.limit_type}); retry after {e.retry_after}s")
except ProviderError as e:
    print(f"Provider {e.provider} error: {e}")
```

**Exception Types:**

| Class | HTTP Status | Meaning |
|-------|-------------|---------|
| `AuthError` | 401 | Invalid or missing API key |
| `PolicyViolationError` | 403 | Request blocked by organization policy |
| `RateLimitError` | 429 | Rate limit exceeded (requests/min or tokens/min) |
| `BudgetExceededError` | 429 | Daily budget limit exhausted |
| `ProviderError` | 502/504 | Upstream LLM provider error |
| `OpenProxyError` | Any | Base exception for all SDK errors |

All exceptions include:
- `status_code` — HTTP status code
- `message` — Human-readable error message
- `response` — Full error response body from the API

---

## TypeScript SDK

### Initialization

```typescript
import { OpenProxy } from 'openproxy-ai';

const client = new OpenProxy({
  apiKey: 'opai_xxxxxxxxxxxxxx',
  baseUrl: 'https://your-org.openproxyai.com'
});
```

**Options:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `apiKey` | string | yes | Your organization's API key, prefixed with `opai_` |
| `baseUrl` | string | no | Gateway URL; defaults to `https://api.openproxyai.com` |

### Non-Streaming Chat Completion

```typescript
const response = await client.chat.completions.create({
  model: 'openai/gpt-4o-mini',
  messages: [
    { role: 'system', content: 'You are a helpful assistant.' },
    { role: 'user', content: 'Explain quantum computing' }
  ],
  temperature: 0.7,
  max_tokens: 200
});

console.log(response.choices[0].message.content);
console.log(`Cost: $${response.gateway?.costUsd}`);
console.log(`Provider: ${response.gateway?.provider}`);
console.log(`Request ID: ${response.gateway?.requestId}`);
console.log(`Latency: ${response.gateway?.latencyMs}ms`);
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique completion ID |
| `object` | string | Always `"chat.completion"` |
| `created` | number | Unix timestamp |
| `model` | string | The model that processed the request |
| `choices` | array | List of completion choices |
| `choices[].message.role` | string | Always `"assistant"` |
| `choices[].message.content` | string | The generated response |
| `choices[].finishReason` | string | `"stop"`, `"length"`, `"content_filter"`, etc. |
| `usage.promptTokens` | number | Tokens in the user message |
| `usage.completionTokens` | number | Tokens in the response |
| `usage.totalTokens` | number | Sum of prompt + completion |

**Gateway Metadata** (`response.gateway`):

| Field | Type | Description |
|-------|------|-------------|
| `requestId` | string | Unique ID for audit trail and analytics |
| `costUsd` | number | Exact cost of this request in USD |
| `latencyMs` | number | Total gateway latency in milliseconds |
| `provider` | string | Which LLM provider handled the request (e.g., `openai`, `anthropic`) |
| `model` | string | The actual model routed to (e.g., `gpt-4o-mini`) |
| `policyAction` | string | `"allow"`, `"block"`, or `"log_only"` |
| `policyReason` | string | Reason for block if `policyAction` is `"block"` (e.g., `blocked_keyword`, `model_not_allowed`) |
| `ttftMs` | number | Time to first token in milliseconds (streaming only) |
| `cache` | string | `"hit"` or `"miss"` (if caching is enabled) |

### Streaming Chat Completion

Receive responses token-by-token using async iteration:

```typescript
const stream = await client.chat.completions.create({
  model: 'openai/gpt-4o-mini',
  messages: [{ role: 'user', content: 'Write a haiku' }],
  stream: true
});

let requestId: string | undefined;
let costUsd: number | undefined;

for await (const chunk of stream as AsyncIterable<ChatCompletionChunk>) {
  if (chunk.choices[0].delta?.content) {
    process.stdout.write(chunk.choices[0].delta.content);
  }
  // Gateway metadata is available on each chunk
  if (chunk.gateway) {
    requestId = chunk.gateway.requestId;
    costUsd = chunk.gateway.costUsd;
  }
}

console.log(`\nRequest ID: ${requestId}`);
console.log(`Cost: $${costUsd}`);
```

### Error Handling

The TypeScript SDK throws typed errors:

```typescript
import {
  OpenProxy,
  AuthError,
  PolicyViolationError,
  RateLimitError,
  BudgetExceededError,
  ProviderError,
} from 'openproxy-ai';

try {
  const response = await client.chat.completions.create({
    model: 'openai/gpt-4o-mini',
    messages: [{ role: 'user', content: '...' }]
  });
} catch (error) {
  if (error instanceof AuthError) {
    console.log(`Invalid API key: ${error.message}`);
  } else if (error instanceof PolicyViolationError) {
    console.log(`Request blocked: ${error.message}`);
  } else if (error instanceof BudgetExceededError) {
    console.log(`Budget exhausted`);
  } else if (error instanceof RateLimitError) {
    console.log(`Rate limited: ${error.message}`);
  } else if (error instanceof ProviderError) {
    console.log(`Provider error: ${error.message}`);
  }
}
```

**Error Classes:**

| Class | HTTP Status | Meaning |
|-------|-------------|---------|
| `AuthError` | 401 | Invalid or missing API key |
| `PolicyViolationError` | 403 | Request blocked by organization policy |
| `RateLimitError` | 429 | Rate limit exceeded (requests/min or tokens/min) |
| `BudgetExceededError` | 429 | Daily budget limit exhausted |
| `ProviderError` | 502/504 | Upstream LLM provider error |
| `OpenProxyError` | Any | Base error for all SDK errors |

### Module Support

The TypeScript SDK is published as both ESM and CommonJS:

```javascript
// ESM
import { OpenProxy } from 'openproxy-ai';

// CommonJS
const { OpenProxy } = require('openproxy-ai');
```

---

## Model Names

All models are prefixed with their provider. Use the full name in the `model` parameter:

```
openai/gpt-4o
openai/gpt-4o-mini
openai/gpt-3.5-turbo

anthropic/claude-opus
anthropic/claude-sonnet
anthropic/claude-haiku

azure/gpt-4
azure/gpt-4-turbo

mistral/mistral-large
mistral/mistral-medium
mistral/mistral-small

cohere/command
cohere/command-light
```

---

## Configuration

### Python

The `OpenProxy` client respects environment variables for convenience:

```python
import os

# Will use these if not passed to the constructor
os.environ['OPENPROXY_API_KEY'] = 'opai_...'
os.environ['OPENPROXY_BASE_URL'] = 'https://your-org.openproxyai.com'

client = OpenProxy()  # Uses env vars
```

### TypeScript

Pass options directly to the constructor. Env var support is not built in:

```typescript
const client = new OpenProxy({
  apiKey: process.env.OPENPROXY_API_KEY || 'opai_...',
  baseUrl: process.env.OPENPROXY_BASE_URL || 'https://api.openproxyai.com'
});
```

---

## Timeout and Retries

Both SDKs implement automatic retries for transient failures (5xx errors, rate limits, network timeouts).

### Python Retries

- **Max retries:** 3
- **Backoff:** Exponential (0.5s, 1s, 2s, up to 8s max)
- **Retryable errors:** RateLimitError, ProviderError, network timeouts

```python
client = OpenProxy(
    api_key="opai_...",
    timeout=60.0  # Request timeout in seconds
)
```

### TypeScript Retries

Retry logic is built into the `APIClient` and applied automatically. Configure via the `OpenProxy` constructor options.

---

## Next Steps

- **API Reference** — See [api-reference.md](../reference/api-reference.md) for complete endpoint documentation
- **Quickstart** — See [quickstart.md](../getting-started/quickstart.md) for 5-minute setup
- **Authentication** — See [guides/authentication.md](./authentication.md) for API key management
