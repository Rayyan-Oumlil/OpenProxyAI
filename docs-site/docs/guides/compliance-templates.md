---
title: Compliance Templates
description: Three starting policy configurations for healthcare, finance and government, exactly what each one sets, and what a template does not do.
---

# Compliance Templates

OpenProxyAI ships three policy templates as a starting point for regulated environments. **They are policy configurations you apply and enforce yourself. They are not a certification, and applying one does not make a deployment compliant with anything.** Your own audit still runs against your own controls.

## Applying a template

```
GET  /api/v1/organizations/current/policy/templates
POST /api/v1/organizations/current/policy/apply-template
```

```json
{"template": "healthcare_hipaa"}
```

The template names are `healthcare_hipaa`, `finance_pci` and `government_fedramp`. Only admins can apply one, the organization's plan must include PII detection (the Community plan does not), and the change is written to the [admin audit log](/security/audit-logging) as `apply_compliance_template`.

Applying a template **replaces** these settings: enforcement mode, blocked keywords, PII detection and entity list, prompt-injection detection, response guardrails and response PII redaction. Your model allowlist, rate limits, MCP tool lists, routing and every other setting are kept. Because the keyword list is replaced, not merged, any keywords you added are gone.

## What each one sets

All three set enforcement mode to `enforce`, turn on PII detection, prompt-injection detection and response guardrails, and redact PII in responses.

| | Healthcare (`healthcare_hipaa`) | Finance (`finance_pci`) | Government (`government_fedramp`) |
|---|---|---|---|
| Blocked keywords | diagnosis, patient name, medical record, prescription, treatment plan | account number, routing number, wire transfer, swift code, trading strategy, insider | classified, top secret, secret//noforn, controlled unclassified, fouo |
| PII entities | PERSON, PHONE_NUMBER, EMAIL_ADDRESS, US_SSN, CREDIT_CARD, DATE_OF_BIRTH, MEDICAL_LICENSE, US_DRIVER_LICENSE | PERSON, CREDIT_CARD, US_BANK_NUMBER, US_SSN, IBAN_CODE, PHONE_NUMBER, EMAIL_ADDRESS | PERSON, PHONE_NUMBER, EMAIL_ADDRESS, US_SSN, US_PASSPORT, US_DRIVER_LICENSE, CREDIT_CARD, IP_ADDRESS, LOCATION |
| Retention target recorded | 2,555 days (7 years) | 365 days | 1,095 days (3 years) |

## What a template does not do

- **It does not change how long logs are kept.** The retention target is stored with the policy as a record. The retention the system actually applies to request logs comes from the organization's plan (7 days on Community, 30 on Team, 90 on Business, 365 on Enterprise). If your framework needs longer, export the logs yourself.
- **It does not restrict models.** The model allowlist is left empty, or as you had it. Use [the model registry and routing](/core-concepts/provider-routing) to say which models may see which data.
- **It does not set rate limits, data residency or air-gapped mode.** Those are separate: see [rate limiting and budgets](/core-concepts/rate-limiting-and-budgets), [data residency](/guides/data-residency) and [environment flags](/getting-started/environment-flags).
- **The keywords are plain substring matches.** "diagnosis" blocks every request that contains the word, including harmless ones. Test in `log_only` first.
- **Names, phone numbers and similar entities need the optional Presidio detector.** Without it, the built-in detector finds email addresses, US Social Security numbers written with separators, and payment card numbers that pass a checksum.

## Customizing after applying

A template is a starting point. After applying one, change any field through `/api/v1/organizations/current/policy`, for example by switching to `log_only` while you measure false positives. See [Policies & Guardrails](/core-concepts/policies-and-guardrails).
