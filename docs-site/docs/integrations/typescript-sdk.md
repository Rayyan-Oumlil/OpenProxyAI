---
title: TypeScript SDK
description: The official openproxy-ai TypeScript/JavaScript package — typed, sync-style async, and streaming.
---

# TypeScript SDK

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI.git
cd OpenProxyAI/sdk/typescript && npm install && npm run build
# then, from your project:
npm install /path/to/OpenProxyAI/sdk/typescript
```

Ships both ESM and CJS builds with full type definitions.

## Basic usage

```typescript
import { OpenProxy } from 'openproxy-ai';

const client = new OpenProxy({
  apiKey: 'opai_your_key_here',
});

const response = await client.chat.completions.create({
  model: 'openai/gpt-4o',
  messages: [{ role: 'user', content: 'hi' }],
});

console.log(response.choices[0].message.content);
console.log(`Cost: $${response.gateway.costUsd} | Latency: ${response.gateway.latencyMs}ms`);
```

## Streaming

```typescript
const stream = await client.chat.completions.create({
  model: 'openai/gpt-4o',
  messages: [{ role: 'user', content: 'Write a haiku about proxies.' }],
  stream: true,
});

for await (const chunk of stream) {
  const delta = chunk.choices[0].delta.content;
  if (delta) process.stdout.write(delta);
}
```

The overload on `.create()` returns a `ChatCompletion` when `stream` is omitted or `false`, and an `AsyncIterable<ChatCompletionChunk>` when `stream: true` — TypeScript narrows the return type for you based on the literal value passed.

## Configuration

```typescript
interface OpenProxyClientOptions {
  apiKey: string;
  baseUrl?: string; // defaults to https://api.openproxyai.com
}
```

```typescript
const client = new OpenProxy({
  apiKey: 'opai_dev_key',
  baseUrl: 'http://localhost:8000',
});
```

## Error handling

```typescript
import {
  OpenProxyError,
  AuthError,
  PolicyViolationError,
  RateLimitError,
  BudgetExceededError,
  ProviderError,
} from 'openproxy-ai';

try {
  await client.chat.completions.create({
    model: 'openai/gpt-4o',
    messages: [{ role: 'user', content: 'hi' }],
  });
} catch (err) {
  if (err instanceof AuthError) {
    // invalid API key
  } else if (err instanceof PolicyViolationError) {
    // blocked by policy
  } else if (err instanceof BudgetExceededError) {
    // daily budget exceeded
  } else if (err instanceof RateLimitError) {
    // rate limited
  } else if (err instanceof ProviderError) {
    // upstream provider error
  } else if (err instanceof OpenProxyError) {
    // any other SDK-raised error
  }
}
```

## Resources

- **`client.chat.completions.create(params)`**
- **`client.embeddings`**
- **`client.apiKeys`**

## Gateway metadata

Every response includes a `gateway` object built from the proxy's response headers:

```typescript
response.gateway.requestId    // string
response.gateway.costUsd      // number
response.gateway.latencyMs    // number
response.gateway.ttftMs       // number — time to first token
response.gateway.provider     // string — upstream provider used
response.gateway.model        // string — model actually used
response.gateway.policyAction // string | undefined
response.gateway.policyReason // string | undefined
response.gateway.cache        // string | undefined — cache tier that served this, if any
```

These are read from the `x-openproxyai-*` response headers — see [API Reference → Chat Completions](/api-reference/chat-completions) if you're calling the HTTP API directly instead of using the SDK.
