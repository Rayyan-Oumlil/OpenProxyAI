---
title: FedRAMP-aligned Template
description: The Government policy template — air-gapped deployment, data residency, 7-year retention.
---

# FedRAMP-aligned Template

A pre-built policy and deployment configuration for government and public-sector organizations. **This is a template you configure and enforce yourself — not a claim that OpenProxyAI holds FedRAMP authorization.** Your own ATO process is unaffected by this template; it's a technical and policy starting point.

## What it sets

- **Air-gapped deployment support** — pairs with `AIRGAP_MODE=true` (see [Environment Flags](/getting-started/environment-flags)) to disable every subsystem that isn't required for the core request path
- **Data residency enforcement** — routing restricted to approved regions, with no fallback outside them (see [Data Residency](/guides/data-residency))
- **7-year audit retention**
- **`model_allow`** restricted to a narrower, explicitly-approved model list by default

## Applying it

```
POST /api/v1/organizations/current/policy/apply-template
```

with the Government template ID from `/api/v1/organizations/current/policy/templates`.

## Deployment

Government deployments typically pair this template with a self-hosted [Helm](/guides/deploying-with-helm) install inside your own VPC, rather than any managed hosting option.
