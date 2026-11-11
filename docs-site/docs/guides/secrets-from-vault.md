---
title: Provider keys from HashiCorp Vault
description: Keep provider keys in Vault and let the gateway read them, instead of storing a copy.
---

# Provider keys from HashiCorp Vault

By default a provider key is stored encrypted in the gateway's database. If your security team wants the key to live in Vault only, a provider key can instead **point at a secret in Vault**. The gateway then holds no copy of it: it reads the key when a request needs it, and a key you rotate in Vault is picked up within a minute.

## What the operator sets

Vault is configured by whoever runs the gateway, never by an organization:

| Setting | |
|---|---|
| `VAULT_ADDR` | The Vault address. Must be `https://`; plain `http://` is refused unless `VAULT_ALLOW_INSECURE_HTTP=true` (development only). |
| `VAULT_TOKEN` | A token the gateway uses, **or** |
| `VAULT_ROLE_ID` and `VAULT_SECRET_ID` | An AppRole. The gateway logs in, reuses the token until it nears expiry, and logs in again. |
| `VAULT_NAMESPACE` | For Vault Enterprise namespaces. Optional. |
| `VAULT_KV_MOUNT` | The KV v2 mount. Default `secret`. |
| `VAULT_PATH_PREFIX` | The folder each organization may use. Default `openproxyai/{org_id}/`. |
| `VAULT_CACHE_SECONDS` | How long a secret is cached in memory. Default 60. |

Give the gateway's Vault policy read access to the prefix and nothing else, for example `path "secret/data/openproxyai/*" { capabilities = ["read"] }`.

## What an org admin does

Create the provider key with a path instead of a key:

```bash
curl -X POST https://your-gateway/api/v1/provider-keys \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d '{"provider": "openai", "key_alias": "prod-openai", "vault_path": "openproxyai/<your-org-id>/openai", "vault_field": "api_key"}'
```

Send exactly one of `api_key` and `vault_path`. `vault_field` is the field inside the secret (default `api_key`). The gateway reads the secret once when you create the key, to check it is readable, and discards the value. The key list shows `vault:<path>` where it would show a key prefix.

## The rules

| Rule | Why |
|---|---|
| **A path must be inside your organization's folder.** Anything else (another org's folder, `..`, a leading slash, odd characters) is refused when you create the key and again on every read. | The gateway has one Vault credential. Without this rule an admin could name another tenant's secret and the gateway would fetch it. |
| **No fallback.** If Vault cannot give the secret, that key is skipped, the reason is logged (status code only, never Vault's response or the value), and if no key is left the request gets a 503. The gateway never substitutes a stored key for a Vault one. | A silent fallback would hide an outage and could send traffic through a key you meant to retire. |
| **Rotate in Vault.** `POST .../rotate` on a Vault-backed key is a 409: there is nothing stored here to re-encrypt. | |
| **No redirects.** A redirect from Vault is an error, not followed. | The token must not be sent anywhere else. |
| **Never logged, never returned.** The value appears in no response, audit entry or log line. The audit entry records the path, not the secret. | |

A Vault-backed key still has its own **data class**, **region** and **custom endpoint**, so routing treats it like any other key.

Not included: writing secrets to Vault, dynamic secrets, and other secret managers (AWS Secrets Manager, GCP Secret Manager).
