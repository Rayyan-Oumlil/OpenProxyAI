---
title: Provider Keys
description: Register and rotate the upstream provider keys OpenProxyAI routes to.
---

# Provider Keys

Provider keys are the credentials OpenProxyAI holds for each upstream provider (OpenAI, Anthropic, Azure, Mistral, etc.) — distinct from the [API keys](/api-reference/api-keys) your applications use to call OpenProxyAI itself.

```
GET    /api/v1/provider-keys
POST   /api/v1/provider-keys
PATCH  /api/v1/provider-keys/{key_id}
DELETE /api/v1/provider-keys/{key_id}
POST   /api/v1/provider-keys/{key_id}/rotate
```

## Create

```json
POST /api/v1/provider-keys
{
  "provider": "openai",
  "key_alias": "prod-openai",
  "api_key": "sk-...",
  "weight": 70,
  "region": "us"
}
```

Send exactly one of `api_key`, `vault_path` (HashiCorp Vault) or `aws_secret_name` (AWS Secrets Manager). With the last two the gateway keeps no copy of the key: see [Provider keys from Vault](/guides/secrets-from-vault). `api_base` points the key at a custom endpoint, and `max_data_class` and `is_internal` describe what that endpoint may receive.

`weight` is a whole number from 1 to 100 and sets this key's share of weighted rotation relative to other keys for the same provider. `region` is `us`, `eu`, `ap` or `global` and is used for [data residency](/guides/data-residency) filtering. The raw key is stored encrypted and never returned; the list shows a prefix only.

## Rotate

```
POST /api/v1/provider-keys/{key_id}/rotate
```

This **re-encrypts the stored secret** with a fresh encryption token. The provider key itself does not change, so it does not help if the key has been exposed. Admins only. A key that lives in Vault or AWS Secrets Manager answers `409`, because it is rotated there.

To replace a provider key with a new secret, create a new key with `POST`, check that it serves traffic, then switch the old one off with `PATCH` (`{"is_active": false}`) or `DELETE` it. The `PATCH` body has no field for the secret.

See [Provider Routing](/core-concepts/provider-routing) for how weight and region interact with failover.
