---
title: Data residency and region routing
description: Keep requests on provider keys and models that match your organization's data region, and know exactly where the gateway enforces that.
---

# Data residency and region routing

Data residency in OpenProxyAI means the gateway only sends a request to provider keys and models whose region matches your organization's data region. You set one region per organization, tag each provider key and registered model with a region, and the gateway filters on those tags for every request, including failover. This page explains each control, how to set up an EU-only organization, and what the feature does not cover.

## The model

| Setting | Where | Values | Default |
|---|---|---|---|
| Organization data region | The organization | `us`, `eu`, `ap` | `us` |
| Provider key region | Each provider key | `us`, `eu`, `ap`, `global` | `us` |
| Model regions | Each model registry entry | One to four of `us`, `eu`, `ap`, `global` | required |

An organization has exactly one region, not a set of approved regions. `global` on a key or a model means "any region". The tags are statements you make about where a key or model processes data. The gateway enforces them but cannot verify them with the provider, so tag honestly.

## How enforcement works

Two independent filters apply, in this order of the request pipeline.

### 1. Provider key selection (always on)

Before calling a provider, the gateway considers only active keys of that provider whose region equals the organization's region or is `global`. Weighted rotation and failover choose among those keys only. If the in-region keys are all unhealthy, the request fails instead of falling back to an out-of-region key. The same filter applies to the fallback model (`x-openproxy-fallback-model`).

If no key qualifies, the caller gets HTTP 503:

```json
{
  "error": "no_provider_key",
  "detail": "No provider keys available for region 'eu'. Add provider keys tagged with region 'eu' or 'global'."
}
```

Gateway-wide environment keys (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `AZURE_API_KEY`) carry no region tag. They are used only for organizations in a region listed in `SHARED_KEY_REGIONS` (default `us,global`). An `eu` or `ap` organization must therefore bring its own tagged provider keys; it never silently uses a shared environment key.

### 2. Model authorization (with `routing_mode` set to `enforce`)

When the [policy](/core-concepts/policies-and-guardrails) has `routing_mode` set to `enforce`, a request may only use a registered model that is authorized for it. A model is excluded for region when the organization's region is not in the model's `regions` and the model does not list `global`. Exclusion reasons are checked in this order: disabled, no key, key inactive, data class too low, region, risk, not on the policy's approved list. The first reason that applies is reported.

A blocked request returns HTTP 446:

```json
{
  "error": "routing_blocked",
  "reason_code": "no_authorized_model",
  "detail": "No model authorized for this request's data class can serve it.",
  "explanation": "openai/gpt-4o cannot serve this request under your organization's data-region setting.",
  "route_reason": "not_authorized:region",
  "data_class": "internal",
  "requested_model": "openai/gpt-4o"
}
```

The gateway never swaps in a different model: an unauthorized model is refused. With `log_only`, the same decision is recorded but the request goes through, which is how you preview the effect. Switching to `enforce` is refused with HTTP 409 (`empty_registry`) unless at least one enabled model has an active key.

When routing is enforced, the model's registry entry also fixes the key: only the key linked to that model is used, never another key of the provider and never an environment key.

## Set up an EU-only organization

**1. Set the organization region** (admin):

```bash
curl -X PATCH https://your-gateway/api/v1/organizations/current \
  -H "Authorization: Bearer $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"data_region": "eu"}'
```

The change is recorded in the audit log. The region is read on each request, so it applies to the next call.

**2. Add a provider key tagged `eu`:**

```bash
curl -X POST https://your-gateway/api/v1/provider-keys \
  -H "Authorization: Bearer $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "azure",
    "key_alias": "azure-eu-west",
    "api_key": "REPLACE_WITH_KEY",
    "region": "eu",
    "weight": 1
  }'
```

Use `PATCH /api/v1/provider-keys/{key_id}` with `{"region": "eu"}` to retag an existing key. Keys read from a secret manager keep their own region tag. See [Secrets from Vault](/guides/secrets-from-vault) and the [keys reference](/api-reference/keys).

**3. Register the model with its regions:**

```bash
curl -X POST https://your-gateway/api/v1/model-registry \
  -H "Authorization: Bearer $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model_id": "azure/gpt-4o",
    "provider_key_id": "KEY_ID_FROM_STEP_2",
    "max_data_class": "confidential",
    "regions": ["eu"],
    "risk_rating": "medium"
  }'
```

`regions` is the list of regions where the provider processes the model's data. The registry also holds `retention_days`, `trains_on_data`, `capabilities` and `cost_tier`.

**4. Preview, then enforce.** Set `routing_mode` to `log_only`, send representative traffic, check which requests would be excluded for `region`, then set `enforce`.

## Other places region matters

| Component | Behavior |
|---|---|
| Semantic cache | The embedding endpoint is shared and untagged, so semantic caching is skipped for organizations outside `SHARED_KEY_REGIONS` and in air-gapped mode. Exact-match caching still works. See [Caching](/core-concepts/caching). |
| Air-gapped mode (`AIRGAP_MODE`) | Disables the outbound integrations and the semantic cache embedding call. See [Environment flags](/getting-started/environment-flags). |
| Compliance templates | They set guardrail fields only and do not turn on data residency or assign regions. See [Compliance templates](/security/compliance-templates). |

## What this does not do

- It does not choose where the gateway itself runs, or where its database and logs are stored. Deploy the gateway in the region you need; see [Deployment](/guides/deployment).
- It does not verify a provider's actual processing location. A key or model tagged `eu` is trusted to be `eu`.
- Log retention comes from the plan, not from the region setting.
- It restricts requests sent through the gateway. It does not control direct calls your applications make to providers.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| 503 `no_provider_key` naming your region | No active key tagged with your region or `global` | Add or retag a key |
| 503 for an `eu` organization that worked before the region change | It was relying on a shared environment key | Add region-tagged keys |
| 446 `routing_blocked` with `route_reason` `not_authorized:region` | The model's `regions` do not include your region and not `global` | Correct the model's regions, or choose another model |
| 409 `empty_registry` when enabling `enforce` | No enabled model with an active key | Register one, or stay on `log_only` |
| Reworded prompts stopped hitting the cache after moving region | Semantic cache is skipped outside `SHARED_KEY_REGIONS` | Expected; exact cache continues |

## Next steps

- [Provider routing](/core-concepts/provider-routing) for weights, health and failover.
- [Policies and guardrails](/core-concepts/policies-and-guardrails) for routing modes and data classes.
- [Trust center](/security/trust-center) for the wider security model.
