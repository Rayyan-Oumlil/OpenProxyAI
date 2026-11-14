---
slug: semantic-cache-is-shared-memory
title: "A semantic cache is shared memory: how to use it safely"
tags: [security, architecture]
description: Two 2026 papers show that semantic caches can be poisoned and hijacked. A cache that answers a question with a stored answer to a similar question is shared memory, and here is how OpenProxyAI scopes it, where to use it, and how to tune it.
---

A semantic cache saves money by answering "how do I reset my password?" with the stored answer to "how can I change my password?" That works because it matches on meaning, not on exact text. It also means the answer you get was written for someone else. Whether that matters depends on who "someone else" is allowed to be.

{/* truncate */}

## What the research says

Two peer-reviewed papers from 2026 study this directly.

- **Poisoning.** A paper at NDSS describes semantic caching as reusing query-response pairs across users based on semantic similarity, and notes it is built into the LLM serving of Azure, AWS and Alibaba. Its authors show that an attacker can inject crafted entries so that other users receive attacker-chosen answers, and report the attack working on all three major public clouds. They found existing prompt-injection defenses ineffective against it, and say complete mitigation remains challenging.
- **Key collisions.** A paper accepted to ICML 2026 treats the embedding as a fuzzy hash. The property that makes a cache useful, that similar inputs land near each other, is the opposite of what collision resistance needs. The authors build an automated attack that hijacks responses with an 86% hit rate in their tests and show it can push an agent into harmful behavior.

Neither paper says "do not cache." Both say the match is a security boundary and has to be treated as one.

## How OpenProxyAI scopes a cache hit

![Two match types shown as rows of tags. The exact match uses organization, model, messages and temperature. The semantic match uses organization, model, a fresh entry and a tunable similarity bar.](/img/blog/cache-scope.svg)

- **Exact match.** A hit needs the same organization, model, messages and temperature, so the stored answer was produced for exactly your prompt. Two organizations never share an entry.
- **Semantic match.** An incoming request is compared with fresh stored entries for the same organization and model, and the nearest one is served only if it clears a similarity bar you can tune.

Here is the exact match on the demo stack. The same request, sent twice, then once with the cache bypassed, then reworded:

```text
1st request                            HTTP 200  x-openproxy-cache: miss
same request again                     HTTP 200  x-openproxy-cache: hit:exact
same request, x-openproxy-cache: skip  HTTP 200  x-openproxy-cache: miss
reworded request (exact match only)    HTTP 200  x-openproxy-cache: miss
```

The reworded request missing is the exact match doing its job. Only the semantic match, when you have turned it on, can match a reworded prompt.

## Built-in safeguards

- **Caching is opt-in.** Both cache types are off until you enable them, and the semantic match also needs an embedding endpoint that you configure.
- **The embedding call goes only where you point it.** It never borrows an ambient key, and it is skipped in air-gapped mode.
- **Some requests never touch the cache.** Requests that use tools, functions or structured output skip it, as do requests whose behavior settings change anything beyond temperature.
- **Policy runs before the cache.** With enforcement on, a request that fails policy, including one containing personal data, is refused and never stored. Response guardrails run before an answer is stored.
- **Sensitive requests skip the semantic match.** Under enforced routing, requests above a data-class ceiling you set bypass it.
- **Entries expire**, and the semantic store is capped per organization.
- **A caller can bypass it.** The header `x-openproxy-cache: skip` skips the cache for that request, in both directions.

## Where it fits best

The organization is the cache's boundary, so match the cache to the content:

- **Use the semantic match for shared content.** Support macros, FAQ answers and summaries of public documents are ideal.
- **Keep personal prompts out of it.** For prompts that mention a specific customer, patient or account, use the bypass header or leave the semantic match off. A stored answer written for one person is exactly what a similar prompt from a colleague would retrieve.
- **Give each trust boundary its own organization.** If two groups should never receive each other's answers, separate organizations keep their caches apart.
- **Raise the threshold, then measure.** Paraphrases match at the default bar. Moving it up trades hit rate for fewer surprising matches. Watch hit rates in the cache analytics endpoint and review a sample of semantic hits before you rely on them.
- **Treat the cache as an input anyone with traffic can write to.** Rate limits, key scoping and keeping unauthenticated traffic away from cached routes matter as much as the threshold.

## Try it

The demo runs with Docker, needs no provider key, and has the exact cache on. Console at http://localhost:5173. Send a request twice and watch the header change.

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

If it is useful, star the repo or open an issue with the cache behavior you want next.

See [Caching](/core-concepts/caching) and [Semantic cache tuning](/guides/semantic-cache-tuning) for the settings.

## Sources

- Wu et al., [When Cache Poisoning Meets LLM Systems: Semantic Cache Poisoning and Its Countermeasures](https://www.ndss-symposium.org/ndss-paper/when-cache-poisoning-meets-llm-systems-semantic-cache-poisoning-and-its-countermeasures/), NDSS Symposium.
- Zhang et al., [From Similarity to Vulnerability: Key Collision Attack on LLM Semantic Caching](https://arxiv.org/abs/2601.23088), accepted to ICML 2026.
- OpenProxyAI docs: [Caching](/core-concepts/caching), [Semantic cache tuning](/guides/semantic-cache-tuning).

These statements are based on OpenProxyAI's behavior at the post date.
