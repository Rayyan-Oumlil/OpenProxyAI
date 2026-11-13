---
slug: rotating-provider-keys-without-a-restart
title: "Rotating provider keys without a restart, and what the rotate endpoint does"
tags: [security, engineering]
description: How to replace an OpenAI or Anthropic key held by the gateway with no restart and no dropped requests, what the rotate endpoint really does, how fast Vault and AWS changes arrive, and what happens when a secret cannot be read.
---

You can replace a provider key in OpenProxyAI without restarting anything, because the gateway reads its key list from the database on every request. The surprise is the rotate endpoint: it does not change your provider secret. This post covers three cases (a key stored in the gateway, in HashiCorp Vault, in AWS Secrets Manager), gives a runbook for each with the real calls, and lists what can go wrong, including a rejected key that is not retried on another key.

{/* truncate */}

![A timeline of a Vault key rotation. At time zero the new value is written in Vault. One gateway worker switches to it after 20 seconds and another only after 60 seconds, when its cache expires. A dashed line at 60 seconds marks the earliest safe point to revoke the old key at the provider.](/img/blog/rotating-provider-keys-without-a-restart.svg)

Provider keys are the credentials the gateway holds for OpenAI, Anthropic and others. For the keys your own software uses to call the gateway, read [A leaked key should be a nuisance](/blog/a-leaked-key-should-be-a-nuisance).

## Why no restart is needed

For every request, the gateway selects the active provider keys for the organization from the database, then reads each chosen key's secret. Nothing in the key list is cached in the process. So a key you add, deactivate or delete is in or out on the next request. Only secrets read from Vault or AWS are cached, and only for a short time.

When several active keys serve a provider, one is picked by weighted random choice and the rest become fallbacks. The `round_robin` router strategy ignores weights.

## What the rotate endpoint does

`POST /api/v1/provider-keys/{key_id}/rotate` decrypts the stored key and encrypts the same value again with a fresh token. The provider secret is unchanged. The audit entry is `provider_key.rotated`, with only the first characters of the alias as `key_prefix`. The optional scheduler (`KEY_ROTATION_SCHEDULER_ENABLED`, off by default, every 30 days by default) does the same re-encryption for all active keys.

So if a provider key leaked, rotate does nothing about the leak. An earlier version of our API reference said rotate issues a replacement and invalidates the old key. That was wrong, and the reference now matches the code. Use the runbooks below.

For a Vault or AWS key, rotate returns `409` with `vault_backed_key`: nothing is stored to re-encrypt. The console has no rotate button. It can add, activate, deactivate and delete a key.

## Runbook 1: a key stored in the gateway

There is no field to replace the value of an existing stored key: the update request accepts alias, weight, active flag, region, endpoint and data class only. So you add the new key, then retire the old one.

```bash
# 1. Optional canary: give the old key the maximum weight first
curl -s -X PATCH https://your-gateway/api/v1/provider-keys/$OLD_ID \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d '{"weight": 100}'

# 2. Add the new key (stored encrypted, never returned)
curl -s -X POST https://your-gateway/api/v1/provider-keys \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d '{"provider": "openai", "key_alias": "prod-openai-2", "api_key": "sk-new...", "weight": 1}'

# 3. Take the old key out of the pool
curl -s -X PATCH https://your-gateway/api/v1/provider-keys/$OLD_ID \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d '{"is_active": false}'
```

Then revoke the old key at the provider, in this order. A request that picks a key the provider already revoked is rejected and, as explained below, not retried on another key. Later, `DELETE /api/v1/provider-keys/{key_id}` removes the old row. Weights run from 1 to 100, so a new key at weight 1 beside an old key at 100 gets roughly one request in 101, with the default strategy.

## Runbook 2: a key in Vault

The gateway holds a path, not a secret. Write the new value to the same path and field in Vault (KV v2). The gateway asks Vault for the path with no version, so it gets the latest. Vault's API documents that a read without a version returns the latest version.

The new value arrives within `VAULT_CACHE_SECONDS`, default 60. Each gateway process caches a secret from the moment it read it, so a process serves the old value for at most 60 seconds after you write. Several workers each have their own cache and switch at different moments, as the diagram shows. A test covers it: the old value is served from cache, the new one appears after expiry.

Revoke the old key at the provider only after those 60 seconds, plus your longest request time.

To catch a bad value before it carries traffic, use two paths instead of overwriting one: create a second provider key on a new path with a small weight, watch it, then deactivate the first. The gateway checks only that the secret is readable and non-empty. It does not test the value with the provider.

## Runbook 3: a key in AWS Secrets Manager

