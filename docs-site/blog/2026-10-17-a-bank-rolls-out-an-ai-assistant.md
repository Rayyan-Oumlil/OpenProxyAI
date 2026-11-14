---
slug: a-bank-rolls-out-an-ai-assistant
title: "A hypothetical bank rolls out an AI assistant: one gateway, three teams, one plan"
tags: [product, security]
description: "A walkthrough of a made-up bank launching an internal AI assistant, showing what security, finance and platform teams each need from a gateway and how OpenProxyAI covers it. Not a customer story."
---

This is a hypothetical walkthrough, not a customer story. The bank, the teams and the numbers are invented to show how one rollout could use OpenProxyAI. Picture a mid-sized bank that wants an internal AI assistant for 2,000 employees. Three teams each have a veto: security worries about customer data, finance wants spend under control, and the platform team wants something it can run and support. The usual result is three separate tools and a long delay. A single gateway in front of every model lets all three get what they need from the same place.

{/* truncate */}

![One gateway between the assistant and the model providers, with security, finance and platform each controlling a different part: policy and data classes, budgets and analytics, keys and failover.](/img/blog/a-bank-rolls-out-an-ai-assistant.svg)

## The starting point

The bank's assistant is a chat app plus a few internal tools. Staff will ask about policies, summarize documents and draft emails. Some prompts will contain customer details, whether anyone intends it or not. The bank wants to use more than one model provider, keep keys out of application code, and be able to answer an auditor's questions later.

OpenProxyAI is an open-source, self-hosted gateway. It gives applications one OpenAI-compatible endpoint, and puts policy, routing, budgets and logging in front of every provider. Here is how each team uses it.

## What security gets

Security's question is "what can leave the building, and can we prove what did?"

- **Personal data checks.** A policy checks requests for personal data such as email addresses, card numbers and US Social Security numbers. It starts in log-only mode, where hits are recorded and nothing is blocked, so the team can see real false-positive rates. Then it moves to enforce.
- **Data classes.** Every request gets one of four classes, from public to secret. A request with a card number is raised to confidential automatically.
- **Model clearance.** Each model in the registry is cleared up to a certain class. Under enforcement, a confidential prompt can only reach a model cleared for it, through its own registered key. Otherwise the user gets a plain refusal they can understand. See [data classes](/blog/data-class-taxonomy-people-use) and [refusals that explain themselves](/blog/refusals-should-explain-themselves).
- **A starting template.** The finance compliance template sets blocked keywords, personal data detection and response checks in one call. It is a starting point, not a certification, and the team reviews the keyword list afterward.
- **Evidence.** Every request, policy decision and routing decision goes to an audit log that is not edited afterward. A compliance export can be scoped to a date range and a team.
- **Tenant isolation.** Data is separated by organization at the database level, as described in [row-level security by construction](/blog/row-level-security-by-construction).

## What finance gets

Finance's question is "who is spending what, and what stops a runaway bill?"

- **Budgets at several levels.** Daily dollar budgets for the organization and for individual users, and monthly budgets per team, plus request and token rate limits. Reaching one returns a clear HTTP 429 that names which limit was hit. See [budgets that fail closed](/blog/budgets-that-fail-closed).
- **An early warning.** A webhook fires when daily spend reaches 80 percent of the organization budget.
- **A dashboard.** Cost by model, team, API key and user, with a monthly burn-down against the budget.
- **Prices for every model.** Models are registered with prices, so costs are real figures, not guesses.
- **Cheaper repeat work.** Exact and semantic caching can answer repeated questions without a new provider call. Because shared caches deserve care, the team reads [the semantic cache post](/blog/semantic-cache-is-shared-memory) before turning it on for sensitive teams.

## What the platform team gets

The platform team's question is "can we run this, and what happens at 2 a.m.?"

- **Staff sign in with single sign-on.** An OIDC connector handles sign-in, and SCIM provisioning creates and deactivates users from the identity provider. New users start as viewers.
- **Keys out of code.** Provider keys are stored encrypted in the gateway and rotated without a restart. Applications hold only gateway API keys, one per service, each tied to a team. A leaked one can be revoked alone. See [a leaked key should be a nuisance](/blog/a-leaked-key-should-be-a-nuisance).
- **Failover.** If a provider key is erroring or rate limited, traffic shifts to healthy keys without the application knowing. Combined with data classes, failover only picks models that are allowed for that request.
- **Standard clients.** The existing OpenAI SDKs work by changing a base URL, and there are Python and TypeScript SDKs.
- **A console.** Teams, policies, provider keys, request logs and health in one place.

## The rollout in four steps

| Week | What happens | Who watches |
|---|---|---|
| 1 | Gateway runs with the demo data. Teams are created. SSO is connected. Policy is in log-only mode. | Platform |
| 2 | Pilot group of 50 uses the assistant. The team reads policy hits in analytics and tunes keywords. | Security |
| 3 | Budgets are set per team. The 80 percent webhook goes to a finance channel. | Finance |
| 4 | Policy and routing switch to enforce. The assistant opens to all staff. | All three |

Nothing in this plan needs a custom build. It is configuration, and each team can see its own part in the console.

## What to do now

- Name one owner per area: policy, budgets, platform.
- Start every new rule in log-only mode and read the hits for a week.
- Decide your data classes and which models each class may reach.
- Set team budgets before launch, and route the budget alert to someone who will read it.
- Give each application its own key tied to a team.
- Run a drill: revoke a key, and read the audit log for what it did.

## Good to know

Policy checks look at the prompt text, so keep keyword lists specific. A word like "account" will catch harmless requests. The built-in detector finds email addresses, US Social Security numbers and payment card numbers. Names, phone numbers and similar items need the optional stronger detector. Enabling personal data detection also needs a plan that includes it.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

Needs Docker, no provider key. Console at http://localhost:5173. Star the repo if this matches your rollout, or open an issue with the part your teams would need most.

## Sources

- [Policies and guardrails](/core-concepts/policies-and-guardrails): log-only and enforce, and what is checked.
- [Compliance templates](/security/compliance-templates): what the finance template sets, and what it does not.
- [Rate limiting and budgets](/core-concepts/rate-limiting-and-budgets): limits, 429 bodies and the 80 percent alert.
- [Provider routing](/core-concepts/provider-routing): weights and failover.
- [Configuring SSO](/guides/sso-and-scim) and [configuring SCIM](/guides/sso-and-scim): sign-in and provisioning.
- [Audit logging](/security/audit-logging): what is recorded, and retention by plan.

This walkthrough is fictional. The statements about OpenProxyAI are based on its docs and behavior as of October 17, 2026. OpenProxyAI ships templates and controls, not certifications, and using it does not make any organization compliant.
