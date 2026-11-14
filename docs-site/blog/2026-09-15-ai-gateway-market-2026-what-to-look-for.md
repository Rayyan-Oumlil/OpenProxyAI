---
slug: ai-gateway-market-2026
title: "The AI gateway market in 2026: three releases, and what buyers should ask"
tags: [architecture, product]
description: "Envoy AI Gateway 1.0, Kong AI Gateway 2.0 and Bifrost 2.0 all shipped in 2026. What each announced, what the releases have in common, and six questions to ask before you pick a gateway."
---

An AI gateway is the one service that every model call, every prompt and every agent tool call passes through. In 2026 it stopped being a niche choice. Three well-known projects shipped major releases within about three months of each other: Envoy AI Gateway 1.0 on June 23, Kong AI Gateway 2.0 on September 1, and Bifrost 2.0 on September 15. If you are choosing a gateway now, the releases tell you what the market considers table stakes. This post summarizes each one, using the vendors' own announcements, and turns them into questions you can ask of any gateway.

{/* truncate */}

![Three 2026 gateway releases with their dates, above six questions a buyer should ask of any gateway.](/img/blog/ai-gateway-market-2026.svg)

## What each release announced

We read each announcement at its source and list only what it states.

| Release | Date | What the announcement says |
|---|---|---|
| Envoy AI Gateway 1.0 | 2026-06-23 | First stable, generally available release. One OpenAI-compatible API across 16 providers, an MCP gateway, endpoints for chat, embeddings, images and audio, OpenTelemetry tracing and token metrics, and quota-aware rate limiting. The core control-plane API is covered by a stability guarantee for the 1.x series. |
| Kong AI Gateway 2.0 | 2026-09-01 | General availability in Kong Konnect. MCP server bundling with access control so each caller sees only the tools it may use, modality-aware cost management (text, audio, image, video), new provider coverage, and policies that can key on the authenticated principal. |
| Bifrost 2.0 | 2026-09-15 | Governance with access profiles, projects with budgets, clustering, adaptive load balancing, a complexity-based router, guardrails for PII and prompt injection, signed audit logs, and edge governance for laptops and browsers. The announcement says it runs in your own infrastructure with no SaaS offering. |

Each project has a different home. Envoy AI Gateway is built on a CNCF project, Kong's release is delivered through its Konnect platform, and Bifrost describes itself as running entirely in your own infrastructure. Those origins shape what each is best at. We will not rank them, and you should be wary of anyone who does without running your workload.

## What the releases have in common

Read side by side, the three announcements converge on the same short list.

1. **One API in front of many providers.** All three put an OpenAI-compatible surface over several model vendors.
2. **Agent tool traffic is now in scope.** Envoy ships an MCP gateway. Kong bundles MCP servers behind one route. Bifrost adds virtual MCPs and MCP governance. MCP stands for Model Context Protocol, the standard way agents call tools.
3. **Cost is tracked by who and by what.** Kong keys cost on the principal and splits it by modality. Bifrost budgets by project. Envoy offers quota-aware routing.
4. **Identity matters.** Principals, access profiles and tenant-scoped routing all answer the same question: who is allowed to do what.
5. **Audit and observability are expected.** Tracing, token metrics and signed audit logs appear across the three.

If a gateway you are evaluating lacks one of these five, ask why.

## Six questions to ask any gateway

**1. Where does it run?** A gateway reads every prompt in flight. Ask whether it can run entirely inside your network, with your database and your secret store, and what it needs to reach outside.

**2. Who can use which model, and what happens when the answer is no?** Look for allowlists you can test, and a refusal that names the reason instead of a generic error.

**3. Which tools can an agent reach?** If agents call tools through the gateway, ask how access is granted per caller, not per shared token.

**4. What does a call cost, and who pays?** Ask for budgets per team and per key, a hard stop when one is reached, and a plan for models that have no published price.

**5. Who is allowed in?** Single sign-on, automatic user provisioning and per-user keys are the basics for an enterprise.

**6. What is the license, and who owns the code?** This one is easy to skip and hard to fix later. A gateway is infrastructure you will depend on for years. Ask whether you can read the source, run it without a vendor, and fork it if you must.

## How OpenProxyAI answers

OpenProxyAI is an open-source (Apache-2.0), self-hosted gateway. Here is how it maps to the six questions.

| Question | What OpenProxyAI offers |
|---|---|
| Where does it run? | In your infrastructure. An air-gapped mode turns off calls to third-party services the gateway does not need. Provider keys can be read from your own secret store. |
| Who can use which model? | A policy engine with model allowlists, keyword rules, PII checks and prompt-injection checks. Blocked requests return HTTP 446 with a plain reason. Data-class routing lets only registry-approved models serve sensitive requests. |
| Which tools can an agent reach? | An MCP gateway with per-caller grants, server pinning and scanning. See the [MCP gateway guide](/guides/mcp-gateway). |
| What does a call cost? | Budgets and rate limits per organization, team and user. A model without a listed price is charged a flat estimate so it still counts toward budgets. See [rate limiting and budgets](/core-concepts/rate-limiting-and-budgets). |
| Who is allowed in? | [SSO](/guides/configuring-sso) and [SCIM](/guides/configuring-scim), plus per-application API keys. |
| License and ownership? | Apache-2.0. You can read, run, modify and redistribute it. |

It also covers the common ground from the previous section: one OpenAI-compatible endpoint for every provider, failover between provider keys, exact and semantic caching, and an [audit log](/security/audit-logging) of every request.

## What to do now

- Write down your six answers before you watch a demo. Vendors lead with their strengths, so your list keeps the comparison honest.
- Ask each candidate to show a refusal, a budget stop and a provider failure in a trial environment.
- Check whether the gateway can run with no outbound connection other than to your model providers.
- Read the license file, not the marketing page.
- Run two gateways side by side on a copy of real traffic for a week. Ask your own questions of your own data.

## Good to know

Policy checks run on the prompt text the gateway can read, so keep keyword lists specific. A gateway governs the traffic that goes through it, so pair it with network rules that stop applications from calling providers directly.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

This needs Docker and no provider key. The console is at http://localhost:5173. If you find it useful, star the repo, and if something is missing for your evaluation, open an issue.

## Sources

- Kong, "Kong AI Gateway 2.0 GA", published 2026-09-01: https://konghq.com/blog/product-releases/kong-ai-gateway-2-0-ga
- Envoy AI Gateway v1.0 release notes, v1.0.0 dated 2026-06-23: https://aigateway.envoyproxy.io/release-notes/v1.0/
- Tetrate, announcement of Envoy AI Gateway 1.0, 2026-06-23: https://tetrate.io/press/envoy-ai-gateway-reaches-v1-0-establishing-the-open-source-standard-for-enterprise-ai-traffic
- Maxim AI, "Bifrost v2.0 is here", 2026-09-15: https://www.getmaxim.ai/bifrost/blog/bifrost-v2-0-is-here
- OpenProxyAI docs: [request pipeline](/core-concepts/request-pipeline), [policies and guardrails](/core-concepts/policies-and-guardrails), [provider routing](/core-concepts/provider-routing)

These statements are based on the sources above and on OpenProxyAI's behavior at the post date.