The same shape, with a secret name (never an ARN) inside your organization's folder:

```bash
curl -s -X POST https://your-gateway/api/v1/provider-keys \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d '{"provider": "openai", "key_alias": "prod-openai", "aws_secret_name": "openproxyai/<your-org-id>/openai", "aws_secret_field": "api_key"}'
```

Update the secret in AWS. The gateway asks for the secret by name with no version id or stage, and AWS documents that without one it returns the `AWSCURRENT` version. The cache window is `AWS_SECRET_CACHE_SECONDS`, default 60. The secret may be plain text or JSON read by field. Binary secrets are refused.

## When the secret cannot be read

The rule is no fallback to another source. If Vault or AWS cannot give the secret, that key is skipped, and the reason is logged with a status code or error code, never the secret or the response body. Then:

- If another key for that provider can be read (for example a stored one), it serves the request. An external key is never replaced by a stored value.
- If no candidate key is readable, the request gets a `503` with `no_provider_key`. A test asserts that a Vault outage gives a 503 and never another source.
- Failures are not cached, and an expired cache entry is not served after the cache time. A Vault outage longer than the cache window therefore fails requests for that key.

One caution: if an organization has no active key for a provider in its region, the gateway can use an operator-set environment key (for example `OPENAI_API_KEY`) in regions listed in `SHARED_KEY_REGIONS` (default `us,global`). Deactivating your last stored key can hand traffic to it. This does not apply when keys exist but are unreadable.

## Health, circuit breaker and audit

A rejected key is not retried elsewhere. The fallback loop retries only on status 429, 500, 502, 503 and 504. A 401 or 403 from the provider is not in that list, so a request that picked a bad key fails instead of trying the next one. We did not trace what the client then sees.

Two optional safeguards exist, both off by default:

- **Health check** (`PROVIDER_HEALTH_CHECK_ENABLED`): every 5 minutes it sends a one-token request per key, for OpenAI, Anthropic and custom endpoints. After 3 failed checks in a row (roughly 10 to 15 minutes) the key is marked unhealthy and excluded from selection. Other providers are assumed healthy. A key whose secret cannot be read is skipped by the check, not marked.
- **Circuit breaker** (`CIRCUIT_BREAKER_ENABLED`): opens for 60 seconds after 5 retryable failures in a row. A 401 does not count, so it will not trip on a revoked key.

Audit: creating, updating (including the active toggle), rotating and deleting a provider key each write an admin audit entry with the actor's email and IP address. Filter with `GET /api/v1/admin/audit-log?resource_type=provider_key`. For Vault and AWS keys the entry records the source and path, never the secret. Creation records the alias as the resource id, the other actions the key's UUID. We found no entry written for each secret read.

![The provider keys page of the admin console, listing a key with its provider, alias, region, endpoint, maximum data class, key prefix, weight, circuit state, status and creation date, with a toggle and a delete button.](/img/blog/console-provider-keys.png)

## What this does not do

- **Rotate does not replace a secret.** It re-encrypts the same one.
- **A stored key's value cannot be edited.** Add a new key and retire the old one.
- **No refresh on demand.** The caches live in each process, and we found no endpoint that clears them.
- **No test of a new value** against the provider.
- **Rejected keys are not retried** on another key, and the health check and circuit breaker are off by default.
- **No secret writing.** The gateway only reads Vault and AWS. It does not rotate secrets there, and has no GCP Secret Manager.
- **Docs drift.** The API reference describes rotate and the create fields differently from the code.

## What to do now

1. Add then retire for stored keys, a new value or a new path for Vault and AWS.
2. Revoke at the provider last, after the cache window.
3. Turn on the health check if you want a bad key excluded automatically.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

Needs Docker, no provider key. Console: http://localhost:5173.

## Sources

- OpenProxyAI docs: [Provider keys from Vault and AWS](/guides/secrets-from-vault), [Provider keys API](/api-reference/provider-keys), [Provider routing](/core-concepts/provider-routing), [Audit logging](/security/audit-logging).
- On this blog: [When every authorized provider is down](/blog/when-every-authorized-provider-is-down), [Failover can leak data](/blog/failover-can-leak-data).
- Vault KV version 2 API, read secret version (no version means latest): https://developer.hashicorp.com/vault/api-docs/secret/kv/kv-v2
- AWS Secrets Manager GetSecretValue (no version means `AWSCURRENT`): https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_GetSecretValue.html

These statements are based on the OpenProxyAI source code, tests and docs, and on the two vendor pages above, as read on November 13, 2026. No command here was run against a live gateway.
