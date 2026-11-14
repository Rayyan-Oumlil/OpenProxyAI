---
slug: overlapping-ai-outages-failover-plan
image: /img/blog/og/overlapping-ai-outages-failover-plan.png
title: "Several AI services failed on September 3: a failover plan that holds up"
tags: [architecture, engineering]
description: "On September 3, 2026, ChatGPT, Claude and Grok had overlapping outages, with Gemini users also reporting problems. What the reports say, what they do not, and how to build an approved fallback plan."
---

On September 3, 2026, several of the best-known AI services had trouble on the same morning. eWeek called the overlap rare. The reports do not show a common cause, and each provider gave a different explanation. Still, the morning is a useful reminder for anyone with an AI feature in production: one provider being down is a plan, and several being down at once is a test of the plan.

{/* truncate */}

![A ladder of approved fallbacks: primary provider, second approved provider, exact cache or queued batch, and a clear refusal.](/img/blog/overlapping-ai-outages-failover-plan.svg)

## What was reported

According to [eWeek's report](https://www.eweek.com/news/chatgpt-claude-grok-gemini-outages/), published September 4, 2026:

- Anthropic and SpaceXAI began reporting problems shortly after 9:25 a.m. Eastern. OpenAI reported its issue at 10:43 a.m. All three providers had restored service by 1:07 p.m.
- Claude's API, Claude Code and Cowork showed errors. ChatGPT and Codex were affected. Grok's outage lasted three hours and 37 minutes.
- eWeek calculated that ChatGPT, Claude and Grok were affected at the same time for 93 minutes.
- Gemini users reported failed responses and slow performance, but Google had not confirmed a widespread consumer outage, and eWeek left Gemini out of its overlap calculation.
- The stated causes differed. OpenAI cited a routing error, Anthropic cited infrastructure issues, and SpaceXAI pointed to an outage at its Memphis compute center. No provider linked the incidents, and the article notes that timing alone does not show a shared cause.

We have not drawn any conclusions beyond that. We did not check the providers' own status pages for this post, so the times above are as eWeek reported them.

## What it means for you

Overlapping failures do not prove that multi-provider setups are pointless. They show what a second provider can and cannot do:

- If one provider is down and another is up, a second approved path keeps you running.
- If your second path is a different product from the same vendor, or sits behind the same infrastructure, it may fail with the first.
- If all your approved paths are down, the best outcome is a fast, clear answer, not a hang, and not a quiet move to something nobody approved.

The goal is not zero downtime. It is a decision made in advance about what happens at each step.

## How OpenProxyAI helps

OpenProxyAI puts every provider behind one OpenAI-compatible endpoint, so a fallback does not need an application change.

- **Failover across keys.** If a provider key is rate-limited, erroring or has failed recent health checks, the router moves traffic to the remaining healthy keys without any client-side retry code. See [provider routing](/core-concepts/provider-routing).
- **Health you can see.** The console shows each key as healthy, degraded or down, with latency and error rate, so you notice trouble before your users report it.
- **A backup model per request.** A caller can name a backup model and a retry limit. Under enforced routing, the backup is used only if it is authorized for that request.
- **Fallbacks stay inside approved routes.** The registry decides which models may serve which data, and failover picks only from that set. A sensitive request does not wander to an unapproved provider during an incident. See [our post on provider failover](/blog/provider-failover-explained) and [multi-region data residency](/blog/multi-region-data-residency).
- **A clear refusal when nothing approved is up.** The gateway answers with a plain explanation instead of guessing. A policy or routing decision comes back as HTTP 446, which is different from a provider error in the 5xx range, so your code can tell a refusal from an outage.
- **Cheap degraded modes.** Repeated prompts can be answered from the exact cache. Work that can wait can go through the batch API and finish in the background. See [caching](/core-concepts/caching) and the [batches API](/api-reference/batches).

![The OpenProxyAI provider health page, with counters for healthy, degraded and down keys and a table of keys with their state, latency and error rate.](/img/blog/console-provider-health.png)

## A worked scenario

A support assistant uses one provider as primary and a second, approved provider as backup, both cleared for internal data.

1. The primary starts returning errors. Health checks mark its key degraded, and the router sends traffic to the second provider. Users see nothing.
2. The second provider also slows down. The assistant's repeated questions, such as password resets, are served from the exact cache. Longer reports are queued for the batch API.
3. A request that no approved model can serve returns a clear refusal. The chat window shows a short message and a retry time, and the on-call engineer sees the same event in the request log.

None of this required a code change during the incident. It was decided beforehand.

## What to do now

- Count your real independent paths. Two models from the same provider are one path.
- Register a second provider inside the same data clearance and region.
- Decide per use case what degrades: cache, queue, smaller model, or a clear error.
- Turn on health checks and an alert on key state.
- Make clients treat a policy refusal and a provider error differently.
- Rehearse: in staging, switch off a key and watch what your callers see.

## Good to know

A gateway can only fail over to routes you have configured and approved. If every route you have approved shares a problem, the right result is the clear refusal.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

This needs Docker and no provider key. The console is at http://localhost:5173. If it is useful, star the repo or open an issue with the resilience features you want.

## Sources

- [ChatGPT, Claude, Grok, and Gemini Hit by Rare Overlapping Outages](https://www.eweek.com/news/chatgpt-claude-grok-gemini-outages/), eWeek, September 4, 2026. Times, services, durations and stated causes.
- [Provider routing](/core-concepts/provider-routing): failover and health.
- [Errors and status codes](/api-reference/errors-and-status-codes): the difference between 446 and 5xx.
- [Caching](/core-concepts/caching) and [batches API](/api-reference/batches): degraded modes.

These statements are based on the sources above and on OpenProxyAI's behavior as of September 4, 2026.
