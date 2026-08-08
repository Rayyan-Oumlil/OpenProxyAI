---
title: Billing
description: Plans, usage, and managing your subscription.
---

# Billing

## Plans

See [Pricing](https://openproxy.ai/pricing) for current plan tiers and what's included in each.

## Managing your subscription

```
POST /api/v1/billing/checkout
POST /api/v1/billing/portal
```

`checkout` starts a new subscription; `portal` opens a self-service billing portal for updating payment details, viewing invoices, or changing plans on an existing subscription.

## Usage-based billing

Metered usage syncs to your billing provider on an hourly background schedule. This sync is disabled entirely in [air-gapped deployments](/getting-started/environment-flags) (`AIRGAP_MODE=true`), where billing is handled outside the platform rather than through automatic metered sync.

## Webhook

```
POST /api/v1/billing/webhook
```

Receives subscription lifecycle events from the billing provider — not something you call directly, but relevant if you're debugging a plan change that hasn't reflected in the console yet.
