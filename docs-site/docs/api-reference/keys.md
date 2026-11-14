---
title: API keys and provider keys
description: Create, expire, revoke and replace the API keys your apps use, and register the provider keys the gateway routes to.
---

# API keys and provider keys

OpenProxyAI has two kinds of keys, and mixing them up is the most common mistake. **API keys** are what your applications send to OpenProxyAI (`opai_...`). **Provider keys** are the credentials OpenProxyAI holds for upstream providers such as OpenAI or Anthropic. This page covers both, including how each one is created, shown, expired, revoked and replaced.

| | API key | Provider key |
|---|---|---|
| Used by | Your application, calling the gateway | The gateway, calling the provider |
| Who manages it | Any member (their own keys); admins can revoke anyone's | Admins only |
| Shown in full | Once, at creation | Never returned |
| Stored as | A SHA-256 hash | Encrypted, or a reference to Vault or AWS Secrets Manager |

Both sets of endpoints are management endpoints: authenticate with a session token, not a proxy key. See [Authentication](/getting-started/authentication).

## API keys

```
GET    /api/v1/api-keys
POST   /api/v1/api-keys
DELETE /api/v1/api-keys/{key_id}
```

### Create a key

```bash
curl -X POST https://api.openproxy.ai/api/v1/api-keys \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{
    "name": "prod-eng-platform",
    "permissions": ["proxy:llm"],
    "team_id": null,
    "expires_at": "2027-06-30T00:00:00Z"
  }'
```

| Field | Rules |
|---|---|
| `name` | Required, 1 to 100 characters. Must be unique among your active keys (`409`) |
| `permissions` | List of permission strings. Empty or omitted means `["proxy:llm"]` |
| `team_id` | Optional. You must be a member of that team (`403` otherwise, `404` if unknown) |
| `expires_at` | Optional ISO timestamp. `null` means the key never expires |

The `201` response is the only time the full key appears:

```json
{
  "id": "…",
  "name": "prod-eng-platform",
  "key": "opai_prod_1a2b3c4d_<32 hex characters><4 checksum characters>",
  "key_prefix": "opai_prod_1a2b3c4d",
  "permissions": ["proxy:llm"],
  "is_active": true,
  "expires_at": "2027-06-30T00:00:00Z",
  "team_id": null,
  "created_at": "2026-11-13T15:10:00Z",
  "warning": "Store this key securely. It will not be shown again."
}
```

The key starts with `opai_prod_` or `opai_dev_`, matching the gateway's environment. Creation answers `402` when your organization already has as many active keys as its plan allows (5 on community, 50 on team, 200 on business, 500 on metered, unlimited on enterprise).

### Permissions

| Permission | Allows |
|---|---|
| `proxy:llm` | The default. Required by [batches](/api-reference/batches) and [feedback](/api-reference/feedback) |
| `proxy:mcp` | Required by the [MCP gateway](/guides/mcp-gateway) |

A key lacking the permission an endpoint requires is refused. Give a key only the permissions its application needs.

### Teams and budgets

A key with a `team_id` counts its usage against that team's budget without any extra header. A key without one can still select a team per request with the `x-openproxy-team-id` header; when both are present, the key's team wins. See [Rate limiting and budgets](/core-concepts/rate-limiting-and-budgets).

### List keys

`GET /api/v1/api-keys` returns the keys you created, not every key in the organization. Each entry has `id`, `name`, `key_prefix`, `permissions`, `is_active`, `expires_at`, `created_at` and `team_id`. The full value is never shown again.

### Lifecycle: show-once, expire, revoke, replace

1. **Create.** The full key is returned once. Only its hash is stored, so a lost key cannot be recovered.
2. **Use.** On every request the gateway rechecks that the key exists, is active, has not expired, and that its owner is still an active user in the same organization. Nothing about authorization is cached. A failure of any check is a `401`.
3. **Expire.** If `expires_at` is set, the key stops working at that time and requests return `401`. The key stays in the list as an expired key. You cannot change `expires_at` later; to extend, create a new key.
4. **Revoke.** `DELETE /api/v1/api-keys/{key_id}` marks the key inactive and answers `204`. You can revoke your own keys; revoking someone else's takes an admin. Otherwise the answer is `404`, so an id does not confirm that a key exists. New requests with the key get `401`; a request already in flight is not interrupted.
5. **Replace (there is no rotate call).** For an application key, "rotate" means: create a new key, deploy it to the application, confirm traffic, then revoke the old one. Do this immediately if a key was committed to a repository or logged.

Deactivating the owner (see [users](/api-reference/organizations-teams-users)) also stops all of their keys, because the owner check fails.

```bash
# Replace a key: create the new one, switch the app, then revoke the old
curl -X DELETE https://api.openproxy.ai/api/v1/api-keys/$OLD_KEY_ID \
  -H "Authorization: Bearer $TOKEN"
```

