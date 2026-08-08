---
title: Managing Policies
description: Configure guardrails, switch enforce/log-only mode, and apply compliance templates from the console.
---

# Managing Policies

The Policies screen in the admin console is a UI over the same configuration reachable via `/api/v1/organizations/current/policy` — see [Policies & Guardrails](/core-concepts/policies-and-guardrails) for what each policy does.

## Toggling enforce / log-only

Each policy can be switched between `enforce` and `log-only` independently. A common pattern: turn a new policy on in `log-only` mode first, watch its hit rate in the analytics dashboard for false positives, then switch it to `enforce` once you're confident in it.

## Applying a compliance template

Apply one of the built-in [compliance templates](/guides/compliance-templates) (Healthcare, Finance, Government) as a starting point, then adjust individual policies from there — applying a template merges into your existing configuration rather than replacing it outright.

## Reviewing policy activity

The policy activity table shows hit counts per policy over the selected time range, backed by `/api/v1/analytics/policy` — useful for spotting a policy that's either too aggressive (high log-only hit rate on legitimate traffic) or one that's never firing (worth double-checking it's actually configured correctly).
