---
title: Compliance templates
description: "Three starting guardrail configurations for healthcare, finance and government: how to apply them, exactly what each one sets, and what none of them does."
---

# Compliance templates

OpenProxyAI ships three policy templates for regulated environments: `healthcare_hipaa`, `finance_pci` and `government_fedramp`. Each one fills in the guardrail fields of your organization policy in a single call, so you start from a sensible configuration instead of an empty one. After reading this page you can apply a template, test it without blocking anyone, and know what it leaves for you to do.

**Templates are configurations, not certifications.** They are policy settings that you apply and enforce yourself. Applying one does not make a deployment compliant with HIPAA, PCI DSS, FedRAMP or anything else, and OpenProxyAI makes no claim that it holds any of those certifications or authorizations. Your own compliance program, your agreements (for example a Business Associate Agreement) and your own audit still apply.

## How templates work

The organization has one policy with an `enforcement_mode` of `off`, `log_only` or `enforce` (see [Policies and guardrails](/core-concepts/policies-and-guardrails)). A template is a bundle of values for that single policy, not a separate named policy. When a request violates a rule in `enforce` mode, the gateway refuses it with HTTP 446. A request containing PII is blocked in that case, not silently redacted.

Every template sets the same switches and differs only in its keyword list, PII entity list and recorded retention target:

- `enforcement_mode` set to `enforce`
- blocked keywords (case-insensitive substring match)
- PII detection on, with an entity list
- prompt-injection detection on
- response guardrails on, with PII in responses redacted

## Applying a template

List what is available, then apply one. Only organization admins can apply a template.

```bash
curl https://gateway.your-company.com/api/v1/organizations/current/policy/templates \
  -H "Authorization: Bearer $ADMIN_JWT"

curl -X POST https://gateway.your-company.com/api/v1/organizations/current/policy/apply-template \
  -H "Authorization: Bearer $ADMIN_JWT" -H "Content-Type: application/json" \
  -d '{"template": "healthcare_hipaa"}'
```

The list returns, for each template, its `name`, a `description` and a `configures` array describing what it sets. The apply call returns the resulting policy.

| Condition | Result |
|---|---|
| Caller is not an admin | 403 |
| Unknown template name | 400 |
| Plan does not include PII detection (Community) | Refused by the plan check |
| Success | Policy replaced, change written to the [admin audit log](/security/audit-logging) as `apply_compliance_template` |

### What applying replaces and keeps

Applying a template **replaces** these settings: enforcement mode, blocked keywords, PII detection and its entity list, prompt-injection detection, response guardrails and response PII redaction. The keyword list is replaced, not merged, so any keywords you added earlier are gone.

It **keeps** your model allowlist, rate limits, MCP tool lists, routing and every other setting.

## Running a template in log-only first

Applying a template turns on `enforce` immediately. That is subtle because the first request after the call can already be refused. Two safe ways to measure before blocking real traffic:

1. Apply the template in a staging organization first and replay representative traffic.
2. In production, apply and switch to `log_only` straight away, ideally when traffic is low:

```bash
curl -X PATCH https://gateway.your-company.com/api/v1/organizations/current/policy \
  -H "Authorization: Bearer $ADMIN_JWT" -H "Content-Type: application/json" \
  -d '{"enforcement_mode": "log_only"}'
```

In `log_only` mode a hit is recorded in the audit log and analytics and the request goes through. Review the hits in the console or with `GET /api/v1/analytics/policy`, remove or adjust keywords that fire on harmless text, then return to enforcement:

```bash
curl -X PATCH https://gateway.your-company.com/api/v1/organizations/current/policy \
  -H "Authorization: Bearer $ADMIN_JWT" -H "Content-Type: application/json" \
  -d '{"enforcement_mode": "enforce"}'
```

You can also preview a change against recent traffic before saving it; see [Evaluating changes](/admin-console/evaluating-changes).

## The three templates side by side

| | Healthcare (`healthcare_hipaa`) | Finance (`finance_pci`) | Government (`government_fedramp`) |
|---|---|---|---|
| Blocked keywords | diagnosis, patient name, medical record, prescription, treatment plan | account number, routing number, wire transfer, swift code, trading strategy, insider | classified, top secret, secret//noforn, controlled unclassified, fouo |
| PII entities | PERSON, PHONE_NUMBER, EMAIL_ADDRESS, US_SSN, CREDIT_CARD, DATE_OF_BIRTH, MEDICAL_LICENSE, US_DRIVER_LICENSE | PERSON, CREDIT_CARD, US_BANK_NUMBER, US_SSN, IBAN_CODE, PHONE_NUMBER, EMAIL_ADDRESS | PERSON, PHONE_NUMBER, EMAIL_ADDRESS, US_SSN, US_PASSPORT, US_DRIVER_LICENSE, CREDIT_CARD, IP_ADDRESS, LOCATION |
| Retention target recorded | 2,555 days (7 years) | 365 days | 1,095 days (3 years) |

