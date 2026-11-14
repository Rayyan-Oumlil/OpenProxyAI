---
slug: api-gateway-or-ai-gateway
title: "API gateway or AI gateway: do you need both?"
tags: [architecture, product]
description: "A general API gateway protects and routes traffic. An AI gateway understands prompts, tokens, models and cost. Here is where the first one stops, where the second starts, and how they fit together."
---

You already run an API gateway. It terminates TLS, checks who is calling, and rate limits by request. Then a team asks to call a model provider, and someone says "we can just route it through the gateway we have". That works on day one. By month three, the finance team wants to know which team spent what, and the security team wants to know whether customer data left the building. Neither question is one a general API gateway was built to answer. This post draws the line.

{/* truncate */}

![Three boxes in a row. Clients on the left call an API gateway that handles who is calling, request rates, TLS and versioning. That passes traffic to an AI gateway that handles what is being asked, tokens and dollars, which model may run, model providers, and the cost and audit trail.](/img/blog/api-gateway-or-ai-gateway.svg)

## What a general API gateway is good at

An API gateway sits in front of services and treats every request as an opaque call to a route. It is excellent at the things all APIs need:

- **Identity.** Who is this caller, and are they allowed on this route?
- **Traffic shape.** Requests per second, burst limits, timeouts.
- **Transport.** TLS, routing, versioning, load balancing.
- **Edge safety.** Blocking bad clients, basic request validation.

Keep it. Your AI traffic still enters your network through the same front door as everything else, and that front door should keep doing these jobs.

## Where it stops

Language model traffic has properties that a route-and-rate view cannot see.

| Property of AI traffic | Why a route-level view misses it |
|---|---|
| **The cost is in the content.** One request can cost a fraction of a cent or several dollars, depending on the prompt and the model. | Counting requests says nothing about money. You need tokens and dollars. |
| **The risk is in the content.** A prompt can carry a customer's card number, or an instruction that tries to hijack the model. | The body is just bytes to a route-level gateway. Detecting personal data or injection means reading the text. |
| **The destination is a choice.** Which model, which provider, which region? | A route points at a URL. It does not know that one model is approved for confidential data and another is not. |
| **Responses stream.** Answers arrive token by token over a long-lived connection. | Budgets and logs need the final token count, which only exists when the stream ends. |
| **Providers differ.** Parameters, names and error shapes vary. | A generic proxy forwards the differences to your apps. |
| **Repeats are common.** The same or similar question arrives again and again. | A URL-keyed cache cannot tell that two differently worded prompts mean the same thing. |

None of these is a flaw in your API gateway. They are simply outside its job.

## What an AI gateway adds

An AI gateway understands the thing it is carrying. In OpenProxyAI, every chat request passes through the same stages, in order: authentication, rate limits, policy, cache, routing, and logging ([request pipeline](/core-concepts/request-pipeline)). Concretely:

- **Limits in the units that matter.** Requests per minute, tokens per minute and dollars per day, at the organization, user and team level. A request over any limit is refused with a clear reason ([rate limiting and budgets](/core-concepts/rate-limiting-and-budgets)).
- **Policy on the content.** A model allowlist, blocked keywords, personal data detection and prompt-injection detection, in log-only mode first, or enforce mode when you are ready. A blocked request returns HTTP 446 with a one-sentence explanation a person can read ([policies and guardrails](/core-concepts/policies-and-guardrails)).
- **Routing that knows about models.** Weighted rotation across your provider keys, automatic failover when a key is unhealthy, and an optional data region per organization so requests only go where you approve ([provider routing](/core-concepts/provider-routing), [data residency](/security/data-residency)).
- **A cache that understands meaning.** Exact matches, plus a semantic tier for differently worded prompts ([caching](/core-concepts/caching), [how semantic caching works](/blog/how-semantic-caching-works)).
- **Streaming that stays accounted.** Cost and tokens are recorded even when a stream ends early ([streaming through a proxy](/blog/streaming-sse-proxy-design)).
- **An audit trail built for AI.** Each request is recorded with model, tokens, cost, policy decision and routing, and by default without prompt text ([audit logging](/security/audit-logging)).
- **Tool calls under the same rules.** If your agents use MCP tool servers, an MCP gateway puts them behind one endpoint with tool policies and an audit row per call ([MCP gateway](/guides/mcp-gateway)).

## Two layers, one path

The simplest way to see how they fit is to follow a request.

1. A product app calls your internal AI endpoint. The **API gateway** checks the caller's identity and applies edge limits.
2. It forwards the call to the **AI gateway**, which verifies the key, applies a team's token and dollar limits, runs policy, checks the cache, and picks a provider key.
3. The provider answers. The AI gateway records the cost and decision, then returns an OpenAI-shaped response.
4. The API gateway returns it to the caller.

Each layer answers its own question. The API gateway asks "may this caller reach this service?" The AI gateway asks "may this prompt go to this model, and what did it cost?"

## Do you need both?

| Situation | What to run |
|---|---|
| A single prototype calling one model | Neither. Call the provider directly. |
| Several apps or teams calling models | An AI gateway, even a small one |
| Many services, existing API platform, AI is one workload | Your API gateway at the edge plus an AI gateway for model traffic |
| Regulated data, audit questions, shared budgets | Both, with the AI gateway inside your network |

If you already have an API platform you like, you do not need to replace it. Add the AI-specific layer behind it. If you have no API gateway and only AI traffic, an AI gateway can be your first front door, since it handles authentication and limits too.

## What to do now

1. List who calls models today and with which keys.
2. Write down the two or three questions your API gateway cannot answer: spend by team, data sent to which model, which prompts were blocked.
3. Put an AI gateway behind your existing front door and route one team through it.
4. Start policy in log-only mode, read what it finds, then enforce.

## Good to know

Two layers means two places to configure limits. Keep request-rate limits at the edge and token and dollar limits in the AI gateway, so each number lives where it can be measured.

For a view of how a specific commercial API gateway adds AI features, see [OpenProxyAI vs. Kong AI Gateway](/blog/openproxyai-vs-kong-ai-gateway).

## Try it

The demo runs with Docker and needs no provider key. Console at http://localhost:5173.

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

If it is useful, star the repo or open an issue with the architecture you are trying to fit.

## Sources

- OpenProxyAI docs: [request pipeline](/core-concepts/request-pipeline), [rate limiting and budgets](/core-concepts/rate-limiting-and-budgets), [policies and guardrails](/core-concepts/policies-and-guardrails), [provider routing](/core-concepts/provider-routing), [audit logging](/security/audit-logging), [MCP gateway](/guides/mcp-gateway).
- This post describes general architecture and names no vendor claims.

These statements are based on OpenProxyAI's behavior at the post date.
