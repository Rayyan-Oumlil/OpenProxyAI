---
title: Compliance Templates
description: Pre-built policy templates aligned to Healthcare, Finance, and Government requirements.
---

# Compliance Templates

OpenProxyAI ships three pre-built policy templates as a starting point for regulated environments. **These are policy configuration templates you apply and enforce yourself — not a claim that OpenProxyAI itself holds a corresponding certification.** Your own audit still runs against your own controls.

## Applying a template

```
POST /api/v1/organizations/current/policy/apply-template
```

Available templates are listed at `/api/v1/organizations/current/policy/templates`. Applying a template merges its defaults into your org's existing policy configuration — it does not silently overwrite policies you've already customized.

## Healthcare (HIPAA-aligned)

- PHI redaction defaults tuned for clinical data
- Model allowlists restricting which models can see patient data
- Extended audit retention

## Finance (PCI-aligned)

- Cardholder-data blocking
- Transaction-context logging
- Stricter default rate limits

## Government (FedRAMP-aligned)

- Air-gapped deployment support (see [Deploying with Helm](/guides/deploying-with-helm) and [Environment Flags](/getting-started/environment-flags))
- Data residency enforcement (see [Data Residency](/guides/data-residency))
- 7-year retention

## Customizing after applying

A template is a starting point, not a lock-in. After applying one, individual policies can still be switched between `enforce` and `log-only`, and thresholds adjusted, via `/api/v1/organizations/current/policy` — see [Policies & Guardrails](/core-concepts/policies-and-guardrails).
