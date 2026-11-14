---
slug: own-your-gateway
title: "Open source gateways and consolidation: why owning yours matters"
tags: [architecture, product]
description: "Portkey open-sourced its gateway in March 2026, and Palo Alto Networks closed its acquisition of Portkey in May. What it means for teams that put one service in front of every model call."
---

Two announcements in the AI gateway space landed two months apart. On March 24, 2026, Portkey announced that its gateway is fully open source. On May 29, 2026, Palo Alto Networks announced it had closed the acquisition of Portkey. Both are facts worth knowing, and neither is a reason to pick or avoid any product. They do point at a question every platform and security lead should answer: who controls the service that sees all of your prompts?

{/* truncate */}

![A dashed boundary labeled your infrastructure holds the apps, an Apache-2.0 gateway, the audit database and the secret store. Model providers or local models sit outside the boundary.](/img/blog/own-your-gateway.svg)

## What was announced

**March 24, 2026.** Portkey's press release says it launched a newly unified Gateway and made it completely open source. The release lists governance, observability, authentication and cost controls as part of what is now open source, and says the same for its MCP gateway, which governs how AI agents call tools. The company states that governance and cost controls previously needed a separate subscription.

**May 29, 2026.** Palo Alto Networks' press release says it "closed the acquisition of Portkey, a pioneer in AI Gateways." It states the plan to make Portkey the core AI gateway for its Prisma AIRS security platform, combined with agent identity security and AI observability.

We are reporting what the two companies said. The purchase price is not disclosed in the sources we read, and we do not speculate about what either company will do next.

## What it means for you

A gateway is unusual infrastructure. It reads every prompt, holds or brokers your provider credentials, and decides what is allowed. That makes three things matter more than they would for a typical library.

**1. Who owns it can change.** Software companies get acquired, repositioned and bundled. That is normal. The question is what you hold when it happens. If the gateway runs in your environment under a license that lets you keep using and modifying the code, a change of ownership is news, not an incident.

**2. Open source is a spectrum.** "Open source" can mean the core is open and key features are not, or that the code is open but the license limits what you can do with it. Read the license text and the feature list together.

**3. Where it runs decides what leaks.** A gateway hosted by someone else sees your prompts. One that runs in your own network sees them only inside your boundary. For regulated teams, this is often the deciding factor, more than any feature.

## Why Apache-2.0 and self-hosting

OpenProxyAI is open source under Apache-2.0 and designed to run in your own infrastructure. Here is what that gives you in practice.

| Concern | What you get |
|---|---|
| Vendor change | You hold a copy of the code under a license that allows use, modification and redistribution, including for commercial purposes. The license also includes a patent grant from contributors. |
| Data location | Prompts and answers pass through a gateway you run. Request metadata lands in your own Postgres database. Keeping redacted prompt samples is opt-in. |
| Credentials | Provider keys can be stored encrypted by the gateway or read from your own HashiCorp Vault or AWS Secrets Manager. With the latter two, the gateway keeps no copy. See [provider keys from Vault](/guides/secrets-from-vault). |
| Isolation | Postgres row-level security keeps each organization's rows separate. See [row-level security](/security/row-level-security). |
| Air-gapped sites | An air-gapped mode turns off calls to third-party services the gateway does not strictly need. |
| Audit | Every request produces an [audit record](/security/audit-logging) in your own database. |

One endpoint serves every provider, so moving between model vendors does not require changing application code. The gateway, not the application, holds the relationship with each provider.

## A simple scenario

A team runs a gateway as a hosted service from a vendor. The vendor is acquired and the roadmap changes. The team now has to ask: is our data handled the same way, does the price change, and do we have a migration plan? With a self-hosted open-source gateway, the same news raises a different question: do we want to adopt the new features? The data, the keys and the audit trail never left.

## What to do now

- List what your gateway sees: prompts, credentials, user identities. Decide where each should live.
- Read the license. Check that it lets you run the code without the vendor and modify it.
- Check which features need a paid or hosted component.
- Keep your application code on a standard API (OpenAI-compatible), so any gateway can be swapped in or out.
- Ask vendors what happens to your deployment if ownership changes.

## Good to know

Self-hosting means you operate the service: upgrades, backups and capacity are yours. The demo below runs on one machine. For production, start from the [quickstart](/getting-started/quickstart).

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

This needs Docker and no provider key. The console is at http://localhost:5173. If it is useful to you, star the repo, or open an issue with what you would need to move your own gateway in-house.

## Sources

- Portkey press release, "Portkey's Gateway is Now Fully Open Source, Processing over 1 Trillion Tokens Every Day", GlobeNewswire, 2026-03-24: https://www.globenewswire.com/news-release/2026/03/24/3261574/0/en/Portkey-s-Gateway-is-Now-Fully-Open-Source-Processing-over-1-Trillion-Tokens-Every-Day.html
- Palo Alto Networks press release, "Palo Alto Networks Completes Acquisition of Portkey to Secure AI Agents", 2026-05-29: https://www.paloaltonetworks.com/company/press/2026/palo-alto-networks-completes-acquisition-of-portkey-to-secure-ai-agents
- Apache License 2.0 text (patent grant in section 3, trademarks in section 6): https://www.apache.org/licenses/LICENSE-2.0.txt
- OpenProxyAI docs: [quickstart](/getting-started/quickstart), [data residency](/guides/data-residency), [trust center](/security/trust-center)

These statements are based on the sources above and on OpenProxyAI's behavior at the post date.
