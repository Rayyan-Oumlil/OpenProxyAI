---
slug: answers-from-models-without-a-price
title: "Never lose a model's answer because you cannot price it"
tags: [engineering, architecture]
description: An unlisted model never costs you an answer. The call completes, a flat fee is charged, and the cost is flagged as an estimate so budgets keep working.
---

A provider answers your request. The tokens are generated and billed. Then your gateway tries to work out what the call cost, and the model is not in its price list. What should happen next? In OpenProxyAI the answer is simple: the call completes, you get your answer, and the cost is recorded as an estimate. A missing price never decides whether you get a result. This post explains the rule and the trade-off behind it.

{/* truncate */}

![Request path: provider call, then price the call, then audit log. For a model with no listed price, a flat fee is charged, the answer is returned, and the row is logged as successful with the cost marked as an estimate.](/img/blog/answers-from-models-without-a-price.svg)

## The principle

OpenProxyAI prices calls from a table of per-token prices. New and niche models appear faster than any table can follow, and local or self-hosted models may never have a public price at all. So the gateway follows one rule on every endpoint: price after the answer, never instead of it.

For a model with no listed price:

- the answer is returned to the caller,
- the audit log records a successful call,
- a flat fee is charged per unit (a call, or an image),
- the request metadata carries `cost_estimated: true`.

The same rule applies to chat, batch lines, eval runs and conversation turns. A batch to a model nobody has priced yet runs to the end like any other.

## The design choice: open on price, not free

There were three options.

1. **Fail the call.** It looks safe, but it destroys a result that already exists and was already paid for.
2. **Return the answer and record zero cost.** The caller is happy, but spend is invisible. A model nobody can price becomes a model nobody can budget.
3. **Return the answer and charge a flat fee, flagged as an estimate.** This is what OpenProxyAI does.

The third option keeps both promises. Spend counters move, so [budgets and rate limits](/core-concepts/rate-limiting-and-budgets) still see the call. And the caller gets the answer they asked for. The flat fee is configurable, and the [environment flags](/getting-started/environment-flags) page lists it.

## A worked example

Say your team points a batch of 200 summarization lines at a brand-new model that is not in the price table yet.

- Every line returns its answer.
- Every line is logged as a success, with the flat fee as its cost.
- Each row carries `cost_estimated: true` in its metadata, so you can see exactly which calls were estimated.
- The daily and per-batch cost caps still apply, because the estimates count toward them.

For a model that does have a price, the flag is simply absent. It appears only when it is true, so it is easy to filter on.

## Why visibility matters

An estimate is only useful if it is honest about being one. The flag in the audit metadata separates exact costs from estimated ones, so finance and platform teams can tell which spend is firm. See [Audit logging](/security/audit-logging) for where the request metadata lives.

## What to do now

- Set the flat fee to something near your typical cost for models the price table does not list.
- Open a few batch or eval log rows and look for `cost_estimated` in their metadata to see which models are running on estimates.
- If you build a gateway: price after the answer, never instead of it, and make the fallback visible.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

Needs Docker, no provider key. Console at http://localhost:5173. If you run models the price table does not know yet, star the repo or open an issue and tell us which ones.

## Sources

- [Environment flags](/getting-started/environment-flags): the flat-fee setting.
- [Rate limiting and budgets](/core-concepts/rate-limiting-and-budgets): how spend is limited.
- [Audit logging](/security/audit-logging): where the request metadata lives.
- [Batch jobs](/admin-console/batch-jobs): the console view for batches.

These statements are based on OpenProxyAI's behavior at the post date.
