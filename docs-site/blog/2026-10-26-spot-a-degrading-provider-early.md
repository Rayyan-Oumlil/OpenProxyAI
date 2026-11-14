---
slug: spot-a-degrading-provider-early
title: "Spot a degrading provider before the status page does"
tags: [engineering, product]
description: "Status pages lag the real world. Your own traffic does not. Which error and latency signals to watch per provider, and how OpenProxyAI turns them into a health view and queries you can act on."
---

Status pages are written by people, after people notice. By then your users have been waiting on slow answers for a while. The earliest signal that a model provider is struggling is already in your own traffic: more errors, slower first tokens, odd spikes on one key. The trick is to have those numbers split by provider and by key, and to look at them before anyone asks.

{/* truncate */}

![Every request is recorded with status, latency and key. That feeds a provider health page with one state per key, a dashboard with success rate and p95 latency, and a query by model and day. The next step is to act: lower a weight, turn a key off, or add a second approved path.](/img/blog/spot-a-degrading-provider-early.svg)

## What degradation looks like

A provider rarely goes from fine to down. It slides. These are the early signs, roughly in the order they appear.

| Signal | What it usually means |
|---|---|
| Time to first token creeps up | The provider is queueing your requests, or a region is under load. |
| The slow tail grows (p95, p99) while the average looks fine | A share of requests are stuck. Averages hide this for a long time. |
| A trickle of server errors or rate-limit responses | Capacity is tight. It often precedes a larger failure. |
| One key or region looks worse than its siblings | A regional or account-level problem, not a global one. |
| Success rate dips at the same hour each day | A load pattern, yours or theirs. |

Two habits make these visible. First, **split by key and by model**. A blended number hides one bad key behind five good ones. Second, **watch the tail, not the mean**. Users feel the slow requests.

## Where the signals live in OpenProxyAI

Every request passes through the gateway, so every request is recorded with its model, provider, status, latency, time to first token and the key that served it. Three places turn that into something you can read.

**The provider health page.** It shows one state per provider key: healthy, degraded, down, not checked or disabled. Each state carries the reason in plain words, for example repeated failed health checks, a high error rate on recent requests, or an open circuit breaker that is routing traffic to other keys. Next to the state are the last health check, p99 latency, error rate and the weight the key is currently getting. The page refreshes on its own, so you can leave it open on a second screen during an incident.

![The OpenProxyAI provider health page, with counters for healthy, degraded and down keys and a table of keys with their state, latency and error rate.](/img/blog/console-provider-health.png)

**The dashboard.** It shows success rate with the number of failed requests, latency with the 95th percentile alongside, and spend by model. A sudden change in one of those after a deploy or a quiet weekend is a prompt to open the health page.

**Request logs and queries.** Logs filter by model, status and date, and each entry shows the provider, latency and cost. For a custom cut, admins can use the analytics query endpoint. For example, errors and tail latency per model per day:

```bash
curl -X POST https://api.openproxy.ai/api/v1/analytics/query \
  -H "Authorization: Bearer $OPENPROXY_SESSION_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "view": "requests",
    "select": ["model", "day", {"agg": "count", "as": "errors"}, {"agg": "p95", "column": "latency_ms"}],
    "where": [{"column": "status_code", "op": ">=", "value": 500}],
    "group_by": ["model", "day"],
    "order_by": [{"column": "day", "dir": "desc"}],
    "since": "2026-10-19T00:00:00Z"
  }'
```

The query is structured and read-only, scoped to your organization, and each run is recorded in the admin audit log. Run the same query without the filter to get a baseline, then compare.

## From signal to action

Seeing a problem early only matters if you can respond. Once a key looks unhealthy, you have options that need no deploy.

- **Lower its weight** through the provider keys API so it takes less traffic while you watch.
- **Turn it off**, from the provider keys page or the same API, without deleting it. It receives nothing until you turn it back on.
- **Rely on failover.** Failing calls already move to the next healthy key. The health page tells you that it is happening, which is the part people otherwise miss.
- **Add a second approved path** for the models that matter, in another region or at another provider, so there is somewhere to go next time. See [provider failover, explained](/blog/provider-failover-explained) for what has to happen in the seconds after a key starts erroring.

## A worked scenario

On a Tuesday morning the support team reports that the assistant feels slow. Nobody has posted an incident.

1. An engineer opens the provider health page. Two keys are healthy. One shows as degraded, with a high error rate on recent requests.
2. The dashboard shows the success rate has dipped and the 95th percentile latency has climbed since early morning.
3. A query by model and day confirms the errors are all on one model, served through that one key.
4. The engineer lowers the key's weight through the provider keys API. Traffic shifts to the healthy keys and the tail latency falls.
5. An hour later the provider's status page acknowledges an incident. The team was already out of it.

## What to do now

1. Open the provider health page once a day for a week, so you know what normal looks like.
2. Make sure each important model has at least two keys, so there is a healthy sibling to compare with and to fail over to.
3. Save a baseline query: errors and p95 latency per model per day.
4. Agree on a trigger, such as a key staying degraded for a set time, and who lowers a weight when it fires.
5. Add a budget alert webhook so a spike in retries also shows up as a spend signal. See [know who spends what on AI](/blog/know-who-spends-what-on-ai).

## Good to know

The health states depend on the data your deployment collects. Periodic health checks and per-key latency and error figures are optional settings for operators, and the page says so when data is missing instead of showing a false green. If you run the gateway yourself, turn them on and send some traffic first.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

You need Docker and no provider key. The console is at http://localhost:5173. If it helps, star the repo or open an issue with the signals you wish you could see.

## Sources

- [Provider routing](/core-concepts/provider-routing): weights, failover and health.
- [API keys and provider keys](/api-reference/keys): changing a key's weight or turning it off.
- [Analytics API](/api-reference/analytics): overview figures and the structured query endpoint.
- [Admin console overview](/admin-console/overview): the pages of the console.
- [Audit logging](/security/audit-logging): what each request record contains.

The statements above are based on these sources and on OpenProxyAI's behavior at the post date.
