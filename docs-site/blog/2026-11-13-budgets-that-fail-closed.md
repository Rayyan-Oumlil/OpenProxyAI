---
slug: budgets-that-fail-closed
title: "What should happen at 100% of an LLM budget? Choose it before it happens"
tags: [engineering, product]
description: "Hard stop, degrade to a cheaper model, or alert only: what each does to production traffic at 100% of a spend limit, and exactly what OpenProxyAI does today, read from the code."
---

Every LLM budget has a moment when spend reaches the limit. Most teams set the number and never decide what happens next. So the behavior is whatever the tool does by default, found out during an incident. That is the wrong time to learn it.

There are three honest answers: stop, switch to something cheaper, or only tell a human. Each one fails differently. This post compares them, then says which ones OpenProxyAI supports today, with the status codes and headers it returns.

{/* truncate */}

![Chart of one day of spend rising toward a daily budget line. At 80% a budget.alert webhook fires once. At 100% requests get HTTP 429 until the next midnight UTC.](/img/blog/budgets-that-fail-closed.svg)

## Three policies and how each fails

| Policy | At 100% | How it fails in production |
|---|---|---|
| Hard stop | New requests are refused until the limit resets | The product feature behind the budget goes down. Callers that do not handle the error break, or retry in a loop |
| Degrade | Requests move to a cheaper model | Quality drops silently. Answers may be worse than a clear error, and a cheaper model may not be cleared for the same data |
| Alert only | Nothing is blocked, a human is told | Spend keeps rising until someone reads the alert. A runaway loop gets hours, not seconds |

None of them is correct everywhere. Hard stop is the only one that bounds the money. It fails closed, which means the failure is loud and the cost stops. Alert only fails open.

## What OpenProxyAI does today

OpenProxyAI supports the hard stop, plus an early warning. It does **not** have a degrade-to-cheaper-model policy, and it has no alert-only mode where a budget is a warning that never blocks. We searched the backend for both and found neither. A fallback model exists for provider failures, but it is not triggered by spend.

### Before the call, not during it

The limits are checked at the rate-limit stage, before any provider call. See the [request pipeline](/core-concepts/request-pipeline). When a limit is hit, the response is HTTP 429 with this body shape:

```json
{"error": "rate_limit_exceeded", "limit_type": "budget_daily_usd", "detail": "Daily org budget reached. Resets in 3600 seconds.", "retry_after": 3600}
```

The `limit_type` and the `detail` text tell you which limit fired. The numbers above are an example of the shape, not captured output. The response also carries `Retry-After` and the `X-RateLimit-*` headers, including `X-RateLimit-Budget-Remaining-USD`.

| Limit | `limit_type` | Retry-After |
|---|---|---|
| Requests per minute (organization) | `requests_per_minute` | Seconds to the next minute |
| Tokens per minute (organization) | `tokens_per_minute` | Seconds to the next minute |
| Dollars per day (organization) | `budget_daily_usd` | Seconds to the next midnight UTC |
| Dollars per day (one user) | `user_budget_daily_usd` | Seconds to the next midnight UTC |
| Requests or tokens per minute (one team) | `team_requests_per_minute`, `team_tokens_per_minute` | Seconds to the next minute |
| Dollars per month (one team) | `team_budget_monthly_usd` | Seconds to the start of next month |

Requests and tokens are fixed per-minute windows. The order of checks is the order in the table, then per-model limits if the policy sets them. Rejected requests still count toward the request counter.

### Streams are not cut

Once a call has started, nothing interrupts it. We found no budget check inside the streaming loop. A stream that began under the limit finishes, and its cost is added afterward. One more detail: for streamed chat requests only, there is a pre-flight estimate. It prices the prompt plus `max_tokens` (4,096 if you set none) and refuses with HTTP 402 and `budget_exceeded` if that estimate is more than the remaining budget. An end-to-end test covers the 402. That pre-flight is best effort. If the estimate cannot be computed, for example for a model the pricing table does not know, the request goes ahead and a warning is logged.

### Spend is added after the call

The daily spend counter is a number in Redis, incremented when the call is logged, after the provider answers. Two things follow. Several requests that start together can all pass the check and together cross the line. And the last calls before 100% decide how far past it you land. A hard stop here is a gate on the next request, not a ceiling on every request.

