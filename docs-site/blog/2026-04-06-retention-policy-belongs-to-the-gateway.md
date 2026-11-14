---
slug: retention-policy-belongs-to-the-gateway
title: "Team-wide zero data retention shows who should own retention policy"
tags: [security, product]
description: "Vercel added team-wide Zero Data Retention to its AI Gateway on April 6, 2026. The news makes a bigger point: retention is a decision for whoever runs the gateway. Here is how OpenProxyAI keeps that decision in your hands."
---

When a security team asks "what happens to our prompts?", the honest answer has two parts. What does the gateway keep? And what does the model provider keep? On April 6, 2026, Vercel announced a team-wide Zero Data Retention setting for its AI Gateway, and it is a good moment to look at both. The announcement is a sign of where the market is going: retention is a policy that belongs to whoever runs the gateway, set once for the whole team, not a promise buried in each application.

{/* truncate */}

![A request path from your app through your gateway to a provider, with two cards showing what the gateway keeps and what the provider keeps.](/img/blog/retention-policy-belongs-to-the-gateway.svg)

## What Vercel announced

According to the [Vercel changelog entry](https://vercel.com/changelog/zero-data-retention-no-prompt-training-on-ai-gateway), published April 6, 2026:

- Admins can turn on Zero Data Retention (ZDR) for a whole team in the AI Gateway dashboard settings. The page says it applies to every request the team makes, "with no code changes required."
- With it on, requests are routed only to providers where ZDR agreements are in place. Each response includes metadata about which providers were considered and which were filtered out.
- Team-wide ZDR costs $0.10 per 1,000 requests on Pro and Enterprise plans. Per-request ZDR is free on those plans.
- Training opt-out is a related control. Turning on ZDR includes it automatically.

Notice the shape of the idea. Before, a developer had to remember a setting on each call. Now an admin sets the rule once, and every call inherits it. That is the right direction, because a rule that depends on every developer remembering it will eventually be missed.

## Why the gateway is the right owner

A gateway sees every request, so it is the one place where a retention rule can be both uniform and checkable. Three reasons:

| Question | If each app decides | If the gateway decides |
|---|---|---|
| Who sets the rule? | Every team, separately | One admin, once |
| How do you prove it? | Read every codebase | Read one policy and one audit trail |
| What happens to a new app? | It starts with whatever its author chose | It inherits the organization rule on day one |

There is a second part to the answer, and it is easy to miss. A gateway's own retention and a provider's retention are two different layers. You need a clear position on both.

## How OpenProxyAI handles the gateway layer

OpenProxyAI is a self-hosted gateway, so the records live in your database, under your retention rules. The defaults are cautious:

- **Metadata only by default.** OpenProxyAI normally keeps request metadata: model, tokens, cost, status and the policy decision. It does not keep what users typed.
- **Payload capture is off by default.** If you want real examples to test a prompt or model change, you can opt in to a redacted sample of prompts and answers. At the default setting it stores nothing. Only admins can change it, and the change is written to the admin audit log. Personal data such as email addresses, Social Security numbers and card numbers is replaced before anything is stored. Requests above a data-class ceiling you control are never kept, and neither are refused or failed requests. See [capturing traffic for evaluation](/guides/payload-capture).
- **Retention follows your plan.** Request logs and any captured samples expire on a schedule: 7 days on Community, 30 on Team, 90 on Business, 365 on Enterprise. See [audit logging](/security/audit-logging).
- **Audit rows are write-once.** Nothing in the request pipeline edits or deletes a log entry after it is written, so the record of what happened stays trustworthy.
- **Isolation is built in.** Captured rows sit behind the same row-level security as the rest of your data, so one organization cannot read another's.

The result is a short, honest answer for a questionnaire: by default the gateway stores usage metadata, not conversation text, and anything more is an admin decision that is logged.

## How OpenProxyAI helps with the provider layer

OpenProxyAI does not change what a provider keeps. That is governed by your agreement with the provider. What the gateway gives you is control over where each class of data is allowed to go:

- **Data classes and a model registry** let you decide which models may serve which kinds of data, so a sensitive prompt is only routed to models you have approved for it.
- **Routing stays inside that approved set,** including when a provider is unhealthy. See [provider routing](/core-concepts/provider-routing) and [data residency](/security/data-residency).
- **One endpoint for every provider** means the approval list lives in one place instead of in each application.

In practice, the flow is: choose providers whose terms you are comfortable with, record them in the registry, and let the gateway enforce the list.

## A worked scenario

A platform team supports three product squads. Legal asks, "Do we keep customer prompts anywhere?"

1. The team shows the default: metadata only, with capture off.
2. One squad wants to test a prompt change on real traffic, so an admin turns capture on for a small sample. The change appears in the admin audit log, personal data is replaced before storage, and the rows expire with the plan's retention window.
3. For the provider layer, the team points to the registry: only the approved models can serve internal data, and the contract terms for those providers are on file.

Legal gets a documented answer for each layer, and no squad had to change application code.

## What to do now

- Write down your retention position for both layers: the gateway and the provider.
- Check what your gateway stores by default. If you do not know, find out before the next security review.
- Make any capture of real prompts opt-in, sampled, redacted and time-limited.
- Keep a list of which providers your contracts allow for which data, and enforce it in one place.
- Make sure every change to a retention setting lands in an audit log.
- Read our posts on [SOC 2 for AI vendors](/blog/soc2-for-ai-vendors) and the [AI vendor security questionnaire](/blog/ai-vendor-security-questionnaire) to prepare your answers.

## Good to know

Gateway retention and provider retention are separate. Turning off capture in OpenProxyAI does not change what a provider does with a request it receives, so keep the provider terms and the registry up to date.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

This needs Docker and no provider key. The console is at http://localhost:5173. If it is useful, star the repo or open an issue to tell us what you would like to see.

## Sources

- [Team-wide Zero Data Retention and prompt training controls now on AI Gateway](https://vercel.com/changelog/zero-data-retention-no-prompt-training-on-ai-gateway), Vercel changelog, April 6, 2026. The announcement, behavior and pricing described above.
- [Capturing traffic for evaluation](/guides/payload-capture): what OpenProxyAI stores, and when.
- [Audit logging](/security/audit-logging): retention windows and write-once records.
- [Policies and guardrails](/core-concepts/policies-and-guardrails): the organization policy.

These statements are based on the sources above and on OpenProxyAI's behavior as of April 6, 2026.
