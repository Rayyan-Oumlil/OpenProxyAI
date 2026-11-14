---
slug: eu-ai-act-from-2-august-2026
image: /img/blog/og/eu-ai-act-from-2-august-2026.png
title: "EU AI Act, 2 August 2026: what applies today and what moved to 2027"
tags: [security, product]
description: "The AI Act becomes applicable on 2 August 2026, with exceptions. A plain guide to what applies now, what the Digital Omnibus moved, and the records a gateway helps you keep."
---

2 August 2026 was the date many teams had circled for the EU AI Act. The European Commission's AI Act page now says the Act became applicable on that date, with exceptions, and that the rules for high-risk systems start later. So what actually changes for a team that uses AI models through providers? Mostly three things: transparency rules, supervision and enforcement, and the need to know where AI is used in your company. This post walks through the official timeline and shows the records a gateway helps you keep.

{/* truncate */}

![A five-row timeline of EU AI Act dates: February 2025, August 2025, August 2026 highlighted, December 2026, and December 2027 with August 2028.](/img/blog/eu-ai-act-from-2-august-2026.svg)

## The timeline, from the Commission's page

The Commission's AI Act page gives this application timeline. The Act entered into force on 1 August 2024 and became applicable on 2 August 2026, with some exceptions:

| Date | What starts |
|---|---|
| 2 February 2025 | Prohibited AI practices and AI literacy obligations |
| 2 August 2025 | Governance rules and obligations for general-purpose AI models |
| 2 August 2026 | The Act becomes applicable in general. The transparency rules apply. The AI Office and national authorities are responsible for supervising and enforcing the Act |
| December 2026 | A new prohibition on AI systems that generate non-consensual sexually explicit content or child sexual abuse material, introduced by the AI Omnibus |
| 2 December 2027 | Rules for high-risk use cases in the sensitive areas listed in Annex III |
| 2 August 2028 | Rules for high-risk AI embedded in regulated products (Annex I) |

If you read our earlier post on the provisional agreement, [EU AI Act: high-risk rules slip to 2027](/blog/eu-ai-act-digital-omnibus-deal), the high-risk dates in this table are the ones that deal pointed to. The Commission's page now presents them as the timeline. One detail is left out on purpose: how long systems already on the market have to meet marking rules. Check the regulation text for that before you rely on a date.

## What it means for a team using models from providers

**Transparency.** The Commission says the AI Act introduces disclosure duties so people know when they are dealing with a machine, for example a chatbot. Providers of generative AI have to make AI-generated content identifiable, and deep fakes and some published text must be clearly labelled. Whether these duties fall on you or on your provider depends on your role. The Commission has published guidelines on the transparency obligations and a code of practice on marking and labelling AI-generated content. Read them with your legal team.

**Enforcement.** From 2 August 2026, the AI Office and the authorities of the member states are responsible for supervising and enforcing the Act. The AI Office holds enforcement powers over general-purpose AI models.

**Literacy and inventory.** AI literacy obligations have applied since February 2025. A practical first step for both is simple: know which applications call which models.

**High-risk later, but plan now.** Examples on the Commission's page include tools used for employment decisions and credit scoring. When those rules start, they include logging of activity for traceability, documentation, and human oversight. A later start does not shrink the work. See [EU AI Act for engineers](/blog/eu-ai-act-for-engineers).

## How OpenProxyAI helps with the practical work

OpenProxyAI is an open-source, self-hosted gateway. Your applications send every model call to one OpenAI-compatible endpoint, so records and rules live in one place.

**An inventory that builds itself.** Every request is logged with who called, which model and provider served it, tokens, cost, the policy decision, the routing decision and whether the cache answered. You can tag traffic with labels per application, so the question "where do we use AI" has an answer from data, not from a survey. See [Audit logging](/security/audit-logging) and [Shadow AI needs a governed front door](/blog/shadow-ai-needs-a-governed-front-door).

**Rules on which model sees which data.** Each request has a data class. A registry of approved models records the highest class each model may receive, the regions it may serve, a risk rating and its retention terms. In enforce mode, only a model cleared for the request is used. See [Provider routing](/core-concepts/provider-routing) and [Multi-region data residency](/blog/multi-region-data-residency).

**Policy checks with a safe rollout.** Allowlists, blocked keywords, personal data detection and prompt-injection checks run before a request leaves. In log-only mode they record what they would do. In enforce mode a broken rule returns a clear refusal. See [Policies and guardrails](/core-concepts/policies-and-guardrails).

**Records that are hard to dispute.** Audit entries are written once and never edited, and logging happens after the response so it adds no delay. An export is available for reviewers.

## A worked scenario

A retailer runs a customer chatbot, an internal summarizer and a CV-screening pilot. It tags each application with a label. Using the audit data, it sees the chatbot is the only customer-facing one, which tells it where disclosure to users matters. It sets the CV pilot to a stricter data class and routes it only to models cleared for that class and region, because hiring tools sit in the Commission's high-risk examples. It leaves the summarizer on the default. Nothing here decides legal classification, but the team now has facts to bring to its counsel.

## What to do now

- List every application that calls an AI model and tag its traffic.
- Mark which ones face customers, so you know where disclosure matters.
- Read the Commission's transparency guidelines and the marking and labelling code of practice.
- Identify anything near the high-risk examples (hiring, credit, education) and tighten its data class.
- Turn on audit export so reviewers can read records without a ticket.
- Re-check the Commission page every quarter, because dates and guidance are still moving.

## Good to know

OpenProxyAI provides controls and records, not legal classification and not certification. Whether a use case is high-risk, and who carries each duty, is a legal question for your organization.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

Needs Docker, no provider key. Console at http://localhost:5173. If it helps, star the repo or open an issue with the records your regulator asks for.

## Sources

- [European Commission: AI Act](https://digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai): application timeline, transparency, enforcement, high-risk examples.
- Related: [EU AI Act: high-risk rules slip to 2027](/blog/eu-ai-act-digital-omnibus-deal), [EU AI Act for engineers](/blog/eu-ai-act-for-engineers), [Data residency](/security/data-residency).

These statements are based on the Commission's page as read for this post and on OpenProxyAI's behavior at the post date. This is not legal advice.
