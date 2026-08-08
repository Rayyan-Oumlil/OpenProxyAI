---
title: Quickstart
description: Deploy OpenProxyAI, register an organization, and send your first proxied request in a few minutes.
---

# Quickstart

Get from zero to your first proxied request in a few minutes.

## 1. Deploy OpenProxyAI

```bash
curl -sSL openproxy.ai/install.sh | sh
cd openproxy && docker compose up -d
```

This starts the proxy, Postgres (with pgvector for semantic caching), and Redis. See [Deploying with Docker Compose](/guides/deploying-with-docker-compose) for a full walkthrough, or [Deploying with Helm](/guides/deploying-with-helm) for a production Kubernetes setup.

## 2. Register an organization

```bash
curl -X POST https://api.openproxy.ai/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "you@company.com",
    "password": "a-strong-password",
    "name": "Your Name",
    "org_name": "Your Org"
  }'
```

The response includes an `access_token` — use it to sign in to the admin console and issue your first API key.

## 3. Create an API key

From the admin console (or `POST /api/v1/api-keys`), create a key scoped to `proxy:llm`. Keys are shown once at creation — store them in a secret manager, not in source control. See [Authentication](/getting-started/authentication) for the full key lifecycle.

## 4. Send your first request

OpenProxyAI is OpenAI-API-compatible. Point any existing OpenAI SDK at it:

```python
from openai import OpenAI

client = OpenAI(
    base_url="https://api.openproxy.ai/v1",
    api_key=os.environ["OPENPROXY_KEY"],
)

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "hello"}],
    extra_headers={
        "x-op-team": "eng-platform",
        "x-op-policy": "pii_redact,topic_guard",
    },
)
```

The `x-op-team` header attributes cost to a team's budget. `x-op-policy` selects which guardrail policies apply to this request — see [Policies & Guardrails](/core-concepts/policies-and-guardrails).

## 5. Verify it worked

Check the response headers or the admin console's request log — you should see the request logged with its cost, latency breakdown, and cache status (`hit` or `miss`).

## Next steps

- [Authentication](/getting-started/authentication) — key permissions and rotation
- [Request Pipeline](/core-concepts/request-pipeline) — what happens to every request
- [API Reference](/api-reference/overview) — full endpoint list
