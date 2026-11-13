---
title: Rate Limiting & Budgets
description: Requests and tokens per minute, dollars per day and per month, at the organization, user and team level, and what a request gets back when one is reached.
---

# Rate Limiting & Budgets

OpenProxyAI checks limits at the rate-limit stage of the pipeline, before any provider call. Several limits apply together; the first one reached refuses the request.

## What is limited, and where it is set

| Limit | Scope | Where it is set |
|---|---|---|
| Requests per minute | Organization | `DEFAULT_RATE_LIMIT_RPM` (default 60) |
| Tokens per minute | Organization | `DEFAULT_RATE_LIMIT_TPM` (default 100000) |
| Dollars per day | Organization | `DEFAULT_BUDGET_DAILY_USD` (default 50) |
| Dollars per day | One user | `budget_daily_usd` on the user ([Users API](/api-reference/users)) |
| Requests and tokens per minute | One team | `per_team_limits` in the organization policy, for example `{"rpm": 60, "tpm": 50000}` |
| Dollars per month | One team | `budget_monthly_usd` on the team |

The three organization settings are environment settings for the deployment, listed in [Environment Flags](/getting-started/environment-flags) terms: the operator sets them, and they are the same for every organization on that deployment. The policy can also set limits per model. A user's `budget_monthly_usd` is stored on the user but is not enforced on requests.

The checks run in this order: organization requests per minute, organization tokens per minute, organization daily budget, user daily budget, team requests and tokens per minute, team monthly budget, then per-model limits when the policy sets them. Every request counts toward the request counter, including ones that are then refused.

## What a refused request gets back

A request that reaches a limit is refused with HTTP `429`, a `Retry-After` header and a body that names the limit:

```json
{"error": "rate_limit_exceeded", "limit_type": "requests_per_minute", "detail": "...", "retry_after": 12}
```

Budget limits use the same `429` response, with a `limit_type` such as `budget_daily_usd`, `user_budget_daily_usd` or `team_budget_monthly_usd`. Match on `limit_type` rather than only on the status code. Rate limits are per minute, counted in fixed windows.

One check answers `402` instead. A **streamed** request is checked before it starts: the gateway estimates its cost from the prompt plus `max_tokens` (4096 if you did not set one), and if that is more than the organization or user has left for the day, it answers `402` with `budget_exceeded`. See [Errors & Status Codes](/api-reference/errors-and-status-codes).

## How spend is counted

Spend is added after a call finishes, so requests already in flight when a budget is reached still complete. The overshoot is bounded by what runs at the same moment, not by zero. A model the gateway cannot price is charged a flat fee (`UNPRICED_CALL_COST_USD`, default 0.01) and marked as an estimate. See [Rerank, images, audio and Responses](/api-reference/more-endpoints).

## Team attribution

A request counts toward a team when its API key is tied to a `team_id`, or when it carries an `x-openproxy-team-id` header with the team's UUID (a header that is not a valid UUID is refused with 400). See [Authentication](/getting-started/authentication).

## Daily reset

Dollar budgets for the day reset at `00:00 UTC`.

## Monitoring usage

Current spend is visible in the admin console and through `/api/v1/analytics/overview`. The dashboard shows a monthly burn-down with a projection to month end. When daily spend reaches 80% of the organization budget, a `budget.alert` [webhook](/guides/webhooks) is sent.