## Provider keys

```
GET    /api/v1/provider-keys
POST   /api/v1/provider-keys
PATCH  /api/v1/provider-keys/{key_id}
POST   /api/v1/provider-keys/{key_id}/rotate
DELETE /api/v1/provider-keys/{key_id}
```

All provider-key endpoints need the `admin` role (`403` otherwise).

### Register a provider key

```bash
curl -X POST https://api.openproxy.ai/api/v1/provider-keys \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{
    "provider": "openai",
    "key_alias": "prod-openai",
    "api_key": "sk-...",
    "weight": 70,
    "region": "us"
  }'
```

| Field | Rules |
|---|---|
| `provider` | Required, up to 50 characters, for example `openai` |
| `key_alias` | Required, up to 100 characters. A label you choose |
| `api_key` | The raw key, at least 8 characters. Stored encrypted, never returned |
| `vault_path`, `vault_field` | Read the key from HashiCorp Vault instead. The path must be inside your organization's folder |
| `aws_secret_name`, `aws_secret_field` | Read the key from AWS Secrets Manager instead. A secret name, not an ARN |
| `weight` | Whole number 1 to 100, default 1. Share of weighted rotation among keys of the same provider |
| `region` | `us`, `eu`, `ap` or `global`, default `us`. Used for [data residency](/security/data-residency) filtering |
| `api_base` | Custom endpoint (vLLM, Ollama, a private gateway). Omit to use the provider's own |
| `max_data_class` | Most sensitive data class this endpoint may receive: `public`, `internal` (default), `confidential`, `secret` |
| `is_internal` | `true` if the endpoint sits inside your own network |

Send exactly one of `api_key`, `vault_path` or `aws_secret_name`. With the last two, the gateway keeps no copy of the key; see [Secrets from Vault](/guides/secrets-from-vault). The reference is checked when you create the key: an unreadable or out-of-folder reference answers `422`, and so does an invalid `api_base`.

The response and the list show `key_prefix` (the first 8 characters followed by an ellipsis, or the Vault location), `secret_source`, `weight`, `is_active`, `region`, `api_base`, `max_data_class`, `is_internal`, `health_status` and `consecutive_failures`. Depending on gateway settings they also show circuit-breaker and adaptive-weight fields (`circuit_open_until`, `latency_p99_ms`, `error_rate`, `effective_weight`).

### Change a provider key

`PATCH` accepts `key_alias`, `weight`, `is_active`, `region`, `api_base` (send `null` to clear it), `max_data_class` and `is_internal`. It has no field for the secret. Set `{"is_active": false}` to take a key out of rotation without deleting it. `DELETE` removes it and answers `204`.

### Rotate a provider key

```
POST /api/v1/provider-keys/{key_id}/rotate
```

```json
{ "rotated": true, "key_id": "…" }
```

This is the point to be precise about: rotate **re-encrypts the stored secret** under a fresh encryption token. The provider key itself does not change, so rotating does not help if the key has been exposed. A key stored in Vault or AWS Secrets Manager answers `409`, because it is rotated there.

An operator can turn on automatic re-encryption of every active key with `KEY_ROTATION_SCHEDULER_ENABLED` (off by default), run every `KEY_ROTATION_INTERVAL_DAYS` (default 30). See [Environment flags](/getting-started/environment-flags).

### Replace a provider key with a new secret

1. `POST` a new provider key with the new secret.
2. Send a request and confirm it is served by the new key.
3. `PATCH` the old key with `{"is_active": false}`, or `DELETE` it.
4. Revoke the old secret at the provider.

See [Provider routing](/core-concepts/provider-routing) for how weight, region and failover interact.

## Errors

| Status | Where | Cause |
|---|---|---|
| `401` | Any call | Missing, expired or revoked credential |
| `402` | Create API key | Plan key limit reached |
| `403` | API key create, provider keys | Not a team member, or not an admin |
| `404` | Revoke, provider key calls | Not found, or not yours to see |
| `409` | Create API key, rotate | Active key with that name exists, or the provider key lives in a secret manager |
| `422` | Create or update provider key | Invalid body, `api_base`, Vault or AWS reference |

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Key worked yesterday, `401` today | Expired, revoked, or the owner was deactivated | Check `is_active` and `expires_at`; create a new key |
| Lost the key value | Only the hash is stored | Create a new key and revoke the old one |
| `409` creating a key | You already have an active key with that name | Pick a new name or revoke the old one |
| `409` on rotate | Key is read from Vault or AWS | Rotate it in the secret manager |
| `422` on a Vault key | Path outside your folder, or not readable | Fix the path or the permissions |

## Next steps

- [Authentication](/getting-started/authentication)
- [Organizations, teams and users](/api-reference/organizations-teams-users)
- [Provider routing](/core-concepts/provider-routing)
- [Secrets from Vault](/guides/secrets-from-vault)
