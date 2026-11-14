---
slug: budgets-that-fail-closed
image: /img/blog/og/budgets-that-fail-closed.png
title: "What should happen at 100% of an LLM budget? Choose it before it happens"
tags: [engineering, product]
description: "Hard stop, degrade to a cheaper model, or alert only: what each does to production traffic at 100% of a spend limit, and how OpenProxyAI gives you a clear stop with an early warning."
---

Every LLM budget has a moment when spend reaches the limit. Most teams set the number and never decide what happens next. So the behavior is whatever the tool does by default, found out during an incident. That is the wrong time to learn it.

There are three honest answers: stop, switch to something cheaper, or only tell a human. Each one fails differently. This post compares them, then shows how OpenProxyAI gives you a hard stop with an early warning.

{/* truncate */}

![Chart of one day of spend rising toward a daily budget line. At 80% a budget.alert webhook fires once. At 100% requests get HTTP 429 until the next midnight UTC.](/img/blog/budgets-that-fail-closed.svg)

## Three policies and how each fails

| Policy | At 100% | How it fails in production |
|---|---|---|
| Hard stop | New requests are refused until the limit resets | The product feature behind the budget goes down. Callers that do not handle the error break, or retry in a loop |
| Degrade | Requests move to a cheaper model | Quality drops silently. Answers may be worse than a clear error, and a cheaper model may not be cleared for the same data |
| Alert only | Nothing is blocked, a human is told | Spend keeps rising until someone reads the alert. A runaway loop gets hours, not seconds |

None of them is correct everywhere. Hard stop is the only one that bounds the money. It fails closed, which means the failure is loud and the cost stops. Alert only fails open.

## What OpenProxyAI does

OpenProxyAI gives you the hard stop, plus an early warning at 80%. Limits are checked before any provider call (see the [request pipeline](/core-concepts/request-pipeline)), so a refused request costs nothing. When a limit is hit, the response is HTTP 429 with a body that names the limit and says when it resets, plus `Retry-After` and the `X-RateLimit-*` headers, including the remaining budget.

| Limit | Resets |
|---|---|
| Requests per minute (organization) | Next minute |
| Tokens per minute (organization) | Next minute |
| Dollars per day (organization) | Next midnight UTC |
| Dollars per day (one user) | Next midnight UTC |
| Requests or tokens per minute (one team) | Next minute |
| Dollars per month (one team) | Start of next month |

For streamed chat requests there is also a pre-flight estimate. It prices the prompt plus the requested maximum output and refuses with HTTP 402 and `budget_exceeded` if that estimate is more than the remaining budget. A stream that starts under the limit is never cut in the middle.

### The 80% signal

When an organization's spend for the day reaches 80% of its daily budget, the gateway fires a `budget.alert` webhook, once per day. Subscribe a webhook to that event and the right person hears about it while there is still room. See [webhooks](/guides/webhooks).

## A worked example

Suppose an organization has a daily budget. At 80%, the webhook fires once. If a retry loop in one service pushes spend to the limit, the next request gets a 429 naming the daily budget, with the number of seconds until reset. A client that honors `Retry-After` waits. Every caller sees the same clear answer until 00:00 UTC.

To keep one team from taking the whole day's budget, use the team limits. A team monthly budget and policy-level team limits for requests and tokens per minute apply to requests that carry a team, either through the API key's team or the `x-openproxy-team-id` header. A user can have a daily budget too.

## Recommendations by use case

| Use case | Choose | Why |
|---|---|---|
| Internal chat, many users | Hard stop plus per-user daily budgets | One heavy user should not use the organization's day |
| Customer-facing feature | Hard stop at the gateway, and a clear error in your app | A degraded answer is a quality risk you did not review |
| Batch and eval jobs | Per-job cost cap | See [the batch API post](/blog/when-to-use-the-batch-api). The job ends instead of draining the shared budget |
| Regulated data | Hard stop | A cheaper model may not be cleared for that data class |
| Early rollout, unknown usage | Hard stop with a generous limit, and the 80% webhook | You learn the real rate without an open-ended bill |

## What to do now

- Decide your 100% behavior per use case before launch. Write it down.
- Make clients treat 429 as retry after `Retry-After`, with a cap on attempts.
- Subscribe a webhook to `budget.alert`.
- Register prices for the models you use, so cost tracking is exact.
- Set user and team limits for the services most likely to loop.

Good to know: spend is added when a call finishes, so requests already in flight when you reach the limit complete normally. Set the limit with that small margin in mind.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

Needs Docker, no provider key. Console at http://localhost:5173. Star the repo if you want to follow along, or open an issue to tell us which policy you need next.

## Sources

- [Rate limiting and budgets](/core-concepts/rate-limiting-and-budgets): the limits at a glance.
- [Errors and status codes](/api-reference/errors-and-status-codes): 402 and 429.
- [Webhooks](/guides/webhooks): subscribing to `budget.alert`.
- [Users API](/api-reference/organizations-teams-users): the user budget fields.
- [Request pipeline](/core-concepts/request-pipeline): where the limit check sits.

These statements are based on OpenProxyAI's behavior at the post date.
