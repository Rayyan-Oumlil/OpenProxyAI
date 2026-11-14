---
slug: zero-data-retention-and-your-own-audit-log
image: /img/blog/og/zero-data-retention-and-your-own-audit-log.png
title: "Zero data retention at the provider, your own audit log at home"
tags: [security, product]
description: "A provider's no-retention promise covers what they keep. Your audit log covers what you can prove. Here is what OpenProxyAI stores by default, how retention follows your plan, and why capture is off until you opt in."
---

"Do you keep our prompts?" is really two questions. What does the model provider keep after it answers? And what does your own platform keep? A zero data retention arrangement with a provider answers the first. It says nothing about the second, and it does not give you a record of what your teams actually sent. You need both layers to be clear, and you need them to fit together. This post separates them, shows what OpenProxyAI keeps on your side, and lists what to write down for each.

{/* truncate */}

![Two layers: the provider layer, governed by your agreement and recorded in the model registry, and your layer, where the gateway keeps metadata by default, capture is opt-in and retention follows your plan.](/img/blog/zero-data-retention-and-your-own-audit-log.svg)

## The problem

Zero data retention, often shortened to ZDR, is an agreement about what a provider does after it handles your request. The exact terms differ between providers and between plans, so the document that matters is your own contract. Your platform cannot read that contract from the outside, and it cannot change it.

Teams fall into two traps. The first is to treat the provider promise as the whole story: "we have ZDR, so nothing is kept". Your own platform may keep logs, caches, files and conversation history, and a questionnaire will ask about them. The second is the opposite: keep everything "just in case", so that your own log becomes the sensitive data store you were trying to avoid.

For a longer look at why retention belongs to whoever runs the gateway, see [Team-wide zero data retention shows who should own retention policy](/blog/retention-policy-belongs-to-the-gateway).

## Layer one: what the provider keeps

This is set by your agreement with the provider. What the gateway can do is make the decision visible and keep it in one place.

- **The model registry records it.** Each registered model can carry how long the provider keeps prompts (empty if you do not know), whether the provider trains on your data, the regions where it processes data, and a risk rating. Changes to these entries are written to the admin audit log.
- **Data classes decide who sees what.** Routing can limit sensitive requests to the models you have cleared for that level, and refuse the request when none is cleared. See [Provider routing](/core-concepts/provider-routing).
- **Provider-side state is off by default.** For the Responses endpoint, the gateway asks the provider not to store the response, and it refuses requests that ask for provider-held state unless an admin allows it.

## Layer two: what you keep

Your own records exist to answer "what happened, and who decided?" without holding the text of every conversation.

| What | Default | Notes |
|---|---|---|
| Request log | Metadata only | Model, provider, tokens, cost, status and the policy decision. Not prompts or answers. |
| Payload capture | Off | An admin can opt in to a sample rate. Personal data is replaced before anything is stored. |
| Retention of the request log | By plan | 7 days on Community, 30 on Team, 90 on Business, 365 on Enterprise. |
| Admin audit log | Always on | Who changed which setting, with before and after values and no secrets. Not archived by the retention job. |
| Batch files | Kept for a short period | Deleted after 7 days by default, or at once on request. |
| Conversations | Off | If enabled, stored with personal data replaced, and deleted after the plan's retention window of inactivity. |

A few details are worth knowing when you answer a questionnaire.

**Capture is narrow even when it is on.** It keeps a sampled share of delivered requests, with personal data replaced. It never keeps a request above the sensitivity ceiling your operator sets (internal by default), and never keeps one that was refused or failed. Captured rows expire with the plan's retention. See [Capturing traffic for evaluation](/guides/payload-capture).

**The record cannot be quietly edited.** The gateway's database role cannot delete rows from the request log or the admin audit log, so an entry shows what happened. Request log rows past the retention window are archived and hidden from default views and exports. If your framework needs a longer history, export on a schedule or stream events to your SIEM. Details in [Audit logging](/security/audit-logging) and [Telemetry and SIEM](/guides/telemetry-and-siem).

**You can prove what was sent without storing it.** When conversations are on, each answer has a record with a SHA-256 hash of the exact messages sent to the model. An auditor can check a claim about what a provider received without a second copy of the text.

## Putting the two layers together

| Question from legal or an auditor | Where the answer lives |
|---|---|
| Does the provider retain our prompts? | Your agreement, recorded per model in the registry |
| Which models may see confidential data? | The registry and your data class settings |
| Did anyone change that last quarter? | The admin audit log, with before and after |
| What did we send, and what did policy decide? | The request log: model, tokens, decision, reason code |
| Do we keep prompt text? | No by default. Yes only if an admin enabled capture or conversations, and that change is logged |
| How long do we keep it? | The plan's retention window, longer only if you export it |

## A worked scenario

A security team gets a vendor questionnaire from a customer. Two lines matter.

1. **"Does any third party retain customer prompts?"** The team opens the registry. Their approved models list the retention each provider has agreed to, and the contracts are on file. They filter the audit log for registry changes in the last year to show the list has not drifted.
2. **"Do you retain prompts yourselves?"** The team shows the default: metadata only, capture off. One squad had enabled a 10 percent sample to evaluate a prompt change. The admin audit log shows who enabled it and when, and the sample expires on the plan's schedule.

Both answers are specific, and both can be checked.

## What to do now

1. Write down what each provider you use retains, from your contracts, and record it per model in the registry.
2. Decide which data classes may go to which models, and enforce it with routing.
3. Check what your platform stores today: request logs, captured samples, batch files, conversations.
4. Keep capture off unless you have a named purpose. When you turn it on, use a small sample and a short window.
5. Match your retention window to your framework. If it is longer than your plan keeps, schedule an export.
6. Keep the admin audit log in view for reviews. Every retention-related setting change lands there.

## Good to know

The registry records what you have been told about each provider. It is information for your reviews, and it does not verify the provider's practices. The provider's retention remains a matter of your agreement with them. Retention and compliance templates are separate: a template records a retention target next to the policy but does not change how long logs are kept, and templates are configurations, not certifications.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

Needs Docker, no provider key. Console at http://localhost:5173. Open the request logs and look at what a row contains: the metadata is there, the prompt text is not. If it helps, star the repo or open an issue.

## Sources

- OpenProxyAI docs: [Audit logging](/security/audit-logging), [Capturing traffic for evaluation](/guides/payload-capture), [Data residency](/security/data-residency), [Conversations](/guides/conversations), [Other endpoints](/api-reference/other-endpoints), [Batches](/api-reference/batches), [Compliance templates](/security/compliance-templates).
- On this blog: [Team-wide zero data retention shows who should own retention policy](/blog/retention-policy-belongs-to-the-gateway), [An audit trail your auditor can read](/blog/an-audit-trail-your-auditor-can-read), [AI vendor security questionnaire](/blog/ai-vendor-security-questionnaire).

These statements are based on OpenProxyAI's behavior and docs as of October 24, 2026.
