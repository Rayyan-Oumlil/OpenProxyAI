---
title: Semantic Cache Tuning
description: How the L3 semantic cache matches requests, and what to know before relying on it.
---

# Semantic Cache Tuning

The L3 tier of the [cache](/core-concepts/caching) matches requests by embedding similarity rather than exact text, so a rephrased prompt can still hit the cache instead of triggering a new provider call.

## When it helps most

Semantic matching pays off most on high-volume, templated use cases — support responses, summarization of similar documents, repeated internal Q&A — where the same underlying question is asked in many different words. It helps least on genuinely unique, one-off requests, where there's nothing similar to match against regardless of tuning.

## Trade-offs to know before relying on it

- L3 is checked after L1 and L2 exact-match tiers miss, and carries more latency than either (see [Caching](/core-concepts/caching) for the tier-by-tier latency breakdown).
- A similarity match is an approximation, not an exact match — for use cases where a subtly different prompt must always get a fresh answer, scope L3 out for that request rather than relying on default behavior.

:::info Configurable similarity threshold coming soon
Per-team or per-request control over the L3 similarity threshold is planned. Until then, defaults are tuned org-wide.
:::
