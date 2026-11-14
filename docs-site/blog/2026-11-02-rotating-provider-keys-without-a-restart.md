---
slug: rotating-provider-keys-without-a-restart
title: "Rotating provider keys without a restart"
tags: [security, engineering]
description: How to replace an OpenAI or Anthropic key held by the gateway with no restart and no dropped requests, for keys stored in the gateway, in HashiCorp Vault or in AWS Secrets Manager.
---

You can replace a provider key in OpenProxyAI without restarting anything, because the gateway reads its key list on every request. This post covers three cases (a key stored in the gateway, in HashiCorp Vault, in AWS Secrets Manager) with a short runbook for each.

{/* truncate */}

![A timeline of a Vault key rotation. At time zero the new value is written in Vault. One gateway worker switches to it early and another only when its cache expires. A dashed line marks the earliest safe point to revoke the old key at the provider.](/img/blog/rotating-provider-keys-without-a-restart.svg)

Provider keys are the credentials the gateway holds for OpenAI, Anthropic and others. For the keys your own software uses to call the gateway, read [A leaked key should be a nuisance](/blog/a-leaked-key-should-be-a-nuisance).

## Why no restart is needed

For every request, the gateway selects the active provider keys for the organization, so a key you add, deactivate or delete is in or out on the next request. Only secrets read from Vault or AWS are cached, and only for a short time.

When several active keys serve a provider, one is picked by weight and the rest become fallbacks. That gives you a natural canary: add the new key with a small weight, watch it, then retire the old one.

## What the rotate endpoint is for

The rotate endpoint re-encrypts a stored key with fresh encryption and writes an audit entry. It keeps your stored secrets fresh at rest. To change the provider secret itself, use the runbooks below.

## Runbook 1: a key stored in the gateway

Add the new key, then retire the old one.

1. Optional canary: give the old key a high weight and the new key a low one, so a small share of traffic goes to the new key first.
2. Add the new key with the provider keys API. It is stored encrypted and never returned.
3. Deactivate the old key.
4. Revoke the old key at the provider.
5. Later, delete the old key's row.

## Runbook 2: a key in Vault

The gateway holds a path, not a secret. Write the new value to the same path and field in Vault (KV v2). The gateway reads the latest version, as Vault's API does when no version is given.

The new value arrives within a short cache window, 60 seconds by default. Each gateway process has its own cache, so processes switch at slightly different moments, as the diagram shows. Revoke the old key at the provider only after that window, plus your longest request time.

To catch a bad value before it carries traffic, use two paths instead of overwriting one: create a second provider key on a new path with a small weight, watch it, then deactivate the first.

## Runbook 3: a key in AWS Secrets Manager

The same shape, with a secret name inside your organization's folder. Update the secret in AWS. The gateway reads the current version, as AWS does when no version is given, with the same short cache window. The secret may be plain text or JSON read by field.

See [Provider keys from Vault and AWS](/guides/secrets-from-vault) for the setup.

## When a secret cannot be read

The rule is no silent fallback to another source. If Vault or AWS cannot give the secret, that key is skipped and the reason is logged without the secret. If another key for that provider can be read, it serves the request. If none can, the request gets a clear `503`. An external key is never quietly replaced by a stored value.

## Health, circuit breaker and audit

Two optional safeguards help during a rotation:

- **Health check:** periodically sends a tiny request per key and excludes a key that keeps failing.
- **Circuit breaker:** pauses a provider after repeated failures.

Creating, updating, rotating and deleting a provider key each write an admin audit entry with the actor and IP address. Filter with the audit log endpoint by resource type `provider_key`. For Vault and AWS keys the entry records the source and path, never the secret.

![The provider keys page of the admin console, listing a key with its provider, alias, region, endpoint, maximum data class, key prefix, weight, circuit state, status and creation date, with a toggle and a delete button.](/img/blog/console-provider-keys.png)

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

Needs Docker, no provider key. Console at http://localhost:5173. Star the repo if you want to follow along, or open an issue with the rotation flow you need.

## Sources

- OpenProxyAI docs: [Provider keys from Vault and AWS](/guides/secrets-from-vault), [Provider keys API](/api-reference/provider-keys), [Provider routing](/core-concepts/provider-routing), [Audit logging](/security/audit-logging).
- On this blog: [When every authorized provider is down](/blog/when-every-authorized-provider-is-down), [Failover can leak data](/blog/failover-can-leak-data).
- Vault KV version 2 API, read secret version (no version means latest): https://developer.hashicorp.com/vault/api-docs/secret/kv/kv-v2
- AWS Secrets Manager GetSecretValue (no version means `AWSCURRENT`): https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_GetSecretValue.html

These statements are based on OpenProxyAI's behavior at the post date.
