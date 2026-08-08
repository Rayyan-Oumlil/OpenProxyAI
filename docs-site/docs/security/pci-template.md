---
title: PCI-aligned Template
description: The Finance policy template — cardholder data blocking, transaction logging, stricter rate limits.
---

# PCI-aligned Template

A pre-built policy configuration for organizations handling payment and cardholder data. **This is a policy template you configure and enforce yourself — not a claim that OpenProxyAI holds a PCI-DSS certification.** Your own PCI compliance program and QSA assessment are unaffected by this template; it's a technical starting point.

## What it sets

- **Cardholder-data blocking** — requests matching card-number-like patterns are blocked before reaching a provider
- **Transaction-context logging** — audit entries capture the transaction context needed for a financial audit trail
- **Stricter default rate limits** — tighter requests/min and tokens/min ceilings than the platform default
- **`secrets_scan`** and **`injection`** enabled in `enforce` mode

## Applying it

```
POST /api/v1/organizations/current/policy/apply-template
```

with the Finance template ID from `/api/v1/organizations/current/policy/templates`.

## After applying

See [Policies & Guardrails](/core-concepts/policies-and-guardrails) to adjust thresholds, and [Rate Limiting & Budgets](/core-concepts/rate-limiting-and-budgets) if the default limits don't match your transaction volume.
