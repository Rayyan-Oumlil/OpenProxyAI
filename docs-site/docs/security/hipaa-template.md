---
title: HIPAA-aligned Template
description: "The Healthcare policy template: PHI-oriented keywords and entities, injection and response guardrails. What it sets and what it does not."
---

# HIPAA-aligned Template

A pre-built policy configuration for organizations handling protected health information (PHI). A Business Associate Agreement and your own compliance program are still required on your side. **This is a policy template you configure and enforce yourself, not a claim that OpenProxyAI holds a HIPAA certification or authorization.** Your own compliance program is unaffected by it. It is a technical starting point.

## What it sets

Template name: `healthcare_hipaa`. Enforcement mode `enforce`, with:

- **Blocked keywords** (case-insensitive substring match): diagnosis, patient name, medical record, prescription, treatment plan
- **PII detection** for: PERSON, PHONE_NUMBER, EMAIL_ADDRESS, US_SSN, CREDIT_CARD, DATE_OF_BIRTH, MEDICAL_LICENSE, US_DRIVER_LICENSE
- **Prompt-injection detection** on
- **Response guardrails** on, with PII in responses redacted
- **Retention target recorded:** 2,555 days (7 years). The retention that is actually applied to request logs comes from your plan, not from the template.

Names, phone numbers and the other entities beyond email, SSN and card numbers need the optional Presidio detector.

## Applying it

```bash
curl -X POST https://gateway.your-company.com/api/v1/organizations/current/policy/apply-template   -H "Authorization: Bearer $ADMIN_JWT" -H "Content-Type: application/json"   -d '{"template": "healthcare_hipaa"}'
```

Applying it replaces the guardrail settings above and keeps your model allowlist, rate limits and MCP tool lists. See [Compliance Templates](/guides/compliance-templates) for the full comparison and what no template does.

## After applying

Review the result against your own risk assessment. Switch to `log_only` first if you want to measure false positives. See [Policies & Guardrails](/core-concepts/policies-and-guardrails) to adjust it and [Audit Logging](/security/audit-logging) for how long logs are actually kept.
