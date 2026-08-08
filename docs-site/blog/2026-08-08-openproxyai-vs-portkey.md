---
slug: openproxyai-vs-portkey
title: "OpenProxyAI vs. Portkey: SaaS-first vs. self-hosted-first"
authors: [rayyan]
tags: [product, security]
description: Portkey and OpenProxyAI cover similar ground on features — gateway, guardrails, observability. The real difference is which deployment model is the default, not an upgrade.
---

Portkey is the most feature-comparable product to OpenProxyAI in this space — a unified gateway, real guardrails (including PII redaction), observability, and enterprise governance. If you put the feature lists side by side, they overlap a lot. The difference that actually matters is architectural, not a checklist item: which deployment model is the default, and which one you have to pay to unlock.

{/* truncate */}

## Portkey's model

Portkey is SaaS-first. The default way to run it is as a managed, multi-tenant service — your traffic goes through infrastructure Portkey operates. VPC hosting and fully air-gapped deployment exist, but as part of the Enterprise tier, not the starting point. For a lot of teams that's a perfectly reasonable trade: less infrastructure to run, a managed service handling scaling and uptime.

## OpenProxyAI's model

OpenProxyAI is self-hosted from the first tier up. It runs inside your VPC against your own Postgres and Redis from day one — there's no multi-tenant data plane to opt out of later, because it was never the default to begin with.

## Why the ordering is the actual decision

Both products can, in the end, run inside your infrastructure. But "self-hosted is available at the top tier" and "self-hosted is what you start with" are different conversations with your security team. The first one asks them to evaluate a SaaS vendor's data handling practices *unless* you pay for the option to avoid it. The second one means there's no SaaS data-handling question to evaluate in the first place — the software runs where you tell it to, from the free trial onward.

If your organization is comfortable with a managed multi-tenant service and wants the fastest path to a working gateway, Portkey's SaaS-first model is a legitimate, well-built option — the model catalog and guardrail feature set are genuinely strong. If "our prompts never touch infrastructure we don't control" is a requirement rather than a nice-to-have, that's the gap OpenProxyAI is built to close by default.

See [Deploying with Docker Compose](/guides/deploying-with-docker-compose) for what running it in your own VPC actually looks like.
