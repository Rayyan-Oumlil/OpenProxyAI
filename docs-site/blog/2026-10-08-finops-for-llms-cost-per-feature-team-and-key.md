---
slug: finops-for-llms-cost-per-feature-team-and-key
image: /img/blog/og/finops-for-llms-cost-per-feature-team-and-key.png
title: "FinOps for LLMs: cost per feature, per team, per key"
tags: [product, engineering]
description: "A single AI invoice cannot tell you which feature earns its cost. Attribute every request to a team, a key and a label, then read spend by each, project the month, and check the numbers against the provider."
---

FinOps is the habit of making cloud spend something engineers and finance can both read. For LLMs the habit is harder to start, because the first bill arrives as one number from one provider. It does not say which feature drove it, which team owns it, or whether last Tuesday's jump was a launch or a bug. The fix is to attribute cost at the moment of each request, not to reconstruct it afterward. A gateway sees every request, so it can do that without changing how teams build.

{/* truncate */}

![Each request carries a team, a key and labels. The gateway records its cost. Three reports read from the same log: spend by team, spend by key, and spend for one label value. Budgets sit on top.](/img/blog/finops-for-llms-cost-per-feature-team-and-key.svg)

## Three questions, three handles

Most cost questions are one of these:

| Question | Handle on the request | Where you read it |
|---|---|---|
| What does each department owe? | Team | Spend by team |
| Which application or service costs the most? | Key | Spend by key |
| What does this feature cost, across services? | Label | The request log filtered by label |

The handles are chosen at different times. The team and the key are set once, when you create a key and tie it to its team. The label is set per request by the caller. Used together, they give you three views of the same spend that agree with each other, because they come from the same log.

This is a close cousin of [showback and chargeback](/blog/showback-and-chargeback-for-llm-spend), which covers the monthly report for finance. This post is about the engineering side: finding the cost per feature and acting on it.

## Handle 1: the team

A request counts toward a team when its key is tied to that team. A shared key can still pick a team for each call with a documented header, as long as the caller belongs to that team. That is enough for departmental attribution. Spend by team, with requests and tokens beside it, is part of the analytics overview, which you can read in the console or through the analytics API. You can also limit the overview to one team.

## Handle 2: the key

Create one key per application and name it after the application. Now "which service costs the most" has a literal answer: the overview breaks spend down by key, showing the key name and its prefix, with requests, tokens and cost. The structured query endpoint, available to admins, can group the request log by key, model or user, and compute sums, averages and percentiles over a window you choose.

A key per application also helps when something goes wrong. A runaway loop in one service shows up as one key's line going vertical, and you can revoke that key without touching anything else.

## Handle 3: the label

Teams and keys cannot say "this was the summarize-ticket feature" when three services share it, or "this was the enterprise tier". Labels can. A request can carry up to ten short key and value pairs in a documented header:

```http
x-openproxy-labels: {"feature": "ticket-summary", "tier": "enterprise"}
```

Labels are recorded on the request log, and the log can be filtered by a label key and value, with each entry showing its cost. So the cost of one feature is the sum of the cost across the entries for that label over the period. Agree on a naming convention and write it down, because `ticket-summary` and `ticket_summary` are two different values.

## What each response tells you

Every successful response carries its own cost, the model that served it, and the latency in response headers. That lets a service log cost per call itself, or show "this answer cost less than a cent" in an internal tool. If your SDK is the OpenProxyAI Python SDK, the cost is on the response object too.

## From numbers to decisions

Attribution is only useful if it leads to action. Four patterns come up again and again.

1. **Find the biggest model line.** The overview lists spend by model. If one large model carries most of the cost, check whether every call needs it. Moving simple tasks to a smaller model is the largest saving most teams find.
2. **Use the cache for repeated work.** The cache report shows exact hits, semantic hits, misses, hit rate and estimated savings. For how the semantic tier decides, see [how semantic caching works](/blog/how-semantic-caching-works).
3. **Watch the forecast.** The overview includes a projected month-end cost, and the console shows a burn-down. A forecast that crosses the budget in week two is the cheapest alert you will get.
4. **Put a limit under it.** A monthly budget per team and a daily budget per user turn a report into a control. At 80 percent of the organization's daily budget a webhook fires, so the first signal is a message and not an invoice.

## Check the gateway against the provider

If finance will charge teams from these numbers, they should be able to trust them. The reconciliation endpoint compares gateway usage with a provider's own usage export, day by day and model by model, and shows every difference. Run it monthly. A mismatch is a lead: perhaps a key used outside the gateway, which tells you something your report could never show.

## A worked scenario

A company has two features that call the same model: a ticket summarizer owned by support and a contract search owned by legal. Both run in one shared service.

1. Platform creates two teams and two keys, one per owner, each tied to its team. The shared service uses the right key for each call.
2. The service adds a `feature` label to every request.
3. The overview shows legal's spend is three times support's. The label filter shows most of legal's cost is one feature, run with the largest model on every query.
4. Legal tests a smaller model for the first pass on its own prompts, then switches. The daily line drops.
5. At month end, finance reads spend by team, then runs the reconciliation against the provider's export.

## What to do now

- [ ] One key per application, tied to the owning team.
- [ ] Two or three label keys, written down, added to the shared client library.
- [ ] A monthly budget for every team and the 80 percent webhook.
- [ ] A weekly look at spend by model and the month-end forecast.
- [ ] A monthly reconciliation against each provider's export.

## Good to know

The by-team, by-key, by-user and by-model breakdowns come from the analytics overview. Labels are for filtering the request log, so use teams and keys for your main rollups and labels for the finer cut. A model the gateway cannot price is charged a small flat estimate and marked as an estimate, so check that your models have prices before you chargeback on them.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

Needs Docker, no provider key. Console at http://localhost:5173. If it helps, star the repo, and if you need a report we do not have, open an issue.

## Sources

- [Analytics API](/api-reference/analytics): overview, request log filters, cache report, reconciliation, structured query.
- [Rate limiting and budgets](/core-concepts/rate-limiting-and-budgets): team attribution, budgets, the 80 percent alert, how spend is counted.
- [Chat completions](/api-reference/chat-completions): the team and label headers.
- [API keys and provider keys](/api-reference/keys): a key tied to a team.
- [Webhooks](/guides/webhooks): the budget alert.
- On this blog: [showback and chargeback for LLM spend](/blog/showback-and-chargeback-for-llm-spend), [know who spends what on AI](/blog/know-who-spends-what-on-ai), [why your AI bill is unpredictable](/blog/why-your-ai-bill-is-unpredictable).

These statements are based on the sources above and on OpenProxyAI's behavior as of 2026-10-08.
