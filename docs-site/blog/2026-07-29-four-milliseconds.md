---
slug: four-milliseconds
title: What actually happens in the four milliseconds before your LLM call
tags: [engineering, architecture]
description: A request to gpt-4o passes through six stages before it ever reaches OpenAI. Here's what each one is actually doing, and why the order isn't arbitrary.
---

"Adds a few milliseconds of overhead" is the kind of line that shows up in every proxy's marketing copy, ours included. It's true, but it undersells what's actually happening in that window. Six things happen, in a specific order, and the order is load-bearing — get it wrong and you either serve a cached answer to a request that policy should have refused, or you pay for cache infrastructure you can't actually use.

{/* truncate */}

## The pipeline

```mermaid
flowchart TD
    Req([Request]) --> Auth{1 · Auth}
    Auth -->|invalid key| R401[401]
    Auth -->|ok| Rate{2 · Rate limit}
    Rate -->|over limit| R429[429]
    Rate -->|ok| Policy{3 · Policy}
    Policy -->|enforce block| R446[446]
    Policy -->|ok / log-only| Cache{4 · Cache}
    Cache -->|hit L1/L2/L3| Resp([Response])
    Cache -->|miss| Route[5 · Route to provider]
    Route --> Provider[(Provider)]
    Provider --> Resp
    Resp -.->|async, never blocks| Log[(6 · Log)]
```

## Why the order isn't arbitrary

**Auth and rate limiting come first** because there's no point doing any other work — scanning for PII, checking a cache — for a request you're about to reject anyway. Reject cheap failures as early as possible.

**Policy runs before cache, not after.** This is the one that actually matters. If the cache check came first, a request that your policy would block could be answered from an entry stored before the rule existed, and the block would never happen. Running policy first means a refused request never reaches the cache or a provider. In `enforce` mode a request containing PII is refused outright rather than rewritten, so it is never stored. In `log_only` mode or with policy off, it passes and is cached as sent.

**Cache comes before routing** for the obvious reason: a cache hit means there's no routing decision to make at all. The request never reaches the provider-selection logic, because it never reaches a provider.

**Logging is the only stage that happens after the response is sent, not before.** Every other stage can reject or delay the request. Logging can't — it's fire-and-forget, written asynchronously once the response has already gone back to the caller. A slow or temporarily unavailable logging backend should never be the reason your application's request takes longer.

## What this costs in practice

Stages 1–3 and 5–6 typically add low-single-digit milliseconds combined — the actual overhead is dominated by whichever provider you're calling, not by OpenProxyAI. A cache hit at stage 4 doesn't add latency at all; it *replaces* the provider round-trip entirely, which is usually hundreds of milliseconds saved, not spent.

The four milliseconds aren't overhead you're paying for nothing. They're the four milliseconds where policy checks, limits, and cache-key correctness all have to happen in the right order — before the request goes anywhere you can't take it back from.

Full detail on each stage in [Request Pipeline](/core-concepts/request-pipeline).
