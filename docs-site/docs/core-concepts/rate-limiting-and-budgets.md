---
title: Rate Limiting & Budgets
description: Requests/min, tokens/min, and dollars/day limits, enforced per team.
---

# Rate Limiting & Budgets

OpenProxyAI enforces three limits together at the rate-limit stage of the pipeline, before any policy check or provider call happens:

| Limit | Unit |
|---|---|
| Requests | per minute |
| Tokens | per minute |
| Spend | per day (dollars) |

A request that would exceed any one of the three is rejected with `402` (budget) or `429` (rate/token limit) — see [Errors & Status Codes](/api-reference/errors-and-status-codes).

## Team-scoped budgets

Limits are set per team. Requests are attributed to a team either via the `x-op-team` header or by using an API key that's already tied to a `team_id` — see [Authentication](/getting-started/authentication).

## Daily reset

Dollar budgets reset at `00:00 UTC`. A team that exhausts its daily budget resumes normal service at the next reset, or can be granted a manual override from the admin console.

## Monitoring usage

Current spend against budget, per team, is visible in the admin console and via `/api/v1/analytics/overview`. Budgets approaching their limit are flagged in the dashboard before they're hit.
