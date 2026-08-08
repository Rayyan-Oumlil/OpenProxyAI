---
title: API Keys
description: Create, list, and delete proxy API keys.
---

# API Keys

```
GET    /api/v1/api-keys
POST   /api/v1/api-keys
DELETE /api/v1/api-keys/{key_id}
```

## Create

```json
POST /api/v1/api-keys
{
  "name": "prod-eng-platform",
  "permissions": ["proxy:llm"],
  "team_id": "…",
  "expires_at": null
}
```

Response includes the key in full exactly once — see [Authentication](/getting-started/authentication).

```json
{
  "id": "…",
  "key": "sk_live_***",
  "key_prefix": "sk_live_ab12",
  "permissions": ["proxy:llm"],
  "is_active": true,
  "team_id": "…",
  "created_at": "…",
  "warning": "Store this key securely. It will not be shown again."
}
```

## List

`GET /api/v1/api-keys` returns every key for your organization with its prefix, permissions, and status — never the full key value again after creation.

## Delete

`DELETE /api/v1/api-keys/{key_id}` immediately revokes the key. Any in-flight requests using it are not interrupted, but new requests are rejected with `401`.
