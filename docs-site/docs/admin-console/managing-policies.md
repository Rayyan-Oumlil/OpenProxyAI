---
title: Managing Policies
description: Change the organization policy, switch between log-only and enforce, and apply a compliance template from the console.
---

# Managing Policies

The Policy screen in the admin console is a view over the same configuration at `/api/v1/organizations/current/policy`. See [Policies & Guardrails](/core-concepts/policies-and-guardrails) for what each setting does.

## Switching between log-only and enforce

The organization has one enforcement mode: `off`, `log_only` or `enforce`. It applies to the whole policy, not to individual checks. A common pattern is to turn a new rule on in `log_only`, watch its hit rate in the analytics dashboard for false positives, then switch to `enforce` once you trust it.

## Applying a compliance template

Apply one of the [compliance templates](/guides/compliance-templates) (Healthcare, Finance, Government) as a starting point. A template **replaces** the guardrail settings (mode, blocked keywords, PII and injection detection, response guardrails). Your model allowlist, rate limits, MCP tool lists and other settings are kept. Review the result afterward: the keyword list in particular is the template's, not yours.

## Reviewing policy activity

The policy activity table shows hit counts over the selected time range, backed by `/api/v1/analytics/policy`. It helps you spot a rule that is too aggressive (many log-only hits on legitimate traffic) or one that never fires (worth checking that it is configured as you meant).
