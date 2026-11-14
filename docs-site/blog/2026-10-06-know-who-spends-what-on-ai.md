---
slug: know-who-spends-what-on-ai
title: "Know who spends what on AI: team budgets, user limits and alerts"
tags: [product, engineering]
description: "Attribute every model call to a team, user and key, set budgets that stop overspend, and get a webhook at 80 percent of the daily budget. A practical guide for finance and platform leads."
---

The first AI invoice usually arrives as one number. Finance asks which team caused it. Engineering says it is hard to tell, because six services share two provider keys. A gateway fixes this at the source: every request already passes through one place, so every request can carry a team, a user and a key. This post shows how to turn that into budgets, alerts and a spend report you can read in a meeting.

{/* truncate */}

![Requests tagged with team, user and key flow through budget checks, then to dashboards and an 80 percent webhook alert](/img/blog/know-who-spends-what-on-ai.svg)

## Attribution comes first

You cannot budget what you cannot attribute. OpenProxyAI gives you three ways to say who a request belongs to, and they combine.

- **Give each service its own API key, tied to a team.** Usage on that key counts toward that team automatically. No code changes in the application.
- **Send a team header** on requests when one key serves several teams.
- **Add labels.** An optional header carries up to ten small labels, such as the application or feature name. They are recorded on the request log and you can filter by them.

Every request is also tied to the key and the user that made it. So the same call can be read by team, by person, by key and by model.

## Budgets that act, not just report

A dashboard tells you what happened. A budget changes what happens next. OpenProxyAI checks limits before any provider call.

| Scope | What you can set |
|---|---|
| Organization | Requests per minute, tokens per minute, dollars per day |
| Team | Requests and tokens per minute, dollars per month |
| User | Dollars per day, set by an admin |

When a request reaches a limit it is refused with a 429, a Retry-After header and a body that names which limit was hit, so your application can tell a rate limit from a budget. Streaming requests are checked up front against what is left for the day, and a request that would not fit is refused with a 402. Daily budgets reset at midnight UTC.

## An alert before the wall

A hard stop at 100 percent is the last line of defense. You also want a warning before it. When the day's spend reaches 80 percent of the organization's daily budget, OpenProxyAI sends a budget alert webhook to the HTTPS endpoint you configured. The payload carries the spend, the budget and the percent used. Point it at chat, paging or a ticket queue.

Deliveries are signed so your receiver can check they are genuine. A failed delivery never slows the request that triggered it, and failed deliveries are retried automatically. You can view delivery history and retry one by hand.

## Reading the spend

The admin console dashboard shows spend for the last 7, 30 or 90 days, with tables for cost by team, by user, by API key and by model. A team filter narrows the whole page to one team. A monthly burn-down chart shows cumulative spend against the monthly budget with a projection to month end, and flags when you are on track to exceed it.

When the dashboard is not enough, admins can ask their own questions through a structured analytics query, for example total spend and 95th percentile latency grouped by model, provider, user or day. It is read-only, and every query is recorded in the admin audit log. For finance, a compliance export gives a file for a date range, scoped to a team if you like.

### A worked scenario (hypothetical)

A company has three teams on one gateway: support, growth and data science.

1. Each service gets its own key, tied to its team. Growth also sets a label for the campaign tool.
2. Finance sets a monthly dollar budget on each team. Platform sets a daily organization budget as a backstop.
3. A platform lead sets a daily limit for one new hire's experimentation.
4. The alert webhook posts to the platform channel at 80 percent of the daily budget. On Tuesday it fires at midday. The dashboard shows data science's batch job as the top team and one key as the top key.
5. The team fixes the job. At month end, the report to finance is a screenshot of the cost by team table plus a compliance export.

## What to do now

- Replace shared keys with one key per service, each tied to a team.
- Pick the label vocabulary: application, feature, environment. Keep it short.
- Set team monthly budgets and an organization daily budget. Start generous, then tighten.
- Configure the webhook and test that the alert lands where someone will see it.
- Teach applications to read the limit named in a 429 and to back off when it is a budget.
- Put the cost by team table on the agenda of your monthly review.

## Good to know

Spend is added after a call finishes, so calls already in flight when a budget is reached still complete. Models without a known price are charged a flat estimate and marked as an estimate, so register prices for the models you use. The 80 percent alert tracks the organization's daily budget.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

Needs Docker and no provider key. The console is at http://localhost:5173. Star the repo or open an issue if your finance team needs a view we do not have.

## Sources

- Product docs: [Rate limiting and budgets](/core-concepts/rate-limiting-and-budgets), [Authentication](/getting-started/authentication), [Webhooks](/guides/webhooks), [Audit logging](/security/audit-logging), [Errors and status codes](/api-reference/errors-and-status-codes), [API keys](/api-reference/keys), [Users](/api-reference/organizations-teams-users).

These statements are based on OpenProxyAI's behavior at the post date.
