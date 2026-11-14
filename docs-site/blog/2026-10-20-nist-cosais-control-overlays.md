---
slug: nist-cosais-control-overlays
image: /img/blog/og/nist-cosais-control-overlays.png
title: "NIST's AI control overlays: what exists, and what your team can do now"
tags: [security, product]
description: "NIST is building SP 800-53 overlays for securing AI systems, with use cases for assistants and agents. Here is what the project page shows today and how a gateway turns the same ideas into controls you can run."
---

Security teams know NIST SP 800-53 as the catalog of controls behind many audits. NIST is now building overlays on top of it for AI systems, including one use case for single agents and one for multi-agent systems. The project page lists the use cases and a few early drafts, but it does not yet give a date for the first public draft. That gap is where teams get stuck: wait for the final text, or start. This post shows what exists on 20 October 2026 and which controls you can put in place now, in one place, without waiting.

{/* truncate */}

![Three NIST overlay use cases (generative AI assistant, single agent, multi-agent) each mapped to a gateway control: policy rules, per-agent keys and grants, and one audit trail.](/img/blog/nist-cosais-control-overlays.svg)

## What NIST has published so far

The project is called COSAiS, short for Control Overlays for Securing AI Systems. An overlay is a set of tailored guidance applied on top of the SP 800-53 control catalog for a specific situation. According to NIST's project page:

| Item | Detail |
|---|---|
| Goal | A series of implementation-focused overlays for securing AI systems using SP 800-53 controls |
| Focus | Confidentiality, integrity and availability, including components such as training and test data, model weights and configuration settings |
| Proposed use cases | Using generative AI (assistant or large language model); using and fine-tuning predictive AI; using AI agents, single agent; using AI agents, multi-agent; security controls for AI developers |
| Concept paper | Released for comment on 14 August 2025 |
| Annotated outline | A discussion draft for the predictive AI use case, released 8 January 2026, with initial feedback requested by 13 February 2026 |
| Initial public draft | No date is given on the page |
| Naming | The page records that, on 20 October 2026, the project was renamed "Control Overlays for Super Intelligence Systems (COSIS)", following a 29 September 2026 executive order on terminology. Previously issued documents were not altered |

So the picture today is a clear structure and early drafts, not final control text. NIST also says the overlays will draw on its secure software development guidance for generative AI (SP 800-218A), a draft AI guidance document (AI 800-1) and its adversarial machine learning taxonomy (AI 100-2 E2025).

## What this means for a platform or security team

Two points are safe to plan around.

1. **The use cases mirror how teams actually deploy AI.** An assistant that employees chat with, a model that is fine-tuned, an agent that calls tools, several agents that call each other. Each one needs the same basics: control who can call what, control what data goes where, and keep a record.
2. **The 800-53 families that matter are familiar.** Think access control, audit and accountability, and system and information integrity. If your program already maps controls to these families, AI traffic is another system to cover, not a new discipline.

You do not need the final overlay text to start on those basics. You need one place where AI calls pass through, so the same control applies to every application.

## How OpenProxyAI gives you that one place

OpenProxyAI is an open-source, self-hosted gateway. Your applications send every model call to one OpenAI-compatible endpoint. The controls below apply to all of them.

**Policy controls for the assistant use case.** An organization policy sets a model allowlist, blocked keywords, personal data detection and prompt-injection checks. In enforce mode, a request that breaks a rule is stopped before it reaches a provider, with a plain explanation. In log-only mode, the same rules run and record what they would have done, so you can measure first. See [Policies and guardrails](/core-concepts/policies-and-guardrails).

**Data classes for what goes where.** Each request carries a data class, from public to secret. A registry of approved models records the highest class each model may receive and the regions it may serve. With routing enforced, a model that is not cleared for the request is never used. See [Provider routing](/core-concepts/provider-routing) and [Data residency](/security/data-residency).

**Per-agent identity for the agent use cases.** Give each agent its own API key with named permissions, an optional team and an expiry date. Revoke one key and only that agent stops. Tool calls through the MCP gateway are checked against grants, so an agent reaches only the tools it was given. See [API keys](/api-reference/keys), [MCP gateway](/guides/mcp-gateway) and [MCP grants beat shared tokens](/blog/mcp-grants-beat-shared-tokens).

**One audit trail for accountability.** Every request is recorded with who called, which model and provider served it, tokens, cost, the policy decision and the routing decision. Entries are written once and never edited, and logging happens after the response so it adds no delay. An export is available for reviewers. See [Audit logging](/security/audit-logging) and [An audit trail your auditor can read](/blog/an-audit-trail-your-auditor-can-read).

## A worked scenario

A team plans an internal agent that reads support tickets and drafts replies. Before launch it creates a dedicated key for that agent with only the permissions it needs and a six-month expiry. It sets the traffic to a data class of confidential and routes it only to registry models cleared for that class. It turns on personal data detection in log-only mode for a week, reads the hits, then switches to enforce. When a reviewer later asks what this agent did last Tuesday, the answer is a query on the audit trail filtered by that key.

None of this is the overlay itself. It is the evidence-producing groundwork that any overlay will ask for.

## What to do now

- List your AI use cases and sort them into the five NIST use cases above.
- Route all AI traffic through one gateway so controls and records are in one place.
- Create one key per agent, with the smallest permissions and an expiry.
- Define data classes and approve models per class and region.
- Run policy in log-only mode, review, then enforce.
- Watch the NIST project page so you see the first public draft when it appears.

## Good to know

OpenProxyAI ships configurations and controls, not certifications. Applying them does not make an organization compliant with any NIST publication. See [Compliance templates](/security/compliance-templates) and [Compliance templates, not badges](/blog/compliance-templates-not-badges).

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

Needs Docker, no provider key. Console at http://localhost:5173. If it helps, star the repo or open an issue with what your assessors ask for.

## Sources

- [NIST CSRC: SP 800-53 Control Overlays for Securing AI Systems (COSAiS, now COSIS)](https://csrc.nist.gov/projects/cosais): use cases, dates, rename notice.
- Related: [NIST AI agent standards initiative](/blog/nist-ai-agent-standards-initiative), [Policies and guardrails](/core-concepts/policies-and-guardrails), [Audit logging](/security/audit-logging).

These statements are based on the NIST project page as read on 20 October 2026 and on OpenProxyAI's behavior at that date.
