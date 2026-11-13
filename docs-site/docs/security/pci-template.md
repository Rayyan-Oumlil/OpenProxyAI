---
title: PCI-aligned Template
description: "The Finance policy template: payment and banking keywords and entities, injection and response guardrails. What it sets and what it does not."
---

# PCI-aligned Template

A pre-built policy configuration for organizations handling payment and cardholder data. Your own PCI program and assessment are unaffected by it. **This is a policy template you configure and enforce yourself, not a claim that OpenProxyAI holds a PCI-DSS certification or authorization.** Your own compliance program is unaffected by it. It is a technical starting point.

## What it sets

Template name: `finance_pci`. Enforcement mode `enforce`, with:

- **Blocked keywords** (case-insensitive substring match): account number, routing number, wire transfer, swift code, trading strategy, insider
- **PII detection** for: PERSON, CREDIT_CARD, US_BANK_NUMBER, US_SSN, IBAN_CODE, PHONE_NUMBER, EMAIL_ADDRESS
- **Prompt-injection detection** on
- **Response guardrails** on, with PII in responses redacted
- **Retention target recorded:** 365 days (1 year). The retention that is actually applied to request logs comes from your plan, not from the template.

Payment card numbers that pass a checksum are detected by the built-in detector, so a request containing one is blocked in `enforce` mode. The template does not set rate limits and does not add transaction-level logging beyond the standard request log.

## Applying it

```bash
curl -X POST https://gateway.your-company.com/api/v1/organizations/current/policy/apply-template   -H "Authorization: Bearer $ADMIN_JWT" -H "Content-Type: application/json"   -d '{"template": "finance_pci"}'
```

Applying it replaces the guardrail settings above and keeps your model allowlist, rate limits and MCP tool lists. See [Compliance Templates](/guides/compliance-templates) for the full comparison and what no template does.

## After applying

Review the result against your own risk assessment. Switch to `log_only` first if you want to measure false positives. See [Policies & Guardrails](/core-concepts/policies-and-guardrails) to adjust it and [Audit Logging](/security/audit-logging) for how long logs are actually kept.
