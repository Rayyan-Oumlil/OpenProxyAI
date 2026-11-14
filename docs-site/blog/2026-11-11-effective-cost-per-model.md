---
slug: effective-cost-per-model
image: /img/blog/og/effective-cost-per-model.png
title: "List price is not what you pay: measure the effective cost per model"
tags: [product, engineering]
description: "Price per token is only the start. Cache hits, prompt length, model mix and batch work change what a model really costs you. How to measure effective cost per model from your own traffic."
---

Every model comes with a price list: so much per million input tokens, so much per million output tokens. Teams pick a model by comparing those lists, and then the invoice does not match the spreadsheet. The reason is that list price describes the model. Your bill describes your traffic. The number worth tracking is the **effective cost**: what you actually paid, divided by what you actually got.

{/* truncate */}

![List price is the price per token and says nothing about your traffic. What moves the real number is cache hits, prompt and answer length, the mix of models and batch jobs with a spend cap. Effective cost per request is spend on a model divided by its requests, taken from your own logs.](/img/blog/effective-cost-per-model.svg)

## What sits between list price and the invoice

| Factor | How it changes the cost of a request |
|---|---|
| **Cache hits** | A request answered from a cache never reaches the provider, so it costs nothing there. A model with a high hit rate is cheaper per request than its list price suggests. |
| **Prompt length** | Input tokens are billed. A long system prompt or a growing chat history repeats on every call. Two teams on the same model can pay very different amounts per request. |
| **Answer length** | Output tokens are billed too, and priced separately from input. A model that writes long answers costs more than the same model asked to be brief. |
| **Model mix** | A cheaper model that handles the easy jobs lowers the blended cost. A premium model used for everything raises it. |
| **Retries and loops** | A failed or repeated call is still traffic. A loop multiplies the cost of one task. |
| **Batch work** | Work that can wait can run as a batch with a spend cap set before it starts, so its cost is known up front. |

## The number to track

For each model, over a period:

- **Effective cost per request** = spend on the model divided by its requests.
- **Effective cost per useful outcome**, if you can count outcomes, such as resolved tickets or generated reports. This one is the best, because it includes retries and failures.
- **Share of spend** = this model's spend divided by total spend. It shows where optimizing pays.

Compare models on the same job, not across different jobs.

## How OpenProxyAI makes it measurable

Every request passes through the gateway and is recorded with its model, tokens, cost, team, key, user and outcome. Cost is calculated from the prices registered for each model, so register a price for every model you use. A model without a price is charged a small flat estimate and marked as an estimate, which is a poor basis for comparison. The post on [answers from models without a price](/blog/answers-from-models-without-a-price) explains how to avoid it.

From there you have three ways to read the data.

**The dashboard.** Pick a range of 7, 30 or 90 days. Top models by cost shows where the money goes. Cost by team, key and user shows who. The cache hit rate sits with the reliability numbers, and the monthly burn-down projects where you will land. The post on [seeing your AI usage at a glance](/blog/see-your-ai-usage-at-a-glance) walks through the page.

**The overview API.** One call returns requests, tokens and cost grouped by model, user, key and team, plus a daily trend. Dividing cost by requests for each model gives you effective cost per request in a few lines of code.

**The structured query.** Admins can ask a custom question of the request records: for each model, how many requests, how much spend, how many tokens and what tail latency.

```bash
curl -X POST https://api.openproxy.ai/api/v1/analytics/query \
  -H "Authorization: Bearer $OPENPROXY_SESSION_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "view": "requests",
    "select": ["model", {"agg": "count", "as": "calls"}, {"agg": "sum", "column": "cost_usd", "as": "spend"}, {"agg": "avg", "column": "total_tokens", "as": "avg_tokens"}],
    "group_by": ["model"],
    "order_by": [{"column": "spend", "dir": "desc"}],
    "since": "2026-10-12T00:00:00Z"
  }'
```

Spend divided by calls is the effective cost per request. Average tokens per call tells you whether it is the price or the prompt that is driving it. The query is read-only, scoped to your organization, and each run is recorded in the audit log.

**Cache analytics.** A separate call reports exact hits, semantic hits, misses, hit rate and the estimated savings for a period. Each request log also records whether it was a hit or a miss. See [cutting your LLM bill with caching, safely](/blog/cut-your-llm-bill-with-caching-safely) for how the two cache types work and when to leave the semantic one off.

## Moving the number

Measurement pays when it leads to a change you can test.

- **Cache what repeats.** Help-center answers, standard summaries and classifications of repeated input are the best candidates. The cache is isolated per organization.
- **Trim prompts.** Cost by key often reveals one integration with an oversized prompt.
- **Match model to job.** With classification-aware routing on, a request can ask for a capability and the gateway picks the cheapest authorized model that has it. Before you switch a workload to a cheaper model, [test the change](/blog/test-a-model-change-before-you-ship-it) so quality does not quietly fall.
- **Move waiting work to the batch API.** A batch has a start, an end and a cost ceiling. See [when to use the batch API](/blog/when-to-use-the-batch-api).

## A worked scenario

A finance lead asks why two assistants on the same model cost very different amounts.

1. Cost by key shows the support assistant spends far less per request than the internal research assistant, on the same model.
2. A query grouped by model shows the research assistant averages many more tokens per call. Its prompt carries a long document on every turn.
3. The cache analytics show the support assistant gets a high hit rate, because users ask the same questions. The research assistant gets almost none.
4. The research team shortens the prompt and moves its nightly digests to a batch with a spend cap.
5. Next month the effective cost per request for that key drops, and the number is visible in the same dashboard.

The model and its list price never changed.

## What to do now

1. Register a price for every model you use.
2. Open the dashboard and write down effective cost per request for your top three models.
3. Check the cache hit rate. If it is near zero, find the repeated traffic.
4. Compare average tokens per call across keys on the same model.
5. Pick one workload to move to a cheaper model, test it first, and compare effective cost before and after.
6. Move one waiting job to a batch with a cap.
7. Repeat monthly.

## Good to know

Effective cost is only as good as the prices registered for your models, so check them after a provider changes its price list. The cache savings figure is an estimate, not an invoice line. Reconcile against your provider's usage export from time to time with the reconcile call in the analytics API.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

You need Docker and no provider key. The console is at http://localhost:5173. If it helps, star the repo or open an issue with the cost view you wish you had.

## Sources

- [Analytics API](/api-reference/analytics): overview, cache analytics, reconcile and the structured query.
- [Caching](/core-concepts/caching): exact and semantic caching and how to measure them.
- [Batches](/api-reference/batches): spend caps for batch jobs.
- [Provider routing](/core-concepts/provider-routing): how requests reach a model.
- [Admin console overview](/admin-console/overview): the dashboard and its pages.

The statements above are based on these sources and on OpenProxyAI's behavior at the post date.
