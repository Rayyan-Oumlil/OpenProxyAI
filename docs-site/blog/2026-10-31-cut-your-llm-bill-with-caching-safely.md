---
slug: cut-your-llm-bill-with-caching-safely
image: /img/blog/og/cut-your-llm-bill-with-caching-safely.png
title: "Cut your LLM bill with caching, and keep it safe: exact, semantic and isolated"
tags: [product, engineering]
description: "A request answered from a cache costs nothing at the provider. How exact and semantic caching work in OpenProxyAI, why entries never cross organizations, and when to leave the semantic tier off."
---

The cheapest model call is the one you do not make. Many apps send the same question again and again: a help-center answer, a standard summary, a classification of a repeated input. A cache returns the stored answer in milliseconds and the provider bills you nothing. The risk is that a cache can also return the wrong answer to the wrong person. OpenProxyAI gives you two kinds of cache, keeps them inside the organization, and keeps the riskier one off until you ask for it.

{/* truncate */}

![Two cards. The exact cache matches identical requests and is opt in per deployment. The semantic cache matches similar meaning and is off by default. A bar below says entries are never shared across organizations.](/img/blog/cut-your-llm-bill-with-caching-safely.svg)

## Where the savings come from

A cache hit skips the provider call. That removes the token cost and the wait for the model. Three kinds of traffic benefit most:

- **Repeated identical calls.** Nightly jobs, retries, test suites and apps that re-ask the same thing.
- **Templated questions.** Support macros, FAQ answers, internal policy questions.
- **Shared reference prompts.** The same instruction applied to the same public document.

Traffic that is unique every time, or that carries one person's details, will not benefit, and should not be cached.

## Exact caching

The exact cache returns a stored answer only when the new request is identical to an earlier one: the same organization, model, messages and temperature. Change one word and it is a miss. That makes it the safe default: the stored answer was written for exactly this prompt.

You can see it working. On the demo stack, send the same request twice. The first response is a miss, and the second is an exact hit, reported in the cache response header. Send it a third time with the bypass header set to skip, and it is a miss again.

```text
1st request                       miss
same request again                hit:exact
same request, cache skipped       miss
```

## Semantic caching

The semantic cache compares meaning, not text. "How do I reset my password?" can match a stored answer to "How can I change my password?". That catches the reworded repeats that an exact cache misses, which is where support and FAQ traffic gets most of its savings.

It is also an approximation. A similar prompt is not the same prompt. For that reason the semantic cache is **off by default**. An operator turns it on, and it needs an embedding endpoint that the operator configures. A similarity setting lets you trade hit rate against the risk of a loose match. The [semantic cache tuning guide](/core-concepts/caching) covers the settings.

## Isolation: the part that makes it safe to share infrastructure

Cache entries belong to one organization. Two organizations on the same deployment never receive each other's answers, in either tier. The exact key includes the organization, and the semantic match only looks at entries from the same organization and the same model.

Other protections apply on the way in:

- **Policy runs before the cache.** In enforce mode, a request that fails policy, for example one that contains personal data, is refused and never stored.
- **Response checks run before an answer is stored.** If you turn on response guardrails, the stored answer is the one the caller saw.
- **Some requests skip the cache.** Requests that use tools or structured outputs are not cached.
- **Entries expire.**
- **Any caller can opt out.** One header on one request skips the cache in both directions.

## When to leave the semantic tier off

Inside one organization, the cache does not tell people apart. A semantic hit can serve an answer that was written for a similar prompt from a colleague. That is the point of the feature, and it is fine for public or generic content. It is a poor fit when the answer depends on the person.

| Use case | Semantic cache |
|---|---|
| Help-center and FAQ answers | Good fit |
| Summaries of public documents | Good fit |
| Classification of repeated, generic inputs | Good fit |
| Anything about a named customer, patient or account | Leave it off |
| Answers that depend on who is asking | Leave it off |

If two groups must never see each other's answers, put them in separate organizations. We wrote about this in [A semantic cache is shared memory](/blog/semantic-cache-is-shared-memory).

## A rollout that stays safe

1. Turn on the exact cache first. Watch the hit rate in the cache analytics and in the console.
2. Pick one route with generic, repeated questions. Turn on the semantic cache there.
3. Read a sample of semantic hits by hand before you trust them.
4. Raise the similarity setting if you see matches that should have been misses.
5. Add the bypass header to routes that must always be fresh.
6. Keep policy on, so personal data is refused before it can be stored.

## What to do now

- Find your top five repeated prompts and estimate their monthly spend. Start there.
- Enable the exact cache and measure for a week.
- Decide, route by route, whether the answer depends on who asks.
- Write the "leave semantic off" list for your team, for example anything about a named person.
- Check the cache hit tier in the response headers while you test.

## Good to know

Hit rates depend on your traffic, so measure on your own before you plan around a number.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

Needs Docker and no provider key. The demo has the exact cache on, so you can watch a miss turn into a hit. The console is at http://localhost:5173. If it helps, star the repo or open an issue.

## Sources

- OpenProxyAI docs: [Caching](/core-concepts/caching), [Semantic cache tuning](/core-concepts/caching), [Policies and guardrails](/core-concepts/policies-and-guardrails), [Request pipeline](/core-concepts/request-pipeline).
- Earlier post: [A semantic cache is shared memory](/blog/semantic-cache-is-shared-memory), on what a cache hit is matched on.

Statements are based on OpenProxyAI's documented behavior at the post date.
