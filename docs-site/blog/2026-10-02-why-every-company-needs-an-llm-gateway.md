---
slug: why-every-company-needs-an-llm-gateway
image: /img/blog/og/why-every-company-needs-an-llm-gateway.png
title: "Why every company that uses LLMs needs a gateway"
tags: [architecture, product]
description: "Direct calls to model providers work fine for a prototype. At company scale they scatter keys, hide costs and leave no record. Here is what goes wrong, and how one gateway fixes each problem."
---

The first model call in a company is easy. Someone gets an API key, adds three lines of code and it works. The tenth team does the same thing, and so does the fiftieth. A year later the company has dozens of keys in dozens of places, no idea what the bill will be, no record of what was sent where, and an outage at one provider that takes half the products down. A gateway is the fix: one place that every model call passes through, so the rules, the limits and the records live in one spot instead of in every codebase.

{/* truncate */}

![Before: five applications each call three providers directly, with their own keys. After: five applications call one gateway with one key each, and the gateway calls the providers, applying policy, budgets, caching, failover and an audit log.](/img/blog/why-every-company-needs-an-llm-gateway.svg)

## What goes wrong with direct calls

| Problem | What it looks like |
|---|---|
| Keys everywhere | Provider keys sit in app settings, laptops and chat messages. Rotating one means finding every copy. |
| No shared rules | Each team decides for itself whether customer data may go to a model. Nobody can show the rule. |
| Surprise bills | Spend arrives as one invoice per provider, with no split by team, app or person. A loop in one script can burn a month of budget overnight. |
| No record | When a customer asks what an assistant did, the answer is in a dozen log formats, or nowhere. |
| Fragile uptime | A provider error or rate limit is every application's problem to handle, and most do not. |
| Lock-in | Switching a model means editing every application. |
| Agents with loose tools | Each agent connects to each tool server with its own credential, and nobody sees the calls. |

None of these are exotic. They are what happens by default when AI adoption outpaces the platform around it.

## One gateway, one answer to each

OpenProxyAI is an open-source, self-hosted gateway under the Apache-2.0 licence. Applications send requests to one OpenAI-compatible endpoint, so existing SDKs work by changing the base URL. Behind it, the gateway handles the rest.

**Keys stay in one place.** Provider keys are stored encrypted, or read from a secrets manager, and are never shown back. Applications get gateway keys that you can create, limit and revoke without touching a provider account. See [Authentication](/getting-started/authentication).

**One set of rules for every call.** An organization policy sets a model allowlist, blocked keywords, personal data detection and prompt-injection checks. In enforce mode a request that breaks a rule is refused with status 446 before any provider sees it. In log-only mode the same rules record what they would have done, so you can measure before you block. See [Policies and guardrails](/core-concepts/policies-and-guardrails).

**Data goes only where it is allowed.** Each request is given a data class. A registry of vetted models says which classes each model may receive and in which regions. See [Provider routing](/core-concepts/provider-routing) and [Data residency](/security/data-residency).

**Spend you can steer.** Budgets and rate limits apply per organization, team and user. When a limit is hit, the request is stopped with a clear status instead of a surprise invoice. Usage is attributed by team, key, model and label. See [Rate limiting and budgets](/core-concepts/rate-limiting-and-budgets).

**Fewer calls, fewer failures.** Exact and semantic caching answer repeated questions without a provider call. If a provider returns a rate limit or a server error, the gateway can retry on another key or provider that policy allows. See [Caching](/core-concepts/caching).

**A record of every call.** Each request, and each tool call from an agent, is logged after the response so logging never slows the answer. Admins can search it and export it. See [Audit logging](/security/audit-logging).

**Tools under the same roof.** The MCP gateway puts every tool server behind one endpoint and one key. Each tool call is checked against policy and written to the log, and grants decide who may call what. See [MCP gateway](/guides/mcp-gateway).

**Room to change your mind.** Because applications talk to the gateway, moving a workload to another model is a routing change, not a code change. Evaluations and experiments help you compare before you switch.

## A worked scenario

A company has a support assistant, a code helper and a finance summarizer. Before the gateway, each has its own key. After it:

1. Each app gets its own gateway key, tagged to its team. Finance has a lower daily budget.
2. The finance summarizer's traffic is classed as sensitive, so only the registry's approved models in the approved region can serve it. A prompt with a card number is refused.
3. A provider has an outage on Tuesday. The support assistant retries on an authorized alternative, and customers see slower answers instead of errors.
4. On Friday someone asks which team spent the most. The answer is one filtered view.

Nothing in the three applications changed except the base URL and the key.

## What to do now

- [ ] List where provider keys live today.
- [ ] Put one gateway in front of the first application and compare results.
- [ ] Set a budget per team before traffic grows.
- [ ] Start policy in log-only mode, read the results, then enforce.
- [ ] Move agent tools behind the MCP endpoint.
- [ ] Remove direct provider keys from applications once traffic is on the gateway.

## Good to know

A gateway only governs the traffic that goes through it. Its value grows when it is the only route to your providers, so remove direct keys from applications once they have moved. Policy checks run on the request text, so keep keyword lists specific.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

This needs Docker and no provider key. The console opens at http://localhost:5173. If it looks useful, star the repo or open an issue with what you want to see.

## Sources

- Internal: [Request pipeline](/core-concepts/request-pipeline), [Quickstart](/getting-started/quickstart), [Trust center](/security/trust-center).

These statements are based on OpenProxyAI's behavior at the date of this post.