### Unpriced models

If the pricing table cannot price a call, the gateway does not make it free and does not fail the answer. It charges a flat fee, `UNPRICED_CALL_COST_USD`, which defaults to 0.01, and marks the log row `cost_estimated`. So an unpriced model still moves the budget counter, in 1 cent steps. If your real price is higher, the budget will think you spent less than you did. Register prices for the models you use. An abandoned stream is priced from its tokens, not at zero.

### The 80% signal

When an organization's spend for the day reaches 80% of the daily budget, the gateway fires a `budget.alert` webhook, once per day. It only reaches you if you subscribed a webhook to that event. See [webhooks](/guides/webhooks). The dashboard shows something different: a monthly budget burn-down for the organization, with a straight-line projection to month end. It says "On track to exceed the budget" when the projection is over. That is a forecast on a display. It is not the 80% alert, and the monthly organization budget is not enforced by the rate limiter. We found no check for it in the request path.

## A worked example

Suppose an organization has the default daily budget of 50 dollars. At about 40 dollars (80%), the webhook fires once. If a retry loop in one service pushes spend past 50, the next request from anyone in the organization gets a 429 with `limit_type` `budget_daily_usd`. Every caller sees it until 00:00 UTC. A client that honors `Retry-After` waits. A client that ignores it hammers the gateway, and each rejected attempt still counts against the per-minute request limit.

To keep one team from taking the whole day's budget, use the team limits. A team monthly budget (`budget_monthly_usd` on the team) and policy-level `per_team_limits` for requests and tokens per minute apply to requests that carry a team, either through the API key's team or the `x-openproxy-team-id` header. A user can have `budget_daily_usd` too.

## Recommendations by use case

| Use case | Choose | Why |
|---|---|---|
| Internal chat, many users | Hard stop plus per-user daily budgets | One heavy user should not use the organization's day |
| Customer-facing feature | Hard stop at the gateway, and a clear error in your app | A degraded answer is a quality risk you did not review |
| Batch and eval jobs | Per-job cost cap | See [the batch API post](/blog/when-to-use-the-batch-api). The job ends instead of draining the shared budget |
| Regulated data | Hard stop | A cheaper model may not be cleared for that data class |
| Early rollout, unknown usage | Hard stop with a generous limit, and the 80% webhook | You learn the real rate without an open-ended bill |

## What this does not do

- **No degrade policy and no alert-only mode.** The only action at the limit is to refuse.
- **The daily budget is one value for the whole deployment.** It comes from `DEFAULT_BUDGET_DAILY_USD` (default 50) and is counted per organization. There is no per-team daily dollar budget in the code. The [rate limiting page](/core-concepts/rate-limiting-and-budgets) describes budgets as per team and as 402 responses. In the code they are 429 responses, and the 402 appears only in the streaming pre-flight.
- **The 80% threshold is fixed** in the call. It is not a setting.
- **The monthly organization budget and a user's monthly budget are stored but not enforced.** The monthly organization budget feeds the dashboard. We found no enforcement for a user's `budget_monthly_usd`.
- **No refunds for a stream that crosses the limit.** It finishes and is billed.
- **Fixed windows.** A burst at the end of one minute and the start of the next can pass twice the per-minute figure.

## What to do now

- Decide your 100% behavior per use case before launch. Write it down.
- Make clients treat 429 as retry after `Retry-After`, with a cap on attempts.
- Subscribe a webhook to `budget.alert`.
- Register prices for every model you use, so the 1 cent estimate is rare.
- Set user and team limits for the services most likely to loop.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

Needs Docker, no provider key. Console at http://localhost:5173.

## Sources

- [Rate limiting and budgets](/core-concepts/rate-limiting-and-budgets): the limits at a glance. Where it differs from the code, the code is what this post follows.
- [Errors and status codes](/api-reference/errors-and-status-codes): 402 and 429.
- [Webhooks](/guides/webhooks): subscribing to `budget.alert`.
- [Users API](/api-reference/users): the user budget fields.
- [Request pipeline](/core-concepts/request-pipeline): where the limit check sits.

These statements are based on the OpenProxyAI source code, tests and docs as read on November 13, 2026. The 429 body above shows the shape from the code, not captured output.
