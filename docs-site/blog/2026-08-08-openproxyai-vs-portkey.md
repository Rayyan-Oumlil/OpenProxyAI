---
slug: openproxyai-vs-portkey
title: "OpenProxyAI vs. Portkey: where self-hosting stops being free"
authors: [rayyan]
tags: [product, security]
description: Portkey publishes an open-source gateway you can run yourself. What sits behind a hosted app or an Enterprise plan is the control plane around it. Here is where that leaves the comparison.
---

Portkey is the most feature-comparable product to OpenProxyAI in this space: a unified gateway, guardrails, observability and governance. If you put the feature lists side by side, they overlap a lot. The difference that matters is which parts you can run yourself without paying, and which parts live in a hosted service.

{/* truncate */}

:::note Updated November 9, 2026
The first version of this post said Portkey is SaaS-first and that self-hosting is an Enterprise option. That left out Portkey's open-source gateway, which you can run yourself. The post below is rewritten from Portkey's [GitHub README](https://github.com/Portkey-AI/gateway) and [pricing page](https://portkey.ai/pricing) as of today.
:::

## Portkey's model

Portkey has two halves.

- **The gateway is open source.** It is MIT-licensed and runs from `npx` or Docker. Its README lists routing, retries, fallbacks, load balancing, guardrails and a basic dashboard. Portkey's pricing page shows this as the "Open Source" column, labelled "Host it Yourself".
- **The platform around it is hosted.** The README says the logging and observability features are "available on the hosted app". The pricing page lists a free Developer tier, a $49/month Production tier, and an Enterprise tier with SSO, VPC hosting, private cloud deployment and custom BAAs.

Two things were still moving when this was updated. Portkey's pricing page now announces "Portkey is now Prisma AIRS AI Gateway" and links to Palo Alto Networks. And its README says the core enterprise gateway is merging into the open-source project in a 2.0 release that is still pre-release. Treat which features are free as a moving target and check both pages before you decide.

## OpenProxyAI's model

OpenProxyAI is one self-hosted thing. It runs inside your VPC against your own Postgres and Redis, and the admin console, policy engine and audit log are part of what you deploy, not a hosted service beside it. There is no vendor-operated data plane, because there was never one to start with.

## What the real decision is

Both products can run inside your network, so "can it run in our VPC" does not separate them. The questions that do:

- **What do you get when you self-host?** With Portkey's open-source gateway you get the gateway, guardrails and a basic dashboard. Logging and observability, SSO, and the VPC-hosted platform are in the hosted app or the Enterprise plan. With OpenProxyAI you get the console and audit log in the same deployment.
- **Who operates the control plane?** If you take Portkey's hosted app, your request metadata goes through infrastructure Portkey operates, under a brand its pricing page now ties to Palo Alto Networks. If you stay on the open-source gateway, you run the pieces you need yourself.
- **How settled is the licence line?** Portkey is merging enterprise gateway features into open source, so today's split may not hold.

If your organization is comfortable with a managed service and wants the fastest path to a working gateway, Portkey's hosted tiers are a legitimate, well-built option, and its open-source gateway is a strong choice if all you need is the gateway. If "our prompts never touch infrastructure we don't control" is a requirement, both can meet it. OpenProxyAI is built to meet it by default, with the console and audit log included.

See [Deploying with Docker Compose](/guides/deploying-with-docker-compose) for what running it in your own VPC actually looks like.
