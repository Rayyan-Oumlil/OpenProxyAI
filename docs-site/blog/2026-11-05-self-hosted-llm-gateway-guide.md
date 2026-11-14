---
slug: self-hosted-llm-gateway-guide
title: "Self-hosted LLM gateway: what it is, when you need one, how to choose"
tags: [architecture, product]
description: "A plain guide to the self-hosted LLM gateway: what it does, why teams run their own, what to expect from one, eight questions to evaluate it, and how to try OpenProxyAI in about five minutes."
---

An LLM gateway (also called an LLM proxy or AI gateway) is a service that sits between your applications and the language model providers they call, so that every request passes through one controlled point. A self-hosted LLM gateway is one you run yourself, in your own cloud account or data center, so prompts, keys and logs never pass through a vendor's servers. It gives you one endpoint for every model, plus policy, budgets, caching, failover and an audit trail in one place. This guide explains when that matters and how to choose one.

{/* truncate */}

![A self-hosted LLM gateway inside your network. Your applications call the gateway with their existing OpenAI SDK code. The gateway applies policy checks, budgets and limits, caching and failover, and writes an audit log. It forwards requests to a local model that stays inside the network and to cloud models using your own keys.](/img/blog/self-hosted-llm-gateway-guide.svg)

## What an LLM gateway is

Without a gateway, every team wires its own provider SDK and its own API key into its own code. Keys end up in many repositories. Nobody has one view of who calls which model, or what it costs. A rule such as "no customer data to this provider" lives in a wiki page, not in the system.

With a gateway, applications call one endpoint. The gateway checks the request, picks a model that is allowed to serve it, forwards it, and records what happened. Applications keep their existing code, because a good gateway speaks the same API as the provider SDKs. For the longer argument, see [why every company needs an LLM gateway](/blog/why-every-company-needs-an-llm-gateway).

## Why self-host it

Hosted gateways are convenient. Many teams still choose to run their own, for four reasons.

- **Your data stays in your network.** Prompts often contain customer records, contracts or source code. With a self-hosted gateway, the only outside hop is the one you choose: your own call to a model provider, or no outside hop at all when you use a local model.
- **Your keys stay yours.** Provider keys are stored in your deployment. Applications get gateway keys instead, so a leaked application key can be revoked without touching the provider account.
- **You own the audit trail.** Every request is logged in your database, under your retention rules, readable by your security team without a support ticket.
- **No per-request fee.** OpenProxyAI is open source under the Apache-2.0 license. You pay your model providers and your own infrastructure, and nothing per request to us.

The trade-off is real: you operate it. For the build-or-buy side of that decision, read [build vs buy](/blog/build-vs-buy-llm-gateway) and [what the license means](/blog/open-source-apache-2-for-a-gateway).

## What to expect from a gateway

Not every gateway covers the same ground. Here is a baseline, and how OpenProxyAI covers each item.

| Capability | Why it matters | How OpenProxyAI covers it |
|---|---|---|
| One OpenAI-compatible endpoint | Applications switch models without code changes | One endpoint for OpenAI, Anthropic, Azure, Mistral, Google and more |
| Policy checks | Stop bad prompts before they leave | Model allowlists, keyword rules, personal-data detection and prompt-injection checks |
| Data-class routing | Sensitive requests reach only approved models | Each request is classified, and each model has a clearance level |
| Budgets and rate limits | Predictable spend, no runaway loops | Limits per organization, team and user, returned as HTTP 429 |
| Caching | Fewer repeated calls, lower bills | Exact and semantic caching, both off until you enable them |
| Failover | One provider outage is not your outage | Traffic shifts to healthy keys, within the region and data rules you set |
| Audit log | Prove what happened | A record per request with the decision, model and data class; prompt text is not stored in it |
| Key management | Limit the damage of a leak | Provider keys encrypted at rest, apps use separate gateway keys, rotation without a restart |
| Identity | Access follows your directory | Single sign-on and SCIM provisioning |
| Tool access | Agents need governed tools too | An MCP gateway with per-tool grants |
| Admin console | Non-engineers can see and decide | A web console for keys, models, policy, usage and logs |

## How to evaluate one: eight questions

1. **Does it run where I need it?** Check that you can deploy it in your own cloud account or cluster, and that an air-gapped mode exists if your network requires it.
2. **Can I keep my existing code?** Ask for a demo with the official OpenAI SDK and only the base URL changed.
3. **What happens when a provider is down?** Look for automatic failover that respects your data rules, not a fallback that sends sensitive data somewhere it should not go.
4. **Can it keep sensitive data off certain models?** You want classification plus per-model clearance, with a refusal when no model qualifies.
5. **What happens when a budget runs out?** A good answer is a clear refusal, not a surprise invoice.
6. **What does the audit trail contain, and who can read it?** Ask what is stored, for how long, and whether prompt text is kept.
7. **How are keys handled?** Check where provider keys live, how they are rotated, and what a leaked application key costs you.
8. **Can I test a change before enforcing it?** Policy previews and a log-only mode let you see the effect on real traffic first.

Ask the vendor to show each one, not describe it. If the system is only described in slides, treat it as unproven.

## Run it in 5 minutes

You do not need a provider key to see it working. The demo stack starts its own database, a stand-in model endpoint and some sample traffic, so the console opens with data.

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

This needs Docker. When it is up, open the console at http://localhost:5173. The demo uses public demo credentials, so it is for evaluation only; for a real deployment see the [deployment guide](/guides/deployment) and [deploy in your VPC in minutes](/blog/deploy-in-your-vpc-in-minutes).

To connect your own application, change the base URL and key in your OpenAI SDK code, as shown in the [quickstart](/getting-started/quickstart) and in [migrate to a gateway in three lines](/blog/migrate-to-a-gateway-in-three-lines). If it is useful, star the repository, and open an issue if something is missing.

## Good to know

Policy checks run on the prompt text, so keep keyword lists specific. Start in preview or log-only mode, look at what would have been blocked, and enforce after that.

## FAQ

**Is an LLM gateway the same as an API proxy?**
A gateway is a proxy that understands model traffic. A plain API proxy forwards requests. A gateway also reads the request, applies policy and budgets, chooses among models, and records the decision. The word "LLM proxy" is often used for either, so check what a product actually does.

**Does a gateway add latency?**
It adds one network hop and a few checks, and caching can remove model calls entirely for repeated requests. Run it in the same network or region as your applications and measure with your own traffic, since model response time usually dominates.

**Can I use my existing OpenAI SDK?**
Yes. OpenProxyAI exposes an OpenAI-compatible API, so you change the base URL and the API key, with no new package. Streaming works too. See [OpenAI SDK and frameworks](/integrations/openai-sdk-and-frameworks).

**Does it work with local models?**
Yes. Any server that speaks the OpenAI-compatible API, such as vLLM or Ollama, can be registered as a provider with its own clearance level, and it then gets the same policies, budgets and audit logging as cloud models. Details are in [run local models through the same gateway](/blog/run-local-models-through-the-same-gateway).

**Is it open source?**
Yes. OpenProxyAI is released under the Apache-2.0 license, and you can read, run and modify the code. Details are in [open source under Apache-2.0](/blog/open-source-apache-2-for-a-gateway).

*Statements here are based on OpenProxyAI's documentation and behavior at the post date.*
