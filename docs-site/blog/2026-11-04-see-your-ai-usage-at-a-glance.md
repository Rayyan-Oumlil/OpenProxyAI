---
slug: see-your-ai-usage-at-a-glance
image: /img/blog/og/see-your-ai-usage-at-a-glance.png
title: "See your AI usage at a glance: spend by model, team, key and user"
tags: [product]
description: "The OpenProxyAI dashboard answers the questions finance and platform leads ask every week: how much did we spend, on which models, for which teams, and are we on budget."
---

Every team that adopts AI hits the same moment. The first invoice arrives and nobody can say which team, app or model caused it. Provider dashboards show totals per account, not per team. Spreadsheets get built by hand, and they are out of date by Friday. The OpenProxyAI dashboard is built for this moment: every request already passes through the gateway, so the gateway can show usage by model, team, key and user without any extra instrumentation.

{/* truncate */}

![The dashboard layout from top to bottom: headline numbers, reliability and governance numbers, budget burn-down, daily trend, top models, and cost by team, key and user.](/img/blog/see-your-ai-usage-at-a-glance.svg)

## The problem: spend without owners

AI cost has three properties that make it hard to manage. It is variable, because one loop or one long prompt can multiply a bill. It is shared, because many apps use the same provider account. And it is invisible until the invoice, because tokens are not something a team sees while building.

To manage it you need to answer four questions quickly.

1. How much, and is it going up?
2. Which models drive the cost?
3. Which team, key or person is behind it?
4. Are we on track against the monthly budget?

## What the dashboard shows

The dashboard is the first page of the admin console. You choose a time range of 7, 30 or 90 days, and admins can narrow everything to one team.

| Section | What you see |
|---|---|
| Headline numbers | Requests, cost, tokens and average latency, with the 95th percentile latency alongside. Each shows a small trend line and how it compares with the previous period of the same length. |
| Reliability and governance | Success rate with the number of failed requests, how many requests a policy blocked before they reached a provider, how many a policy flagged but allowed, and the cache hit rate. |
| Budget burn-down | Spend so far this month against the organization's monthly budget, with a projection toward the end of the month. |
| Daily trend | Requests and cost per day over the chosen range. |
| Top models by cost | Which models take the largest share of spend. |
| Cost by team | Requests and cost for each team. |
| Cost by API key | Requests, tokens and cost for each key, by name and key prefix. |
| Cost by user | Requests, tokens and cost for each person, by email. |

The cost by team, key and user tables are shown to admins. A button on the page downloads a compliance report as a spreadsheet file for the chosen range.

If you have not set a monthly budget, the burn-down says so and points you to the organization settings. If there is no traffic yet, the page tells you to send some through the gateway.

## Why this works without extra setup

Each request is recorded when it passes through, with its model, tokens, cost, team, key, user, status and policy outcome. The dashboard reads those records. There is no agent to install in your applications and no tags to remember to add. Team attribution comes from the API key, which can be tied to a team, or from a team header on the request.

Cost is calculated from the prices registered for each model. A model with no registered price is charged a small flat estimate and marked as an estimate, so register prices for the models you use. The post on [answers from models without a price](/blog/answers-from-models-without-a-price) explains the details.

## A worked example

Finance asks on Monday why spend doubled last week. A platform lead opens the dashboard.

1. Sets the range to 7 days. The comparison shows cost is up against the previous week.
2. Looks at top models by cost. One expensive model now takes most of the spend.
3. Opens cost by team. One team accounts for the jump.
4. Opens cost by API key. A single key from a batch job is responsible.
5. Checks the daily trend. The increase began on Wednesday, the day the job was deployed.

In about five minutes there is an answer with a named team, key and day. The fix might be a cheaper model for that job, a team budget, or moving it to the [batch API](/blog/when-to-use-the-batch-api). Next to the dashboard, the console has request logs for single requests, and an analytics query page where admins can ask their own questions of the request records through a structured, read-only form. Every query there is audited.

## Turn insight into limits

Seeing spend is the first step. The gateway can also act on it.

- Daily budgets for the organization and for each user, and monthly budgets per team.
- Request and token rate limits.
- A webhook when daily spend reaches 80 percent of the organization budget.

When a limit is reached, the request gets a clear HTTP 429 that names which limit applied. The post on [budgets that fail closed](/blog/budgets-that-fail-closed) covers the behavior in detail.

## What to do now

- Tie each application's API key to a team, so cost lands on someone.
- Register prices for every model you use.
- Set a monthly budget for the organization so the burn-down has a target.
- Set a team budget for the one or two teams most likely to loop.
- Subscribe a webhook to the 80 percent alert.
- Review the dashboard weekly and use the previous-period comparison to spot changes early.

## Good to know

Spend is added after a call finishes, so requests still in flight when a limit is reached can complete. The monthly budget on the dashboard applies to the whole organization, so it is hidden when you filter to a single team. Admin-only tables are not shown to other roles.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

Needs Docker, no provider key. Console at http://localhost:5173. Star the repo or open an issue with the chart or table you wish the dashboard had.

## Sources

- [Admin console overview](/admin-console/overview): the pages of the console.
- [Rate limiting and budgets](/core-concepts/rate-limiting-and-budgets): limits, alerts and monitoring usage.
- [Managing teams](/admin-console/managing-your-organization): team budgets and attribution.
- [Authentication](/getting-started/authentication): API keys tied to a team.
- [Audit logging](/security/audit-logging): the records behind the numbers.

These statements are based on the OpenProxyAI console and docs as read for this post, at its date of November 4, 2026.