The recorded retention target is a note stored with the policy. It does not change how long logs are kept (see below).

## Healthcare (`healthcare_hipaa`)

For organizations that handle protected health information (PHI).

**What it sets.** The healthcare keywords and entity list in the table above, plus the common switches. DATE_OF_BIRTH and MEDICAL_LICENSE are the entities specific to this template.

**What it does not do.** It does not provide or replace a Business Associate Agreement with your model providers, and it does not stop PHI that does not match a keyword or entity. A free-text clinical note without the word "diagnosis" and without a detectable name passes.

**Log-only first.** Keywords such as "diagnosis" and "prescription" are plain substring matches and will fire on harmless text, for example an engineer asking how to parse a field named `diagnosis`. Measure these in `log_only` before enforcing.

```bash
curl -X POST https://gateway.your-company.com/api/v1/organizations/current/policy/apply-template \
  -H "Authorization: Bearer $ADMIN_JWT" -H "Content-Type: application/json" \
  -d '{"template": "healthcare_hipaa"}'
```

## Finance (`finance_pci`)

For organizations that handle payment and cardholder data, or that want to keep banking details and trading material out of prompts.

**What it sets.** The finance keywords and entity list above. Payment card numbers that pass a checksum are found by the built-in detector, so a request containing one is blocked in `enforce` mode even without the optional detector.

**What it does not do.** It does not set rate limits and does not add transaction-level logging beyond the standard request log. It is not a PCI DSS assessment.

**Log-only first.** The keyword "insider" and the phrase "wire transfer" also appear in ordinary business writing. Expect false positives from internal finance and compliance teams.

```bash
curl -X POST https://gateway.your-company.com/api/v1/organizations/current/policy/apply-template \
  -H "Authorization: Bearer $ADMIN_JWT" -H "Content-Type: application/json" \
  -d '{"template": "finance_pci"}'
```

## Government (`government_fedramp`)

For government and public-sector organizations that want classification markings and identity data kept out of prompts.

**What it sets.** The classification-marking keywords and the wider entity list above, which adds US_PASSPORT, IP_ADDRESS and LOCATION.

**What it does not do.** It does not turn on air-gapped mode or data residency, and it does not assign US-region provider keys. Set those yourself: see `AIRGAP_MODE` in [Environment flags](/getting-started/environment-flags) and [Data residency](/security/data-residency). It is not a FedRAMP authorization.

**Log-only first.** "classified" is a common English word (classified ads, classified information in a news summary). LOCATION and IP_ADDRESS can fire on network documentation. Measure both before enforcing.

```bash
curl -X POST https://gateway.your-company.com/api/v1/organizations/current/policy/apply-template \
  -H "Authorization: Bearer $ADMIN_JWT" -H "Content-Type: application/json" \
  -d '{"template": "government_fedramp"}'
```

## What no template does

- **It does not change how long logs are kept.** The retention that applies to request logs comes from the organization's plan: 7 days on Community, 30 on Team, 90 on Business and 365 on Enterprise. If your framework needs longer, export the logs yourself. See [Audit logging](/security/audit-logging).
- **It does not restrict models.** The model allowlist is left as you had it. Use [provider routing](/core-concepts/provider-routing) to decide which models may see which data.
- **It does not set rate limits, data residency or air-gapped mode.** See [Rate limiting and budgets](/core-concepts/rate-limiting-and-budgets), [Data residency](/security/data-residency) and [Environment flags](/getting-started/environment-flags).
- **Keywords are plain substring matches.** A blocked word blocks every request that contains it, including harmless ones.
- **Most entities need the optional NLP detector.** Without it, the built-in detector finds email addresses, US Social Security numbers written with separators, and payment card numbers that pass a checksum. Names, phone numbers and the other entities need the optional detector to be installed.

## Customizing after applying

A template is a starting point. After applying one, change any field with `PATCH /api/v1/organizations/current/policy`, for example to add your own keywords or to switch to `log_only` while you measure false positives. Re-applying a template later overwrites those edits.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Apply returns 403 | The caller is not an admin | Use an admin token |
| Apply returns 400 | Template name is misspelled | Use `healthcare_hipaa`, `finance_pci` or `government_fedramp` |
| Apply is refused on Community | PII detection is not in the plan | Upgrade the plan |
| Harmless requests return 446 | A keyword matched as a substring | Switch to `log_only`, find the hits, remove the keyword |
| Names or phone numbers are not detected | The optional NLP detector is not installed | Install it, or rely on the built-in email, SSN and card checks |
| Your custom keywords disappeared | Applying a template replaces the keyword list | Add them again with a policy update |
| Logs older than the plan window are missing | Retention follows the plan, not the template's target | Export logs before they age out |

## Next steps

- [Policies and guardrails](/core-concepts/policies-and-guardrails) for every policy field
- [Audit logging](/security/audit-logging) for retention and exports
- [Trust center](/security/trust-center) for the overall security posture
