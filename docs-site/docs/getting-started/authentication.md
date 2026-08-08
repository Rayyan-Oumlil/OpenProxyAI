---
title: Authentication
description: API keys, permissions, rotation, and SSO for OpenProxyAI.
---

# Authentication

## API keys

Every request to the proxy is authenticated with a bearer API key:

```
Authorization: Bearer sk_live_***
```

Keys are created from the admin console or via `POST /api/v1/api-keys`, and are shown in full exactly once at creation time. OpenProxyAI stores only a prefix and a hash — if a key is lost, revoke it and issue a new one; it cannot be recovered.

## Creating a key

```bash
curl -X POST https://api.openproxy.ai/api/v1/api-keys \
  -H "Authorization: Bearer <your-session-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "prod-eng-platform",
    "permissions": ["proxy:llm"],
    "team_id": "<optional-team-uuid>"
  }'
```

The response includes the key exactly once:

```json
{
  "id": "…",
  "key": "sk_live_***",
  "key_prefix": "sk_live_ab12",
  "permissions": ["proxy:llm"],
  "warning": "Store this key securely. It will not be shown again."
}
```

## Permissions

Keys are scoped by permission string. The default and most common is `proxy:llm`, which allows calling `/v1/chat/completions`, `/v1/embeddings`, and `/v1/models`. Keys can optionally be tied to a `team_id`, which ties the key's usage to that team's budget automatically instead of requiring an `x-op-team` header on every request.

## Rotating a key

```
POST /api/v1/provider-keys/{key_id}/rotate
```

Rotation issues a new key and invalidates the old one. Rotate immediately if a key may have been exposed — for example, committed to a repository or logged in plaintext.

## Session auth (admin console)

The admin console itself uses short-lived access tokens plus a refresh token, issued by `POST /api/v1/auth/login` and renewed via `POST /api/v1/auth/refresh`. This is separate from the proxy API keys used by your applications — session tokens are for managing your org, API keys are for sending traffic through the proxy.

## SSO

Organizations on Growth and Enterprise plans can connect an identity provider via `/api/v1/auth/sso/initiate` and `/api/v1/sso/connections`. Once configured, org members sign in to the admin console through your IdP instead of a password. See [Configuring SSO](/guides/configuring-sso).
