---
slug: inference-region-is-not-storage-region
image: /img/blog/og/inference-region-is-not-storage-region.png
title: "Inference region is not storage region: pin where your prompts are processed"
tags: [security, product]
description: "Where a model reads your prompt and where data sits at rest are two different questions. See how to pin the first with region-tagged keys and models, and which parts of the second stay in your hands."
---

"Our AI runs in the EU" can mean three things. The prompt is processed in the EU. Stored files and logs sit in the EU. Or just that the company's headquarters is. Auditors and customers care about the first two, and they are not the same control. This post separates them, shows how OpenProxyAI pins the processing region for every request in one place, and lists what you still decide yourself.

{/* truncate */}

![Two panels. Where the prompt is processed is set by organization region, region-tagged keys and models, and enforced by the gateway. Where data sits at rest depends on where the gateway is deployed and on provider-side storage settings.](/img/blog/inference-region-is-not-storage-region.svg)

## Two questions that sound like one

| Question | Plain meaning | Who controls it |
|---|---|---|
| **Inference region** | Where the model reads your prompt and produces the answer. | The key and model a request is sent to. |
| **Storage region** | Where data is kept at rest: files, logs, databases. | Where you deploy the gateway, and the provider's own storage settings. |

Providers draw the same line. OpenAI's data residency guide says plainly that "support for regional storage does not imply support for regional processing", and treats them as separate settings (source below). Our post on [OpenAI's per-request regional processing](/blog/openai-per-request-regional-processing) covers that announcement. The practical lesson is the same for every provider: ask both questions, and answer them separately.

## Pin the processing region at the gateway

If each team picks a region in its own code, your policy is as strong as the least careful call. OpenProxyAI moves the decision to the one place all traffic passes. There are three settings:

| Setting | Where | Values |
|---|---|---|
| Organization data region | The organization | US, EU or Asia-Pacific |
| Provider key region | Each provider key | US, EU, Asia-Pacific, or global (any region) |
| Model regions | Each entry in the model registry | One or more of the above |

An organization has exactly one region. A key tagged global can serve any organization, and a key tagged for a region serves organizations in that region.

**Key selection is always filtered.** Before a request leaves, the gateway considers only active keys whose region matches the organization or is global. Failover works inside that set, and so does a fallback model you name in a header. If every in-region key is unhealthy, the request fails with a clear error. It never quietly moves to a key in another region. An EU organization never uses a shared key set up for the whole gateway, so it must bring keys tagged for its own region.

**Model authorization adds a second filter.** With routing set to enforce, a request can only use a registered model that is cleared for it. A model whose regions do not include the organization's region, and that is not marked global, is excluded. The caller gets a 446 response with a plain sentence, such as "this model cannot serve this request under your organization's data-region setting". The gateway refuses. It does not swap in a different model.

When routing is enforced, the registry entry also fixes which key is used for the model: the key linked to it, never another key of the same provider.

## Roll it out without surprises

1. **Set the organization region.** The change is recorded in the audit log and applies to the next request.
2. **Tag your provider keys.** Add keys with the right region, or retag existing ones.
3. **Register models with their regions.** The list means "where this provider processes the data for this model".
4. **Run in log-only mode first.** The gateway records which requests it would have excluded for region, and lets them through. Read the results, fix tags, then switch to enforce.

A worked example: a company has an EU residency commitment for customer data. It tags one key for the EU and another as global, registers the EU-hosted model for the EU only, and keeps the global model for non-sensitive tasks. A support request is sent. The gateway considers only the EU key. If that key is rate-limited, the caller gets an error and a clear reason, not a silent trip to a global key. Developers wrote no region logic.

## What stays in your hands

This is the honest part, and it is the reason the two questions matter.

- **Where the gateway runs.** The gateway's own database and logs are where you deploy it. Put the deployment in the region you need. The [VPC-first post](/blog/vpc-first-architecture) and the [deployment guide](/guides/deployment) cover the options.
- **Provider-side storage.** Some endpoints keep data at rest, such as stored batch files. That is configured in the provider account. Check it separately from processing.
- **The tags themselves.** The gateway enforces the labels you set. It cannot confirm with the provider where processing really happens, so tag from the provider's own documentation and re-check when it changes.
- **Direct calls.** The rules cover traffic sent through the gateway. If an application can still call a provider directly, it can bypass them. Remove direct provider keys from applications.

One more effect to expect: for organizations outside the shared-key regions, the semantic cache is skipped, because the shared embedding step is not region-tagged. Exact-match caching continues to work.

## What to do now

- Write down, per data type, both answers: where it may be processed and where it may be stored.
- Set the organization region and tag every provider key.
- Register each model with the regions your provider documents.
- Use log-only mode for a week, then enforce.
- Remove direct provider keys from application code so the gateway is the only path.
- Add the provider-side storage setting to your vendor review.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

Needs Docker and no provider key. The console is at http://localhost:5173. Star the repo or open an issue about the regions you need.

## Sources

- [OpenAI data residency guide](https://developers.openai.com/api/docs/guides/data-residency): the storage versus processing distinction, quoted above.
- Product docs: [Data residency](/security/data-residency), [Provider routing](/core-concepts/provider-routing), [Provider keys](/api-reference/keys), [Errors and status codes](/api-reference/errors-and-status-codes), [Deployment](/guides/deployment).
- Related posts: [OpenAI adds per-request regional processing](/blog/openai-per-request-regional-processing), [Multi-region data residency](/blog/multi-region-data-residency), [VPC-first architecture](/blog/vpc-first-architecture).

These statements are based on the OpenAI page above and on OpenProxyAI's behavior at the post date. OpenProxyAI ships controls, not certifications, and using it does not make anyone compliant with a law or a contract.
