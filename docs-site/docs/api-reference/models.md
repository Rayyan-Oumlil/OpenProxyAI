---
title: Models
description: GET /v1/models — list the models available through your organization's configured providers.
---

# Models

```
GET /v1/models
```

Returns an OpenAI-compatible model list, built from your organization's configured provider keys and their associated model patterns — not a static global list. A model only appears here if a provider key capable of serving it is configured for your org (see [Provider Routing](/core-concepts/provider-routing)).

## Response

```json
{
  "object": "list",
  "data": [
    { "id": "gpt-4o", "object": "model", "owned_by": "openai" },
    { "id": "claude-3-5-sonnet", "object": "model", "owned_by": "anthropic" }
  ]
}
```

Any tool that discovers models via the standard OpenAI `list models` call — including most OpenAI-compatible client libraries — works against this endpoint unmodified.
