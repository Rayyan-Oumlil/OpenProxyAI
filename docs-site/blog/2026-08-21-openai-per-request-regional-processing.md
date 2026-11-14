---
slug: openai-per-request-regional-processing
title: "OpenAI adds per-request regional processing: what it means for your region policy"
tags: [security, product]
description: "OpenAI API customers can now choose regional processing for a single request. Storage region and inference region are different things, so here is how to keep your own rules in front of both."
---

On August 21, 2026, OpenAI's API changelog announced that API customers can now select regional processing for an individual request. That is useful news for teams with data residency rules, because the choice no longer has to be made once for a whole project. It also raises a practical question: who decides, request by request, which region a prompt may go to? If the answer is "each developer, in their own code", the policy is only as strong as the least careful call. This post explains what OpenAI announced and how a gateway keeps your region rules in one place.

{/* truncate */}

![A request enters the gateway, is labeled with a data class, and is matched against approved regions and cleared models. Only keys in an approved region are candidates, even during failover.](/img/blog/openai-per-request-regional-processing.svg)

## What OpenAI announced

From the OpenAI API changelog entry dated August 21, 2026, and OpenAI's data residency guide:

- **The change.** API customers can select regional processing for an individual request. You do it by using a prefixed domain with an API key from a project that has Global geography.
- **Existing rules still apply.** The entry says existing eligibility, data retention control, endpoint and model support requirements still apply.
- **Storage and processing are separate.** The guide says regional storage means customer content is stored at rest in the selected region when an endpoint needs to keep it. Regional processing means inference runs in that region. It states that "support for regional storage does not imply support for regional processing".
- **A caveat OpenAI states plainly.** For a region that does not support regional processing, the guide says OpenAI may process and temporarily store customer content outside that region to deliver the service.

We are not repeating region lists or price details here. They change, and OpenAI's own pages are the place to check them before you rely on them.

## Why this matters: two regions, two questions

A residency requirement usually hides two questions.

1. **Where is data stored?** This covers things like stored batch inputs and outputs.
2. **Where is the prompt processed?** This is the inference region, where the model reads your text.

A team can answer the first and forget the second. Per-request selection makes the second one easier to get right, and also easier to get wrong, because the region is now a per-call decision.

The safer pattern is to treat the region as policy, not as a coding choice. Decide the rule once, enforce it where all traffic passes, and let applications stay simple.

## How OpenProxyAI keeps the rule in one place

OpenProxyAI is an open-source, self-hosted gateway. Applications call one OpenAI-compatible endpoint. Region rules live in the gateway.

| Control | What it does |
|---|---|
| Region-tagged provider keys | Each provider key carries a region label: US, EU, Asia-Pacific or global. |
| Approved regions per organization | The organization lists the regions its traffic may use. Routing drops every key outside that list before a request is sent. |
| Failover that stays inside the lines | If every in-region key is unhealthy, the request fails. It never falls back to an out-of-region key. |
| Data classes | Each request gets one of four classes, from public to secret, from your default, a header the caller sends, and any personal data the detector finds. |
| Model registry | Each model has a highest class it may see and the regions it is approved for. Under enforcement, a model serves a request only if it is cleared for the request's class and the organization's region. |
| Plain refusals | A request that no approved model can serve gets HTTP 446 and a sentence the end user can read. |

So the question "may this prompt go to that region?" is answered by the gateway, in the same way for every application. The audit log records the routing decision, so you can show which model and key served a request. The earlier post on [data classes](/blog/data-class-taxonomy-people-use) covers the scheme, and [failover can leak data](/blog/failover-can-leak-data) explains why the failover rule matters.

## A worked example

An organization has EU residency rules for customer data. The platform team does the following.

1. Registers two provider keys, tagged EU and global.
2. Sets the organization's approved regions to EU.
3. In the model registry, clears the model that runs on the EU key for confidential data and does not clear the global one.
4. Turns routing on in log-only mode for a week, then enforces.

A support app sends a prompt that contains a payment card number. The detector classifies it as confidential. Routing considers only the EU key, and only models cleared for confidential data. If the EU key is rate-limited, the request fails with a clear refusal rather than quietly using the global key. A marketing script sending public text can still use any approved key. The developers wrote no region code at all.

## What to do now

- Write down which data classes have a region rule, and which have none.
- Tag every provider key with the region that matches how its provider project is configured.
- Set approved regions at the organization level, then check the registry for each model.
- Run routing in log-only mode first and read what it would have refused.
- Decide how your apps should behave on a 446 or a failed in-region request, and test it.
- Re-read OpenAI's changelog entry and data residency guide for your endpoints and models, since support varies by endpoint and model.

## Good to know

The region label on a key is something you set. It should match how that provider project and endpoint are configured, so verify the provider side whenever you add a key. OpenProxyAI enforces which keys are eligible, and the provider governs what happens inside its own service.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

Needs Docker, no provider key. Console at http://localhost:5173. If it is useful, star the repo or open an issue about the region rules you need.

## Sources

- [OpenAI API changelog](https://developers.openai.com/api/docs/changelog): the entry dated August 21, 2026 on regional processing for an individual request.
- [OpenAI data residency guide](https://developers.openai.com/api/docs/guides/data-residency): storage versus processing, and the per-request setup.
- [Data residency](/guides/data-residency): region-tagged keys and approved regions in OpenProxyAI.
- [Provider routing](/core-concepts/provider-routing): how keys are chosen and how failover behaves.
- [Provider keys API](/api-reference/provider-keys): the region label on a key.
- [Errors and status codes](/api-reference/errors-and-status-codes): the 446 response and its explanation.

These statements are based on the OpenAI pages above and on OpenProxyAI's behavior at the post date. OpenProxyAI ships controls, not certifications, and using it does not make anyone compliant with a law or a contract.
