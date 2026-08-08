---
title: HIPAA-aligned Template
description: The Healthcare policy template — PHI redaction, model allowlists, extended retention.
---

# HIPAA-aligned Template

A pre-built policy configuration for organizations handling protected health information (PHI). **This is a policy template you configure and enforce yourself — not a claim that OpenProxyAI holds a HIPAA certification.** A Business Associate Agreement and your own compliance program are still required on your side; this template is a technical starting point, not a substitute for either.

## What it sets

- **`pii_redact`** tuned with PHI-specific patterns, in `enforce` mode by default
- **`model_allow`** restricting which models can receive requests tagged as containing clinical data
- **Extended audit retention** — longer than the platform default, to match typical healthcare record-retention expectations
- **`secrets_scan`** and **`topic_guard`** enabled in `enforce` mode

## Applying it

```
POST /api/v1/organizations/current/policy/apply-template
```

with the Healthcare template ID from `/api/v1/organizations/current/policy/templates`.

## After applying

Review the resulting policy set against your own risk assessment — see [Policies & Guardrails](/core-concepts/policies-and-guardrails) to adjust individual policies, and [Audit Logging](/security/audit-logging) to confirm your retention window matches your organization's requirement.
