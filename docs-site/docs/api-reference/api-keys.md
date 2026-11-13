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
  "name": "prod-eng-platform",
  "key": "opai_prod_1a2b3c4d_<32 hex characters><4 checksum characters>",
  "key_prefix": "opai_prod_1a2b3c4d",
  "permissions": ["proxy:llm"],
  "is_active": true,
  "expires_at": null,
  "team_id": "…",
  "created_at": "…",
  "warning": "Store this key securely. It will not be shown again."
}
```

## List

`GET /api/v1/api-keys` returns the keys **you** created (not every key in the organization), with prefix, permissions, expiry and status. The full key value is never shown again after creation. Only the SHA-256 hash of a key is stored.

## Delete

`DELETE /api/v1/api-keys/{key_id}` revokes the key by marking it inactive. You can revoke a key you created; revoking someone else's takes an admin, and otherwise the answer is `404`. New requests with a revoked key are rejected with `401`. A request already being served is not interrupted.
