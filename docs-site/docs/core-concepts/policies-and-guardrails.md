---
title: Policies & Guardrails
description: Configure PII redaction, topic guarding, prompt-injection detection, and model allowlists.
---

# Policies & Guardrails

Policies are named checks that run against every request at the policy stage of the pipeline (see [Request Pipeline](/core-concepts/request-pipeline)). Each policy runs in either `enforce` or `log-only` mode.

## Built-in policies

| Policy | What it does |
|---|---|
| `pii_redact` | Redacts personally identifiable information (emails, phone numbers, etc.) from the outgoing request before it reaches a provider. |
| `secrets_scan` | Scans the response for accidentally-echoed secrets (API keys, tokens) and blocks or strips them. |
| `topic_guard` | Blocks requests that match disallowed topic categories — for example legal, medical, or self-harm content, configurable per org. |
| `injection` | Scores the request for prompt-injection patterns; requests above the configured threshold are blocked. |
| `model_allow` | Restricts which models a team is permitted to call — useful for keeping regulated data on a specific approved model. |
| `jailbreak_lm` | A lightweight classifier that flags jailbreak attempts. Ships in `log-only` mode by default. |

## Enforce vs. log-only

- **`enforce`** — a policy hit blocks the request and returns HTTP `446`.
- **`log-only`** — a policy hit is recorded (visible in the audit log and analytics) but the request proceeds. Useful for evaluating a new policy's false-positive rate before turning it on in enforce mode.

## Selecting policies per request

Policies are applied via the `x-op-policy` header, comma-separated:

```
x-op-policy: pii_redact,topic_guard
```

If the header is omitted, the team's configured default policy set applies.

## Setting org-wide defaults

Default policies, their mode, and their thresholds are configured per organization at `/api/v1/organizations/current/policy`, and can be seeded from a starting template — see [Compliance Templates](/guides/compliance-templates) for the Healthcare, Finance, and Government presets.

## Viewing policy activity

Policy hits are queryable via `/api/v1/analytics/policy` and exportable via `/api/v1/analytics/policy/export` for compliance reporting.
