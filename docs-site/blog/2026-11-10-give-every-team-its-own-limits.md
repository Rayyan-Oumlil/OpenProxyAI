---
slug: give-every-team-its-own-limits
title: "Give every team its own AI budget and rate limits, so one team cannot drain the rest"
tags: [product, engineering]
description: "Organizations, teams and keys let you cap spend and traffic where it belongs. Set a monthly budget per team, rate ceilings per team, and see who used what."
---

One shared key, one shared budget, and one runaway script can leave every other team with a wall of errors on a Tuesday afternoon. The fix is not more monitoring. It is giving each team its own limits, so a problem stays where it started. OpenProxyAI does this with organizations, teams and keys.

{/* truncate */}

![An organization box with a daily budget and per-minute limits sits above three team boxes: support, data and an intern sandbox. Each team has its own monthly budget and its own rate counters. A call must pass the organization and its team.](/img/blog/give-every-team-its-own-limits.svg)

## The problem

Shared limits fail in two ways. Either they are so tight that every team trips over them, or so loose that one team can spend the whole budget. Finance cannot tell which team drove the bill. Platform engineers cannot tell whose traffic caused a spike. And an experiment by an intern shares a ceiling with your production support bot.

## The layers

OpenProxyAI checks several limits together on every request. The first one reached refuses the request.

| Layer | What it limits |
|---|---|
| Organization | Requests per minute, tokens per minute and a daily dollar budget for the whole organization. |
| User | A daily dollar budget for one user. Give each application its own service user to get a per-app ceiling. |
| Team | A monthly dollar budget for the team, and requests and tokens per minute counted separately for each team. |
| Model | Optional per-model rate limits in the policy. |

A request must pass every layer that applies. So a team can use only what its own limits allow, and all teams together stay inside the organization's limits.

## How requests get attributed to a team

Two ways, both simple:

- **Tie the key to a team.** When you create an application key, give it a team. Every request with that key counts against the team, with no extra work in the app.
- **Send a header.** A request can carry the team's id in a documented header, for example when one service calls on behalf of several teams. The caller must actually be a member of that team, or the request is refused.

Admins create teams in the console, set a monthly budget, and add members. New people can be invited by email and land directly on the team.

## What a team sees when it hits a limit

A refused request gets HTTP 429 with a `Retry-After` header and a body that names the limit that was reached, for example a team monthly budget or a team requests-per-minute limit. Applications can match on that name and tell the user what happened. A team that spent its monthly budget does not affect any other team, because the budget is counted per team.

## Seeing who used what

The console dashboard shows spend broken down by team, user and key, with a team filter on the trend. The same data is available through the analytics API. A `budget.alert` webhook fires when daily spend reaches 80% of the organization budget, so you hear about it before the limit. Requests can also carry labels, which are recorded on the log for chargebacks by project or department.

## A worked scenario

A company has three groups using AI.

| Group | Setup | Result |
|---|---|---|
| Support | Team with a healthy monthly budget. Keys tied to the team. | Customer chat keeps running even when others are busy. |
| Data | Team with a monthly budget sized for batch jobs. | Heavy jobs hit their own ceiling first. |
| Intern sandbox | Team with a very small budget. | A looping script stops after a few dollars and nobody else notices. |

At the end of the month, finance reads spend by team from the dashboard instead of guessing.

## What to do now

1. Create a team for each group that owns AI spend.
2. Set a monthly budget on each team. Start modest and raise it with evidence.
3. Issue application keys tied to the team, one service user per application.
4. Set per-minute ceilings for teams in the organization policy.
5. Make applications read the limit name in a 429 and show a helpful message.
6. Review spend by team monthly and adjust.

## Good to know

Dollar budgets for the day reset at 00:00 UTC, and team budgets reset at the start of each month. Spend is added after a call finishes, so requests already running when a budget is reached still complete. The per-minute ceiling for teams is one value in the organization policy applied to each team's own counter, so teams with very different needs can differ on budget even though they share the same rate ceiling. See [Rate limiting and budgets](/core-concepts/rate-limiting-and-budgets) and [Managing teams](/admin-console/managing-teams).

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

Needs Docker, no provider key. Console at http://localhost:5173. If it helps, star the repo or open an issue.

## Sources

- OpenProxyAI docs: [Rate limiting and budgets](/core-concepts/rate-limiting-and-budgets), [Managing teams](/admin-console/managing-teams), [Authentication](/getting-started/authentication), [API keys](/api-reference/api-keys), [Errors and status codes](/api-reference/errors-and-status-codes).
- On this blog: [Budgets that fail closed](/blog/budgets-that-fail-closed), [Keys will leak: design so a leaked application key is a nuisance](/blog/a-leaked-key-should-be-a-nuisance).

These statements are based on OpenProxyAI's behavior and docs as of November 10, 2026.
