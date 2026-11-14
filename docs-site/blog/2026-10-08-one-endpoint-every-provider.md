---
slug: one-endpoint-every-provider
image: /img/blog/og/one-endpoint-every-provider.png
title: "One endpoint for every model provider, and no code change to swap models"
tags: [product, architecture]
description: "Point your existing OpenAI SDK at one gateway and reach every provider. Weighted routing, automatic failover and a model registry let you change models without touching application code."
---

Most teams do not start with one model provider and stay there. A new model is cheaper, a region needs a different vendor, a provider has a bad afternoon. Each change tends to mean new SDKs, new keys scattered across services, and a release for every application that calls a model. There is a simpler shape: your applications talk to one endpoint, and the gateway decides which provider serves each request. This post shows how that works in OpenProxyAI and what it saves you.

{/* truncate */}

![An application with one base URL and one gateway key talks to a gateway that applies policy and budgets, a model registry, weighted routing and failover, then reaches provider A, provider B, or a backup or local model.](/img/blog/one-endpoint-every-provider.svg)

## The problem: provider details leak into every app

When each application holds its own provider credentials, three things go wrong over time.

- **Keys spread.** Every service that calls a model needs a provider key. Rotating one means finding all of them.
- **Switching is a project.** Moving a workload from one model to another means code changes, review and a deploy per application.
- **Outages are your problem.** If one provider is down or rate-limiting you, each application needs its own retry and fallback logic.

## One endpoint, one key

OpenProxyAI exposes an OpenAI-compatible API. If your code already uses an OpenAI SDK, you change the base URL and use a gateway key instead of a provider key. Nothing else in the application changes. The Python and TypeScript SDKs and common frameworks work the same way. See the [quickstart](/getting-started/quickstart).

Behind that endpoint you register the provider keys your organization holds: OpenAI, Anthropic, Azure, Mistral, Google and many more. Applications never see them. The list of models an application can call comes from the standard model-list call, and it reflects the keys you have configured, not a fixed global list.

## Routing across keys and providers

You can register several keys for the same provider, for example two accounts with different rate-limit tiers, or keys tagged for different regions. Each key has a weight, and traffic is shared in proportion. See [provider routing](/core-concepts/provider-routing).

This gives you practical controls with no application involvement:

| You want to | You do this | The application |
|---|---|---|
| Spread load across two accounts | Register both keys, set weights | Unchanged |
| Ramp a new key up slowly | Start with a low weight, raise it | Unchanged |
| Retire a key | Switch it off in the console or the API | Unchanged |
| Keep EU traffic in the EU | Tag keys by region and set residency | Unchanged |

## Failover without client code

If a key is rate-limited, returning errors or failing health checks, the router moves traffic to the remaining healthy keys. The application sees one successful response and does not need its own retry logic. A caller can also name a backup model for a single request, and cap how many fallback attempts are allowed.

There is one rule that makes this safe for sensitive work. When data-class routing is enforced, every fallback must come from the set of models your registry has approved for that request. A backup that is not approved is ignored, and if nothing approved is available the request is refused with HTTP 446 instead of going somewhere else. See [provider routing](/core-concepts/provider-routing) and the [request pipeline](/core-concepts/request-pipeline).

## The model registry: decide once, change in one place

The model registry is where your organization lists the models it has vetted. For each model you record the most sensitive data class it may receive, its regions, a risk rating, how long the provider keeps data, whether it trains on data, and which provider key serves it. You manage it in the admin console.

![The Model registry page of the admin console listing models with provider key, maximum data class, regions, risk, retention, trains on data and status.](/img/blog/console-model-registry.png)

The registry also lets applications ask for a capability instead of a model. A request that names a capability is served by the cheapest approved model that has it, and the cheapest is chosen by lowest cost first, then lowest risk. When a better or cheaper model arrives, you add it to the registry and the next requests can use it. When a model is retired or disabled, you switch its entry off. The applications keep sending the same request.

Capability routing needs data-class routing to be in enforce mode, because it relies on the registry to know what is allowed.

## A worked example

A support tool calls a capability named for summarizing tickets. Today the cheapest approved model with that capability is Model A.

1. A cheaper vendor releases Model B. Your security team reviews it and adds it to the registry with a data class of internal, a US region and its retention period.
2. You preview what would happen with the policy preview, which shows which model would serve a sample request and why others were ruled out. No provider call is made and no budget is used.
3. The next real request routes to Model B because it is cheaper and approved.
4. A month later Model B has an incident. You switch its entry off. Requests go to Model A again. The support tool was never redeployed.

Every decision is recorded in the audit row and shown on the request trace, with a plain-language line saying what was authorized and why a model was ruled out.

## What to do now

- List the places your code names a provider SDK directly. Plan to replace them with the gateway's base URL.
- Move provider keys out of applications and into the gateway, or into your secret store, and read them from there.
- Register at least two keys for your most important provider, so failover has somewhere to go.
- Add your vetted models to the registry, starting with log-only routing so you can see decisions before enforcing them.
- Decide which capabilities your applications need and name them.

## Good to know

Capability routing and the registry apply to chat and embeddings requests. Conversations name a specific model on purpose, so a conversation never switches model behind your back.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

This needs Docker and no provider key. The console is at http://localhost:5173. If it helps, star the repo, or open an issue if a provider you rely on needs better coverage.

## Sources

OpenProxyAI documentation, read at the post date:

- [Provider routing](/core-concepts/provider-routing)
- [Request pipeline](/core-concepts/request-pipeline)
- [Provider keys API](/api-reference/keys)
- [Quickstart](/getting-started/quickstart)
- [Managing policies](/admin-console/managing-your-organization)

These statements are based on OpenProxyAI's behavior at the post date.
