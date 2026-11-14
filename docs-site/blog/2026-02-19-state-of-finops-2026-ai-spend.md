---
slug: state-of-finops-2026-ai-spend
image: /img/blog/og/state-of-finops-2026-ai-spend.png
title: "State of FinOps 2026: 98% now manage AI spend, and visibility is the hard part"
tags: [product, security]
description: "The FinOps Foundation's State of FinOps 2026 survey reports that 98% of respondents manage AI spend. Here is what the survey says about visibility and allocation, and how budgets, labels and attribution answer it."
---

Managing AI spend used to be a niche job. The FinOps Foundation's State of FinOps 2026 survey, released on February 19, 2026, says it is now close to universal. If you run AI features in a company, someone is probably already asking you who spent what. This post covers what the survey reports and what a gateway can do about the hard parts.

{/* truncate */}

![A request carries a team and labels, is attributed to a team, checked against daily and monthly dollar limits, then reported by model and team.](/img/blog/state-of-finops-2026-ai-spend.svg)

## What the survey says

The [Linux Foundation's announcement](https://www.linuxfoundation.org/press/state-of-finops-survey-ai-value-and-skills-top-priorities-as-finops-matures-across-technology-value-98-manage-ai-90-saas-64-licensing-48-data-center-1) of the sixth annual survey, and the results at [data.finops.org](https://data.finops.org/), give these figures:

- 1,192 respondents took part, with companies that together represent more than $83 billion in annual cloud spend.
- 98% of respondents manage AI spend. The results page puts it at 63% in 2025, and the announcement says it was 31% two years earlier.
- FinOps for AI is the top forward-looking priority.
- Many organizations are asked to fund AI investments through efficiency gains.
- The challenges respondents name are visibility into AI costs, because pricing models differ between providers, allocating AI costs to business units, which the survey calls harder than traditional infrastructure, and determining value and return.
- The most requested tooling feature is granular monitoring of AI spend, such as tokens and LLM requests.

We use only those figures. The survey is about practitioners' priorities, and we do not read more into it than it says.

## What it means

Two of the named challenges are the kind of problem data can solve: seeing the cost, and assigning it to an owner. The third, value, is a judgment call, but it is impossible without the first two. If you cannot say which team spent what on which model, you cannot say whether it was worth it.

A bill from a model provider does not help much. It shows one total for one key. The detail you need, who, which feature, which model, how many tokens, lives in the requests, and the gateway is the place that sees all of them.

## How OpenProxyAI helps

OpenProxyAI treats attribution and limits as part of every request, not a report built afterward.

| Challenge | What OpenProxyAI offers |
|---|---|
| Visibility across providers | One endpoint for every provider, with cost, tokens, model, status and policy decision recorded for each request. The analytics API and the console show spend by model, user, key and team, plus a daily trend. |
| Allocating cost to owners | A request counts toward a team when its API key is tied to that team, or when it carries the team's identifier. Requests can also carry up to ten labels, such as an application or cost center, which you can filter on in the logs and analytics. |
| Controlling spend | Dollar budgets per day for the organization and for a user, and per month for a team. A request that would pass a limit is refused with a clear response that names the limit. Requests per minute and tokens per minute can also be limited per team. |
| Seeing it coming | The dashboard shows a monthly burn-down with a projection to month end. When daily spend reaches 80% of the organization budget, a webhook is sent so your own tools can react. |
| Handing it to finance | An export for reviewers includes budget against actual cost for the period. |

See [rate limiting and budgets](/core-concepts/rate-limiting-and-budgets), the [analytics API](/api-reference/analytics) and [webhooks](/guides/webhooks) for details.

## A worked scenario

A company has four product teams sharing three providers.

1. Each team gets its own API key, tied to the team, and an admin sets a monthly dollar budget for each.
2. Applications add a label for the feature, such as "search" or "support-bot", to each request.
3. The platform lead opens the console. Cost by team shows who is ahead of plan, and filtering by label shows which feature is driving it.
4. One team reaches 80% of its daily budget early in the day. A webhook posts to the team's chat channel. If the limit is reached, further requests are refused with a message naming the limit, not silently failing.
5. At month end, finance gets the budget-against-actual export and a clear answer to "who spent what."

No application had to be rewritten to get any of this, since the labels are request headers and the attribution is in the key.

## What to do now

- Give every team and every service its own key.
- Decide on a small, consistent set of labels, such as application, environment and cost center.
- Set budgets at the organization, team and user level before usage grows.
- Send budget alerts to where the owners already work.
- Review spend by model each month, since price differences between models are often the biggest lever.
- Agree with finance on what "value" means for each feature, so the numbers have a counterpart.

## Good to know

Spend is added after a call finishes, so requests already in flight when a budget is reached still complete. Budgets are a strong guardrail, not a hard cap to the cent.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

This needs Docker and no provider key. The console is at http://localhost:5173. If it is useful, star the repo or open an issue with the reports you want.

## Sources

- [State of FinOps survey: AI value and skills top priorities](https://www.linuxfoundation.org/press/state-of-finops-survey-ai-value-and-skills-top-priorities-as-finops-matures-across-technology-value-98-manage-ai-90-saas-64-licensing-48-data-center-1), Linux Foundation and FinOps Foundation, February 19, 2026. Survey size, spend represented, the 98% and 31% figures, and priorities.
- [State of FinOps 2026 results](https://data.finops.org/), FinOps Foundation. The 63% figure for 2025, the named challenges and the most requested tooling feature.
- [Rate limiting and budgets](/core-concepts/rate-limiting-and-budgets): limits, attribution and alerts.
- [Analytics API](/api-reference/analytics): spend by model, user, key, team and label.

These statements are based on the sources above and on OpenProxyAI's behavior as of February 19, 2026.
