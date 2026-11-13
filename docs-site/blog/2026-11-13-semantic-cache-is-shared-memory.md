---
slug: semantic-cache-is-shared-memory
title: "A semantic cache is shared memory. Here is what ours isolates, and what it does not"
tags: [security, architecture]
description: Two 2026 papers show that semantic caches can be poisoned and hijacked. A cache that answers a question with a stored answer to a similar question is shared memory between everyone who can reach it. What our cache keys on, with real output, and where to turn it off.
---

A semantic cache saves money by answering "how do I reset my password?" with the stored answer to "how can I change my password?" That works because it matches on meaning, not on exact text. It also means the answer you get was written for someone else. Whether that matters depends entirely on who "someone else" is allowed to be.

{/* truncate */}

## What the research says

Two peer-reviewed papers from 2026 study this directly.

- **Poisoning.** A paper at NDSS describes semantic caching as reusing query-response pairs across users based on semantic similarity, and notes it is built into the LLM serving of Azure, AWS and Alibaba. Its authors show that an attacker can inject crafted entries so that other users receive attacker-chosen answers, and report the attack working on all three major public clouds. They found existing prompt-injection defenses ineffective against it, and say complete mitigation remains challenging.
- **Key collisions.** A paper accepted to ICML 2026 treats the embedding as a fuzzy hash. The property that makes a cache useful, that similar inputs land near each other, is the opposite of what collision resistance needs. The authors build an automated attack that hijacks responses with an 86% hit rate in their tests and show it can push an agent into harmful behavior.

Neither paper says "do not cache." Both say the match is a security boundary and has to be treated as one.

## What ours matches on, read from the code

![Two tiers shown as rows of tags. The exact tiers match on organization, model, messages and temperature. The semantic tier matches on organization, model, not expired, and similarity of at least 0.95. A separate row lists user, team, API key and data class as not part of either match.](/img/blog/cache-scope.svg)

OpenProxyAI has three tiers: an in-memory cache, Redis, and a semantic tier on Postgres with pgvector.

- **Exact tiers.** The key is one SHA-256 over the organization, model, messages and temperature. A hit needs all four to be identical. Two organizations never share an entry.
- **Semantic tier.** An incoming request is embedded and compared with stored entries for the same organization and model that have not expired. The nearest one is served if its cosine similarity is at least `0.95` (`SEMANTIC_CACHE_SIMILARITY_THRESHOLD`).

Here is the exact tier on the demo stack. The same request, sent twice, then once with the cache bypassed, then reworded:

```text
1st request                          HTTP 200  x-openproxyai-cache: miss
same request again                   HTTP 200  x-openproxyai-cache: hit:exact
same request, x-openproxy-cache: skip  HTTP 200  x-openproxyai-cache: miss
reworded request (exact tier only)   HTTP 200  x-openproxyai-cache: miss
```

The reworded request missing is the exact tier doing its job. Only the semantic tier, when an operator has turned it on, could match a reworded prompt.

## What it does not isolate

This is the part to read before you turn the semantic tier on.

**Inside one organization, the cache does not distinguish people.** The semantic match filters by organization and model. It does not filter by user, team or API key. Neither does the exact key, though there the messages must be identical, so the stored answer was produced for exactly your prompt. The semantic tier is different: it can serve a stored answer written for a similar prompt from another user, because that is its purpose.

An illustration, made up for this post: one person asks for a summary of a named customer's contract, and a colleague later asks for a summary of a different customer's contract. The two prompts are close in embedding space. If they clear the threshold, the second person gets the first person's summary. Nothing was breached in the usual sense, and no one saw a prompt they should not. An answer written for one person was handed to another.

**The data class is not part of the match either.** The class is worked out from the content of the request, so identical messages have the same class, but a stored answer carries no label of its own.

## What we do to limit it

- **Both cache tiers are off by default.** An operator turns them on, and the semantic tier also needs an embedding endpoint the operator configures.
- **The embedding call never uses an ambient key.** It goes only to the endpoint the operator set, and is skipped entirely in air-gapped mode and for organizations whose data region is not in the shared-key list.
- **Some requests never touch the cache.** Anything with tools, functions or a structured-output format skips it, because the key does not cover those fields. So does a request whose behavior settings change anything beyond temperature.
- **Policy redaction happens before the cache.** A stored entry holds the redacted prompt, never the raw value that was removed.
- **Under enforced routing, the semantic tier is skipped above a data-class ceiling** (`OFF_REGISTRY_MAX_DATA_CLASS`, default `internal`), because building the embedding is a call to a model the registry does not govern.
- **Entries expire**, and the semantic tier is capped per organization.
- **A caller can bypass it.** The header `x-openproxy-cache: skip` skips the cache for that request, in both directions.

## What we would not recommend

- **Do not turn the semantic tier on for prompts that carry one person's data.** Support macros, FAQ answers and summaries of public documents fit. Anything that mentions a specific customer, patient or account does not.
- **Do not use one organization for two trust boundaries.** The organization is the only wall the cache has. If two groups should never receive each other's answers, put them in separate organizations.
- **Raise the threshold, then measure.** At `0.95`, paraphrases match. Moving toward `0.98` trades hit rate for fewer surprising matches. Watch the hit rates in `/api/v1/analytics/cache` and review a sample of semantic hits before you trust them.
- **Treat the cache as an input an attacker can write to.** Anyone who can send traffic to a cached route can try to place an entry. Rate limits, key scoping and keeping unauthenticated traffic away from the cache matter more than the threshold.

Per-user or per-team scoping inside an organization is not something the cache does today. If your use case needs it, use the bypass header on personalized routes or leave the semantic tier off.

## Try it

The demo runs with Docker, needs no provider key, and has the exact cache on. Send a request twice and watch the header change.

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

See [Caching](/core-concepts/caching) and [Semantic cache tuning](/guides/semantic-cache-tuning) for the settings above.

## Sources

- Wu et al., [When Cache Poisoning Meets LLM Systems: Semantic Cache Poisoning and Its Countermeasures](https://www.ndss-symposium.org/ndss-paper/when-cache-poisoning-meets-llm-systems-semantic-cache-poisoning-and-its-countermeasures/), NDSS Symposium.
- Zhang et al., [From Similarity to Vulnerability: Key Collision Attack on LLM Semantic Caching](https://arxiv.org/abs/2601.23088), accepted to ICML 2026.
- OpenProxyAI docs: [Caching](/core-concepts/caching), [Semantic cache tuning](/guides/semantic-cache-tuning).

Statements about OpenProxyAI come from its code and a run on the demo stack on November 13, 2026. The contract-summary example is hypothetical.
