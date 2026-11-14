---
slug: fedramp-20x-ai-and-consolidated-rules
title: "FedRAMP 20x and the 2026 Consolidated Rules: a plan for AI platform teams"
tags: [security, product]
description: "FedRAMP 20x asks for continuous evidence, not paperwork, and the Consolidated Rules for 2026 are now public. Here is what that means for teams running LLMs near federal work, and which controls to build first."
---

FedRAMP 20x is the federal program's push to judge cloud services by measured results instead of point-in-time paperwork. On June 25, 2026, the public changelog for the Consolidated Rules for 2026 opened, giving everyone one reference for the 20x requirements. FedRAMP also ran an AI prioritization effort that fast-tracked a short list of conversational AI services. If your team builds AI features for agencies, or runs AI tools inside a regulated boundary, the direction is clear: you will be asked to show evidence, continuously, of how AI traffic is controlled.

{/* truncate */}

![Four evidence themes from FedRAMP 20x, identity, data separation, continuous evidence and analytics, each paired with a gateway control you run yourself](/img/blog/fedramp-20x-ai-and-consolidated-rules.svg)

## What FedRAMP published

Everything below comes from fedramp.gov.

- **FedRAMP 20x** is described as an approach that focuses on whether a provider's security decisions produce results, measured continuously, rather than control-by-control audits at a point in time. Providers set their own security goals and agencies use the evidence to choose services.
- **Certification classes.** Class A, B and C are available, and Class D (High) is planned for a later phase. The first pilot, for Low impact, focused on Key Security Indicators. A Moderate impact pilot ran from November 18, 2025 through March 2026.
- **Consolidated Rules for 2026** is a public reference that brings rules, definitions, timelines and guidance together for agencies, cloud providers, assessors and advisors. The site keeps a changelog, whose first entry is dated June 25, 2026, and offers machine-readable source data. Because the rules are still evolving, check the changelog before relying on any detail.
- **AI prioritization.** The 2025 AI prioritization initiative began in August 2025 and completed in April 2026. It was open to AI cloud services that give federal workers access to conversational AI for routine use. A service had to meet five conditions, including enterprise features such as single sign-on, SCIM provisioning, role-based access control and real-time analytics, plus data separation so that customer data does not leave the customer environment without authorization.

## What it means for AI platform teams

You are probably not a cloud provider seeking certification. You are more likely a team that builds on top of one, or that runs AI tools for an organization with government work. Even so, the 20x ideas apply to you in three ways.

1. **Evidence beats documents.** A policy PDF saying "we do not send sensitive data to unapproved models" is weak. A log showing every request, which rule applied and where it went is strong.
2. **The AI prioritization criteria are a good checklist.** Single sign-on, automated user provisioning, roles, analytics and data separation are things any security reviewer will ask about for an AI tool.
3. **Boundary matters.** The more of your AI traffic that stays inside infrastructure you control, the easier it is to describe your boundary honestly.

## How OpenProxyAI helps

OpenProxyAI is an open-source, self-hosted LLM gateway. It runs inside your own cloud account against your own database, so the infrastructure that sees your prompts is infrastructure you choose. Mapping it to the themes above:

| Theme | What you get |
|---|---|
| Identity | Sign in through your identity provider with OpenID Connect. SCIM creates and deactivates users automatically from Okta or Microsoft Entra ID. Roles are set by admins in the console, and provisioning can never grant admin |
| Data separation | Four data classes and a model registry. With routing enforced, a model only serves requests it is cleared for. Provider keys can be tagged with a region, and routing stays inside approved regions even during failover |
| Continuous evidence | Every request is logged with its policy decisions, routing decision and cost. Entries are write-once. Export a review file for a date range, scoped to a team or policy if you want |
| Analytics | Spend, cache and policy activity dashboards, a structured query API for admins, and a webhook when daily spend nears the budget |

For government-style deployments there are two more options. The government policy template sets classification-marking keywords, a wider list of personal data types (including IP addresses and locations), prompt-injection checks and response redaction, and records a three-year retention target. For on-premises or isolated environments, an air-gapped mode turns off optional outbound calls that the gateway does not strictly need.

### A worked scenario

An integrator supports an agency analytics team that wants an internal drafting assistant.

1. The integrator deploys the gateway in the agency-approved environment and connects the identity provider. Staff sign in with their agency accounts, and leavers are deactivated by the identity provider, which takes effect on their next request.
2. The registry lists only the models the team has approved, each cleared to a data class. Provider keys are tagged with approved regions.
3. The government template is applied in log-only mode for two weeks. The team reviews what it would have flagged, trims keyword lists, then switches to enforce.
4. At review time the team exports the log for the quarter. The export shows requests, decisions, routes and costs, so the conversation is about evidence, not recollection.

## What to do now

- Read the Consolidated Rules overview and decide which class, if any, applies to a service you provide.
- Write your AI boundary down: where prompts are processed, where logs live, which providers can be reached.
- Move AI sign-in and offboarding to your identity provider if they are manual today.
- Define data classes and clear each model for the classes you are willing to send it.
- Turn on audit export and pick a review cadence.
- Subscribe to the FedRAMP changelog so rule changes do not surprise you.

## Good to know

OpenProxyAI does not hold a FedRAMP authorization and the government template is a policy configuration, not a certification. Your authorization covers your system and your boundary. The template does not change how long logs are kept, which follows your plan (7, 30, 90 or 365 days), so export logs yourself if a requirement is longer. Region tagging and air-gapped mode are separate settings you turn on deliberately.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

Needs Docker and no provider key. The console is at http://localhost:5173. Star the repo or open an issue if there is a control your review needs.

## Sources

- [FedRAMP 20x](https://www.fedramp.gov/20x/): approach, classes and phases.
- [Consolidated Rules for 2026](https://www.fedramp.gov/2026/): the public reference.
- [Consolidated Rules changelog](https://www.fedramp.gov/2026/changelog/): first entry dated June 25, 2026.
- [FedRAMP AI prioritization](https://www.fedramp.gov/ai/): criteria, August 2025 start and April 2026 completion.
- Product docs: [Compliance templates](/guides/compliance-templates), [Configuring SSO](/guides/configuring-sso), [Configuring SCIM](/guides/configuring-scim), [Data residency](/guides/data-residency), [Audit logging](/security/audit-logging), [Trust center](/security/trust-center).

These statements are based on the sources above and on OpenProxyAI's behavior at the post date.
