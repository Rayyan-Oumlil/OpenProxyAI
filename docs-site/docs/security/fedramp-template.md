---
title: FedRAMP-aligned Template
description: "The Government policy template: classification-marking keywords, PII entities, injection and response guardrails. What it sets and what it does not."
---

# FedRAMP-aligned Template

A pre-built policy configuration for government and public-sector organizations. Your own authorization process is unaffected by it. **This is a policy template you configure and enforce yourself, not a claim that OpenProxyAI holds a FedRAMP certification or authorization.** Your own compliance program is unaffected by it. It is a technical starting point.

## What it sets

Template name: `government_fedramp`. Enforcement mode `enforce`, with:

- **Blocked keywords** (case-insensitive substring match): classified, top secret, secret//noforn, controlled unclassified, fouo
- **PII detection** for: PERSON, PHONE_NUMBER, EMAIL_ADDRESS, US_SSN, US_PASSPORT, US_DRIVER_LICENSE, CREDIT_CARD, IP_ADDRESS, LOCATION
- **Prompt-injection detection** on
- **Response guardrails** on, with PII in responses redacted
- **Retention target recorded:** 1,095 days (3 years). The retention that is actually applied to request logs comes from your plan, not from the template.

The template does not turn on air-gapped mode or data residency. For those, see `AIRGAP_MODE` in [Environment Flags](/getting-started/environment-flags) and [Data Residency](/guides/data-residency), and assign US-region provider keys yourself.

## Applying it

```bash
curl -X POST https://gateway.your-company.com/api/v1/organizations/current/policy/apply-template   -H "Authorization: Bearer $ADMIN_JWT" -H "Content-Type: application/json"   -d '{"template": "government_fedramp"}'
```

Applying it replaces the guardrail settings above and keeps your model allowlist, rate limits and MCP tool lists. See [Compliance Templates](/guides/compliance-templates) for the full comparison and what no template does.

## After applying

Review the result against your own risk assessment. Switch to `log_only` first if you want to measure false positives. See [Policies & Guardrails](/core-concepts/policies-and-guardrails) to adjust it and [Audit Logging](/security/audit-logging) for how long logs are actually kept.
