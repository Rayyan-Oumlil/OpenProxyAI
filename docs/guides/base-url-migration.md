# Drop-in Base URL Migration

Route existing OpenAI or Anthropic SDK traffic through OpenProxyAI with a single change: set `base_url` (or `baseURL`) to your gateway URL. No code changes to your request shape — the gateway is fully OpenAI-compatible.

---

## Prerequisites

- An OpenProxyAI API key (create one in the admin console)
- Your gateway URL (e.g. `https://your-org.openproxyai.com` or `https://openproxyai-backend-xxxx.a.run.app`)

---

## OpenAI Python SDK

**Before (direct to OpenAI):**

```python
from openai import OpenAI

client = OpenAI(api_key="sk-...")  # OpenAI API key
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Hello"}],
)
```

**After (via OpenProxyAI):**

```python
from openai import OpenAI

client = OpenAI(
    api_key="opai_xxxxxxxxxxxxxx",  # OpenProxyAI API key
    base_url="https://your-org.openproxyai.com/v1",
)
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Hello"}],
)
```

**Note:** Use your OpenProxyAI API key. The `base_url` must end with `/v1` so the SDK appends `/chat/completions` correctly.

---

## OpenAI Node / TypeScript SDK

**Before (direct to OpenAI):**

```typescript
import OpenAI from "openai";

const client = new OpenAI({
  apiKey: "sk-...",
});

const response = await client.chat.completions.create({
  model: "gpt-4o-mini",
  messages: [{ role: "user", content: "Hello" }],
});
```

**After (via OpenProxyAI):**

```typescript
import OpenAI from "openai";

const client = new OpenAI({
  apiKey: "opai_xxxxxxxxxxxxxx",
  baseURL: "https://your-org.openproxyai.com/v1",
});

const response = await client.chat.completions.create({
  model: "gpt-4o-mini",
  messages: [{ role: "user", content: "Hello" }],
});
```

---

## Anthropic Python SDK

**Before (direct to Anthropic):**

```python
from anthropic import Anthropic

client = Anthropic(api_key="sk-ant-...")
message = client.messages.create(
    model="claude-3-haiku-20240307",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Hello"}],
)
```

**After (via OpenProxyAI):**

OpenProxyAI’s gateway exposes OpenAI-compatible endpoints. For Anthropic models, use the gateway’s model format and the OpenAI SDK:

```python
from openai import OpenAI

client = OpenAI(
    api_key="opai_xxxxxxxxxxxxxx",
    base_url="https://your-org.openproxyai.com/v1",
)
# Use anthropic/... prefix for model routing
response = client.chat.completions.create(
    model="anthropic/claude-3-haiku-20240307",
    messages=[{"role": "user", "content": "Hello"}],
    max_tokens=1024,
)
```

If you prefer to keep using the Anthropic SDK, configure its HTTP client base URL (implementation depends on SDK version). Most users achieve zero-code migration by switching to the OpenAI SDK and the `anthropic/` model prefix.

---

## Anthropic Node / TypeScript SDK

**Before (direct to Anthropic):**

```typescript
import Anthropic from "@anthropic-ai/sdk";

const client = new Anthropic({
  apiKey: "sk-ant-...",
});

const message = await client.messages.create({
  model: "claude-3-haiku-20240307",
  max_tokens: 1024,
  messages: [{ role: "user", content: "Hello" }],
});
```

**After (via OpenProxyAI — use OpenAI SDK):**

Same as Anthropic Python: use the OpenAI SDK with `baseURL` and the `anthropic/` model prefix for a drop-in migration.

---

## Summary

| SDK            | Change                                      | Auth          |
|----------------|---------------------------------------------|---------------|
| OpenAI Python  | `base_url="https://gateway/v1"`             | OpenProxyAI key |
| OpenAI Node    | `baseURL: "https://gateway/v1"`             | OpenProxyAI key |
| Anthropic      | Use OpenAI SDK + `anthropic/` model prefix  | OpenProxyAI key |

Request shape and parameters remain the same. Only the base URL and API key change.
