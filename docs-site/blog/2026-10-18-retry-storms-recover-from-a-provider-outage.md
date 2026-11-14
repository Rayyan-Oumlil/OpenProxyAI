---
slug: retry-storms-recover-from-a-provider-outage
image: /img/blog/og/retry-storms-recover-from-a-provider-outage.png
title: "Retry storms: recover from a provider outage without causing a second one"
tags: [engineering, product]
description: "When a model provider degrades, well-meant retries from every layer of your stack can pile on and keep it down. How to back off, cap attempts and fail over, and what OpenProxyAI does for you."
---

A model provider starts returning errors. Your app retries. The SDK under it retries. The queue worker behind that retries too. A few minutes later the provider is still struggling, and a large share of the load it sees is your own repeated calls. This is a retry storm, and it turns a short outage into a long one. The fix is a small set of habits, and a gateway can enforce most of them in one place.

{/* truncate */}

![Two designs for the same outage. Stacked retries at three layers can send up to 27 calls for one user request. One owner of retries, with backoff, failover to another key and a spend cap on batch work, keeps the load bounded.](/img/blog/retry-storms-recover-from-a-provider-outage.svg)

## Why retries make outages worse

A retry is a bet that the failure was brief. During a real incident the bet loses, and every client places it at the same moment. Three things make it worse.

- **Retries multiply across layers.** If each of three layers tries three times, one user request becomes up to 27 calls. The numbers in the diagram are an example, but the multiplication is real.
- **Clients retry in step.** If every caller waits the same two seconds, the provider sees waves of traffic instead of a trickle.
- **Some errors should never be retried.** A malformed request, a bad key or a policy refusal will fail the same way every time. Retrying it only adds load.

## Habits that keep you safe

**Retry only what is retryable.** Rate limits and server errors may clear on their own. Client errors will not. Treat the two differently.

**Back off with jitter.** Wait longer after each failure, and add a random amount so callers do not move in lockstep. Doubling the wait each time, with a ceiling, is the common shape.

**Honor the server's hint.** When a response says how long to wait, wait at least that long. Do not invent a shorter delay.

**Cap the attempts.** Two or three tries is plenty for a user-facing call. Past that, return a clear error and let the user or a queue decide.

**Give retries one owner.** Pick a single layer to retry, and set the others to zero. Stacked retries are how a small outage becomes a flood.

**Cap concurrency, not just attempts.** When a provider slows down, requests pile up in flight. A limit on how many calls a service has open at once stops a slowdown from eating all your workers.

**Prefer another path to the same path.** A retry against the key that just failed is the weakest option. A retry against a different key, or a different approved model, has a real chance of working.

**Make retried work safe.** If a retry can run the same action twice, such as charging a card from an agent step, add an idempotency check on your side.

## What OpenProxyAI does for you

Because every call already passes through the gateway, it can own the retry decision so your apps do not have to.

| Habit | What happens at the gateway |
|---|---|
| Retry only what is retryable | Rate limits and server errors move on to another key. Client errors are returned as they are, never retried. |
| Prefer another path | A failed call goes to the next healthy key for that model, weighted by the weights you set. It does not hammer the key that just failed. |
| Cap the attempts | The chain of keys is bounded, and a request can lower the cap with the `x-openproxy-retries` header, from 0 to 5. |
| Fail over across models | A request can name a backup model with `x-openproxy-fallback-model`. Under enforced routing it is used only if your registry authorizes it for that data. |
| Stop sending to a sick key | Health checks and an optional circuit breaker take a failing key out of rotation until it recovers. When every key for a model is out, callers get a 503 with a `Retry-After` hint instead of a pile of slow timeouts. |
| Honor hints | Limit responses are `429` with a `Retry-After` header and a body that says which limit was reached. |
| Cap batch work | A batch job runs its lines at a small fixed concurrency and stops when it reaches the spend cap you set. |

The gateway tries each key at most once per request and moves on. It does not add waiting between keys, because each attempt goes to a different place. The waiting belongs on your side, and that is the part to design on purpose.

## A worked scenario

An analytics team runs a nightly job that sends thousands of summaries through the gateway. Halfway through, one provider region starts returning server errors.

1. The gateway moves each failing call to the team's second provider key. Most lines finish without anyone noticing.
2. The failing key shows as degraded on the provider health page, with the reason next to it.
3. The batch job runs at a bounded concurrency, so it does not flood the second key. Its spend cap means a bad night cannot become a bad invoice.
4. The interactive assistant, which a person is waiting on, has client retries set to one, with jitter. If both keys are struggling, it returns a clear error in seconds instead of spinning.
5. Once the provider recovers, health checks bring the first key back into rotation.

Nobody paged a human to edit a config file, and the provider never saw a stampede.

## What to do now

1. List every layer that retries: your code, your SDK, your queue, your agent framework. Keep one, set the rest to zero.
2. Use exponential backoff with jitter, a ceiling and a small attempt cap in the layer you keep.
3. Read `Retry-After` and obey it.
4. Put a concurrency limit on every service that calls a model.
5. Register a second key, ideally with a different region or account, for each model that matters.
6. Name an approved backup model for the calls that can tolerate one.
7. Move bulk work to the batch API, with a spend cap.
8. Rehearse: turn off a key in staging and watch what your apps do.

## Good to know

Failover protects you from a key or a region failing. If a provider is down for everyone, a second key at the same provider will not help, so plan a second approved provider for the work that matters. The post on [provider failover](/blog/provider-failover-explained) walks through the sequence in more detail, and [one endpoint for every provider](/blog/one-endpoint-every-provider) shows how a second provider is added without changing application code.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

You need Docker and no provider key. The console is at http://localhost:5173. If it helps, star the repo or open an issue with what you would like to see.

## Sources

- [Provider routing](/core-concepts/provider-routing): weighted keys, failover and health.
- [Rate limiting and budgets](/core-concepts/rate-limiting-and-budgets): the 429 response and `limit_type`.
- [Chat completions](/api-reference/chat-completions): the retry and fallback headers.
- [Batches](/api-reference/batches): spend caps for bulk work.
- [Errors and status codes](/api-reference/errors-and-status-codes): what each code means and what to retry.

The statements above are based on these sources and on OpenProxyAI's behavior at the post date.
