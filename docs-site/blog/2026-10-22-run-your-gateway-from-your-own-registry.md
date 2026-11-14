---
slug: run-your-gateway-from-your-own-registry
title: "Run your gateway from your own registry and upgrade on your schedule"
tags: [security, engineering]
description: "The gateway sees every prompt, so it should run only the code you chose. Mirror images into your registry, pin by digest, and upgrade when you decide. OpenProxyAI is Apache-2.0 and built for it."
---

The gateway sits on the path of every prompt and every provider key. That makes its container image one of the most sensitive things you run. Pulling a moving tag from a public registry at deploy time means your next rollout runs whatever that tag points to that day. A better habit is simple: copy the image into a registry you control, pin it by digest, and upgrade as a planned change. OpenProxyAI is open source under Apache-2.0 and is designed to be run this way.

{/* truncate */}

![Upgrade flow: a release is mirrored into your internal registry, pinned by digest, tested in staging and then promoted to production on your schedule.](/img/blog/run-your-gateway-from-your-own-registry.svg)

## The problem with moving tags

A tag such as latest is a label that the publisher can move. It is convenient for a demo and risky for production, for three reasons:

- **Unplanned changes.** A pod restart can pull a different image than the one you tested.
- **No clear record.** After an incident, "which build was running" should have a precise answer.
- **Outside dependency at deploy time.** If a public registry is slow, rate limited or unreachable, your rollout or your recovery stalls.

A digest fixes the first two. It is a content hash of the image, so the same digest is always the same bytes. A private mirror fixes the third.

## A routine that works

1. **Choose a release.** Read the release notes and the changelog. Decide when you will take it.
2. **Mirror it.** Copy the image into your internal registry under a version tag that you set and never move. Do the same for the console image if you run it.
3. **Record the digest.** Your registry reports it when you push. Store it in your deployment repository.
4. **Pin by digest.** Kubernetes accepts an image reference with a digest, so what runs is exactly what you mirrored. If your tooling builds the reference from a repository and a tag, have your pipeline resolve the tag to a digest when it renders the manifest, or enforce digests with an admission policy.
5. **Test in staging.** Run your checks against the pinned image, including a model call, a blocked request and an audit log query.
6. **Promote.** Move the same digest to production. Keep the previous digest so a rollback is a one-line change.

Back up the database before you promote. Each rollout runs the database migrations for the new version first, and a backup makes the rollback story honest.

## Why Apache-2.0 matters here

The license is part of the operating model, not just a legal footnote.

| You can | Why it helps |
|---|---|
| Run it on your own infrastructure | Prompts, logs and provider keys stay in your environment. |
| Read the code that handles your data | Your security team can review it instead of trusting a description. |
| Build the image yourself from the source | You can produce it in your own pipeline and your own base image policy. |
| Mirror and archive every version you run | You are never dependent on a vendor's registry staying available. |
| Fork or patch if you must | You are not blocked on a vendor roadmap for an urgent change. |

The repository includes a container build for the gateway and a Helm chart for Kubernetes, and the chart takes the image repository and tag from your values. The deployment guide says to pin a tag rather than use latest for real deployments. For the full license story, see [own your gateway](/blog/own-your-gateway) and [build versus buy](/blog/build-vs-buy-llm-gateway).

## Upgrades are yours

OpenProxyAI does not update itself. There are no background auto-updates, and the air-gapped guidance spells out a manual path: obtain the new image, move it into the isolated network, run the migrations, deploy, and restart with your existing settings. In a connected environment the same discipline applies. A new version arrives when your pipeline brings it, not when a vendor pushes it.

For organizations that review changes before adopting them, this is the point. Read what changed, test it against your own policies, and schedule it like any other platform upgrade.

## Keep the supporting pieces local too

The gateway needs a database and a cache. Run those from your own managed services, as the production values in the chart do. The optional analytics store and the console can also come from your registry. If you run in an isolated network, the documented air-gapped mode turns off the optional hosted integrations, and it needs a license key set at startup. See the deployment guide for details.

## What to do now

1. Create a repository path in your internal registry for the gateway and console images.
2. Mirror the release you tested. Never use a moving tag in production.
3. Store the digest in version control next to your deployment configuration.
4. Add a staging step that exercises a model call, a policy block and an audit query.
5. Back up the database before each upgrade and keep the previous digest for rollback.
6. Put the upgrade on a calendar. Quarterly is a reasonable default, sooner for security fixes.

## Good to know

This post describes a deployment practice you apply with your own registry and pipeline tools. The demo images that the project publishes are tagged for every commit and are meant for trying the product, not as production release channels.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

Needs Docker, no provider key. Console at http://localhost:5173. Star the repo or open an issue if you want a release or mirroring pattern documented.

## Sources

- OpenProxyAI docs: [Deployment](/guides/deployment), [Environment flags](/getting-started/environment-flags), [Data residency](/security/data-residency), [Trust center](/security/trust-center).
- On this blog: [Deploy in your VPC in minutes](/blog/deploy-in-your-vpc-in-minutes), [VPC-first architecture](/blog/vpc-first-architecture), [Build versus buy](/blog/build-vs-buy-llm-gateway), [Own your gateway](/blog/own-your-gateway).
- License: the Apache License 2.0 text that ships in the repository.

These statements are based on OpenProxyAI's behavior at the post date.
