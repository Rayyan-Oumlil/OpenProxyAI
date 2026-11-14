---
slug: do-you-need-a-gateway-with-one-provider
image: /img/blog/og/do-you-need-a-gateway-with-one-provider.png
title: "Do you need an LLM gateway if you only use one provider?"
tags: [product, architecture]
description: "Using a single model provider is a fine place to start. A gateway still earns its place on day one with policy, key custody, cost visibility and audit, and it makes a future second provider a small change."
---

Plenty of teams use exactly one model provider, and that is a sensible choice. One contract, one set of docs, one bill. So the fair question is: if there is only one provider, what would a gateway add? A gateway is not mainly about juggling providers. It is about having one place where your rules, your keys, your costs and your records live. Those matter just as much with one provider as with five.

{/* truncate */}

![A diagram with your apps on the left, each holding a gateway key. In the middle, a gateway lists five benefits: policy on every request, the provider key kept in one place, budgets and cost by team, an audit log of every call, and readiness to switch models later. On the right, a solid line leads to your one provider and a dashed line leads to a possible second provider later.](/img/blog/do-you-need-a-gateway-with-one-provider.svg)

## What changes when the rules live in one place

Without a gateway, every app talks to the provider on its own. Each one holds a provider key, sets its own retries, and decides for itself what is safe to send. That is fine for one app. It gets uncomfortable at three.

With a gateway, apps send requests to one endpoint using the SDK they already have. The gateway applies the same steps to every call: check the key, check limits, run policy, check the cache, call the provider, record the result ([request pipeline](/core-concepts/request-pipeline)). Here is what that buys you with a single provider.

### 1. Policy that every app inherits

Your organization sets one policy: which models may be used, which words or patterns should stop a request, whether personal data may leave, and whether prompts that look like injection attempts are refused. You can start in a log-only mode to see what would have been blocked, then enforce when you trust the rules. When a request is refused it returns HTTP 446 with a plain sentence explaining why, so the app can show a useful message ([policies and guardrails](/core-concepts/policies-and-guardrails), [refusals should explain themselves](/blog/refusals-should-explain-themselves)).

With one provider, this still matters. A model that is approved for public data may not be approved for customer records, and a team that tests with real data by accident is a common first incident.

### 2. Provider keys kept in one place

The provider key is a bearer credential: anyone who has it can spend your money. With a gateway, apps hold a gateway key instead, and the provider key stays with the platform team. If a gateway key leaks, you revoke one app's key and nothing else changes. If the provider key needs to change, you rotate it once, without redeploying the apps ([a leaked key should be a nuisance](/blog/a-leaked-key-should-be-a-nuisance), [rotating provider keys without a restart](/blog/rotating-provider-keys-without-a-restart)).

You can also register more than one key for the same provider, for example two keys with different rate-limit tiers. The gateway spreads traffic across them by weight, and if one is rate limited or unhealthy, it shifts to the others without any retry logic in your app ([provider routing](/core-concepts/provider-routing)).

### 3. Cost you can attribute

A provider invoice tells you the total. It does not tell you which team or feature caused it. A gateway tags each request with its team and records the cost, so you can see spend per team and set limits. Budgets can be set per user and per team, and a request that would go over is refused with a clear reason instead of showing up on next month's bill ([rate limiting and budgets](/core-concepts/rate-limiting-and-budgets), [know who spends what on AI](/blog/know-who-spends-what-on-ai), [budgets that fail closed](/blog/budgets-that-fail-closed)).

An optional cache can also answer repeated questions without a provider call, which is a cost lever you can switch on once you have traffic ([caching](/core-concepts/caching)).

### 4. Audit you do not have to build

When someone asks "who called which model last Tuesday, and what did it cost", you want one query, not a hunt through app logs. Each request is recorded with its model, token counts, cost, status and policy decision. By default the log holds metadata and not prompt text, and capturing text is an admin decision ([audit logging](/security/audit-logging), [an audit trail your auditor can read](/blog/an-audit-trail-your-auditor-can-read)).

### 5. Switching later becomes a small change

Today you use one provider. In a year there may be a cheaper model for simple tasks, a stronger one for hard tasks, or a regional requirement. If every app calls the provider's SDK directly, that is a migration project across every codebase. If apps call a gateway, adding a second provider is a registry and key change on the platform side, and the apps change at most the model name they request.

You can also test before you commit. The gateway can run an evaluation of a candidate model against your own examples before you route real traffic to it ([evaluating changes](/admin-console/evaluating-changes), [test a model change before you ship it](/blog/test-a-model-change-before-you-ship-it)). And you can move between models inside a conversation ([switching models mid-conversation](/blog/switching-models-mid-conversation)).

## A worked example

A six-person product team uses one provider for a support assistant and an internal summarizer. Before: both apps hold the provider key, nobody can say which one drives the bill, and a developer pasted a real customer email into a test prompt last month.

After adding a gateway:

| Before | After |
|---|---|
| Provider key in two codebases | Provider key in the gateway only; each app has its own gateway key |
| One invoice, no split | Cost per team, with a daily budget on each |
| Test prompt with real email reaches the provider | Policy flags the email; in enforce mode the request is refused with an explanation |
| No record of who called what | One log row per request |
| A second provider means two code changes | A second provider means a registry entry |

Changing the apps took one base URL ([migrate to a gateway in three lines](/blog/migrate-to-a-gateway-in-three-lines)).

## When you can wait

Be honest about your situation. If you have a single prototype, one developer, no sensitive data and no shared key, calling the provider directly is simpler. A gateway starts paying off when any of these become true:

- More than one app or team shares a provider account.
- Anyone outside the platform team holds the provider key.
- Someone asks you to show spend by team or to prove what data was sent.
- You expect to add a second model or provider.

## What to do now

1. Count how many places hold your provider key today.
2. Pick the one rule you most want enforced everywhere, such as "no customer identifiers in prompts".
3. Run a gateway in log-only mode for a week and read what it records.
4. Move one app to the gateway endpoint, then the rest.

## Try it

The demo runs with Docker and needs no provider key. Console at http://localhost:5173.

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

If it is useful, star the repo or open an issue describing your single-provider setup.

## Sources

- OpenProxyAI docs: [request pipeline](/core-concepts/request-pipeline), [policies and guardrails](/core-concepts/policies-and-guardrails), [provider routing](/core-concepts/provider-routing), [rate limiting and budgets](/core-concepts/rate-limiting-and-budgets), [audit logging](/security/audit-logging), [evaluating changes](/admin-console/evaluating-changes).
- No third-party facts are used in this post.

These statements are based on OpenProxyAI's behavior at the post date.
