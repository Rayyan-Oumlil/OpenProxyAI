---
slug: why-ai-gateways-converge
title: "Why every AI gateway ends up building the same six things"
authors: [rayyan]
tags: [architecture, product]
description: Look at enough LLM proxies — the ones that started as routers, the ones that started as observability tools, the ones that started as guardrail products — and they all converge on roughly the same feature set. That's not a coincidence.
---

Look across the category — tools that started as pure multi-provider routers, tools that started as observability platforms, tools that started as guardrail/safety products — and a strange thing happens over about eighteen months: they all start shipping roughly the same six capabilities, regardless of which door they walked in through.

{/* truncate */}

## The six things

```mermaid
flowchart LR
    A[Auth] --> B[Rate limiting]
    B --> C[Routing / failover]
    C --> D[Caching]
    D --> E[Policy / redaction]
    E --> F[Audit logging]
```

1. **Auth** — every gateway needs to know who's calling, which means API keys or org-scoped credentials from day one.
2. **Rate limiting** — the moment there's more than one team or customer sharing the gateway, someone needs a ceiling, or one noisy caller starves everyone else.
3. **Routing / failover** — the entire pitch of "one API, many providers" is hollow if a provider outage takes your app down with it, so failover stops being optional almost immediately.
4. **Caching** — cost pressure is universal, and semantic or exact-match caching is the highest-leverage lever available before touching model choice.
5. **Policy / redaction** — this is the one that arrives later, usually forced by a customer's security review rather than an internal roadmap decision, but it arrives for almost everyone eventually.
6. **Audit logging** — once policy enforcement exists, "prove it happened" is the natural next ask, and it's also the thing that turns a technical tool into something a compliance team will actually sign off on.

## Why convergence happens instead of specialization

The intuitive expectation is that a router stays a router, an observability tool stays an observability tool, and the market ends up with well-differentiated point solutions. That's not what happens, for a structural reason: each of the six capabilities creates *demand* for the next one once it exists.

A router that handles multiple providers immediately needs rate limiting, because now there's shared infrastructure with multiple tenants. Rate limiting immediately raises the question of budgets, because "limited" and "affordable" turn out to be different problems. An observability tool that shows you an expensive or risky request immediately gets asked "can you also just block that," which is policy enforcement wearing a different name. A caching layer that stores request/response pairs is most of the way to an audit log already — the data model overlaps enormously, even if the original intent was purely performance.

The pattern holds regardless of starting point because the underlying need — "let my org use multiple LLM providers safely, affordably, and provably" — is a single coherent problem. Products that enter through one door tend to walk toward the others because their users keep asking for the adjacent piece, not because of some grand product strategy.

## What actually stays differentiated

Given that convergence, the meaningful differences between mature products in this category aren't feature checklists anymore — most serious options eventually check most of the same boxes. The differences that persist are architectural defaults that are expensive to change after the fact: SaaS-first versus self-hosted-first as the default deployment model, whether policy enforcement is a core pipeline stage or an integration you wire in separately, whether the admin surface assumes a security/compliance reviewer as a user or only an engineer. Those are decisions baked in from the first architecture diagram, and they don't converge the way feature lists do — which is usually the more useful axis to evaluate on than a side-by-side capability table.
