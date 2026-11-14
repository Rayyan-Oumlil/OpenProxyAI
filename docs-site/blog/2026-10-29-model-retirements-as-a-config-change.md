---
slug: model-retirements-as-a-config-change
image: /img/blog/og/model-retirements-as-a-config-change.png
title: "Model aliases and retirements: make deprecation a config change"
tags: [product, engineering]
description: "Providers retire models on their own schedule. If your apps ask for a capability and your registry decides which approved model serves it, a retirement becomes an edit in one place, not a code change in every service."
---

Every model you depend on has an end date, even if it is not published yet. When the date comes, a service that hard-codes the model name starts failing, and the fix is a code change, a review and a deploy in every repository that mentions it. That is a lot of work for what should be a routine event. The way out is to move the decision about which model serves a request out of application code and into one governed place. OpenProxyAI gives you three levers for that, and this post is honest about what each one does and does not do.

{/* truncate */}

![Two ways to name a model. A hard-coded name makes each service a migration. A capability request lets the registry choose among approved models, so retiring a model is one registry edit. A disabled model name gets a clear refusal.](/img/blog/model-retirements-as-a-config-change.svg)

## What the gateway does not have

The gateway does not have a free-form alias table where you map `fast-model` to any name you like. Do not build your plan on one. What it has instead is a model registry, capability-based requests and per-request fallback. They cover the same need, and they add something an alias table lacks: every model that can serve a request has been vetted first.

## Lever 1: ask for a job, not a model

The model registry lists the models your organization has approved. Each entry records the most sensitive data class it may receive, the regions it processes data in, a risk rating, how long the provider retains data, whether it trains on data, a cost tier and a list of capabilities such as code generation or summarization. It is linked to a provider key, and an admin manages it in the console.

A caller can then ask for a capability in the model field instead of a model name:

```json
{"model": "cap:CODE_GENERATION", "messages": [{"role": "user", "content": "Write a unit test."}]}
```

The gateway picks the cheapest authorized model that has that capability, then the lowest risk among equals. If your policy uses feedback as a quality signal, it can prefer the better-rated model when ratings show a clear gap. The response headers say which model answered and why. See [switching models mid-conversation](/blog/switching-models-mid-conversation) for how model choice interacts with history.

Retirement then becomes:

1. Register the replacement as its own entry, with its own data class, regions and retention.
2. Give it the same capabilities as the model it replaces.
3. Disable the old entry.

No service changes. Requests for the capability are then served by the replacement, and the response headers show it.

## Lever 2: the registry decides what is allowed

Registry entries are not inherited. A replacement is a new data-handling decision, because its provider may keep prompts longer or process them elsewhere. So a new entry must be cleared on its own terms, and a model that is not cleared for a request's data class never serves it, however similar its name looks. This is the reason a registry is safer than an alias: a rename cannot quietly widen where your data goes. (If you also use a model allowlist in the policy, add the replacement there too.)

Routing has two modes worth knowing. In preview, the gateway records which registry model would serve each request and refuses nothing, so you can see the effect of a registry change before it matters. In enforce, each request is restricted to models cleared for its data class. Capability requests need enforce mode, and enforce needs at least one enabled model with an active provider key.

## Lever 3: fallback, set by the caller

For a model that is failing or about to disappear, a caller can name a backup in a documented header, and set the most fallback attempts for the request. If the first model fails, the backup is tried. Under enforced routing the backup is ignored unless it is authorized for that request, so a fallback cannot become a way around your data rules.

Be clear about the limit: this header is chosen by the caller, so it lives in application code or a shared client. It helps availability. It is not a central switch. For that, use the capability request and the registry. Failover across provider keys of the same provider is separate and automatic, as covered in [provider failover explained](/blog/provider-failover-explained).

## When an old name is still hard-coded

Some caller will still send the exact old name. If the model is disabled in the registry and routing is enforced, that call is refused at the gateway with a readable message and HTTP 446, instead of an unclear provider error. The refusal is in the request log, so you can find the straggler and its owner by filtering on the model. Disabling does not silently redirect a call that names a model, and that is deliberate, because a silent swap would change how data is handled without a decision.

## Prove the replacement before the switch

A newer model is not automatically better on your prompts. Before you disable the old entry:

- Run an evaluation of the candidate on a dataset from your own traffic, with a cost cap.
- Or send a share of live traffic through an adaptive experiment, which moves traffic toward the variant users rate better.
- Compare cost per request in the analytics, since a model with a higher price can still cost less if it needs fewer retries.

The post on [testing a model change before you ship it](/blog/test-a-model-change-before-you-ship-it) walks through this, and the [evaluating changes](/admin-console/evaluating-changes) page shows where it lives in the console.

## A worked scenario

An internal coding helper asks for `cap:CODE_GENERATION`. Two models carry that capability: model A and, cheaper and newer, model B, which was added last week and has been in a test experiment since. Because B is cheaper and cleared for the same data class, it already serves most requests. The provider of A announces a retirement date. The platform team disables A in the registry a week early. The helper keeps working, the log shows B answering, and one old script that hard-coded A returns a 446 refusal that names the model. Its owner fixes one line.

## What to do now

- [ ] List the exact model names your services send. The request log can be filtered by model.
- [ ] Register approved models with honest data class, region and retention values.
- [ ] Move shared services to capability requests where the choice of model is not a product decision.
- [ ] Put retirement dates from provider pages in your own calendar, and disable the old entry before the date.
- [ ] Switch routing to preview first, then enforce.
- [ ] Add a fallback header in shared clients where availability matters.

## Good to know

Capability routing picks the cheapest authorized model with the capability, so register candidates deliberately: a cheap model with the wrong capability tag would be chosen. Callers that name an exact model keep that exact model, which is the right behavior for pinned evaluations.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

Needs Docker, no provider key. Console at http://localhost:5173. If it helps, star the repo, and if you want a different way to name models, open an issue.

## Sources

- [Provider routing](/core-concepts/provider-routing) and [Data residency](/security/data-residency): the registry fields and key weighting.
- [Managing your organization](/admin-console/managing-your-organization): routing preview and enforce.
- [Chat completions](/api-reference/chat-completions): the fallback and retries headers.
- [API overview](/api-reference/overview): the route model and route reason response headers.
- [Errors and status codes](/api-reference/errors-and-status-codes): the 446 refusal.
- [Evaluating changes](/admin-console/evaluating-changes) and [Adaptive experiments](/guides/adaptive-experiments).
- On this blog: [test a model change before you ship it](/blog/test-a-model-change-before-you-ship-it), [one endpoint, every provider](/blog/one-endpoint-every-provider), [data class taxonomy people use](/blog/data-class-taxonomy-people-use).

These statements are based on the sources above and on OpenProxyAI's behavior as of 2026-10-29.
