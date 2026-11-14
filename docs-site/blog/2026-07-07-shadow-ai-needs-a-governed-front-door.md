---
slug: shadow-ai-needs-a-governed-front-door
image: /img/blog/og/shadow-ai-needs-a-governed-front-door.png
title: "Only 30% can detect shadow AI. Give every AI call one governed front door"
tags: [security, product]
description: "A Smarsh and FTI Consulting study found 55% of enterprises deploying AI but only 26% with governance that keeps pace. See how one governed endpoint gives you visibility, policy and budgets across teams."
---

On July 7, 2026, Smarsh released its 2026 Enterprise AI Trends Study, conducted by FTI Consulting. Its headline: AI adoption is outpacing governance, and shadow AI is creating new blind spots. Only 30% of enterprises report comprehensive capabilities to detect and manage it. You cannot govern what you cannot see, and the quickest way to see AI use is to route it through one place.

{/* truncate */}

![A diagram showing team apps, internal tools and agents all calling one OpenProxyAI endpoint that records who called, which model, cost and policy result, then forwarding only to approved providers. A note cites the study: 30% report comprehensive shadow AI detection.](/img/blog/shadow-ai-needs-a-governed-front-door.svg)

## What the study found

These figures are from the Smarsh press release announcing the study.

| Finding | Figure |
|---|---|
| Enterprises actively deploying AI | 55% |
| Say governance frameworks are fully aligned with the pace of implementation | 26% |
| Report comprehensive capabilities to detect and manage shadow AI | 30% |

The release defines shadow AI as the use of unauthorized AI tools outside approved workflows. It says limited visibility into that use makes it harder to manage recordkeeping, supervision, privacy and regulatory obligations. It also notes that enterprise risk now spans AI agents, APIs, collaboration platforms and third-party applications.

A note on the source: Smarsh sells communications archiving and compliance software, and FTI Consulting ran the research. The press release does not state the sample size or fieldwork dates, so we quote only the three figures it prints.

## What it means

Shadow AI is rarely malicious. A team wants to summarize tickets, finds an API key, and ships. Nobody reviewed which model got the data, who is allowed to use it, or what it costs. Multiply by every team and you get the gap the study describes: lots of AI, little visibility.

Banning tools does not close the gap. It pushes use further out of sight. What works is an approved path that is easier than the workaround, and that records what goes through it.

## One governed endpoint

OpenProxyAI is an open-source, self-hosted gateway. Teams point their apps at one OpenAI-compatible endpoint and keep using the SDKs they already know. Behind it, every request passes the same checks.

**Visibility.** Every call is logged with who made it, which model answered, tokens, cost, and what the policy decided. The admin console and the analytics API break usage down by team, user, application key and model. Requests can also carry labels, so finance can charge back by department. By default the gateway keeps this metadata, not what people typed. Keeping a redacted sample of prompts for evaluation is an opt-in.

**Policy.** One organization policy applies to all traffic:
- a model allowlist, so only approved models answer;
- blocked keywords;
- personal data detection;
- prompt-injection detection;
- optional checks on responses.

New rules can run in log-only mode first, which records what would have been blocked without blocking it. Enforced blocks return HTTP 446 with a one-sentence explanation the caller can show a person.

**Data-aware routing.** A model registry records which models and keys may receive which class of data, in which region. Enforced, a request carrying confidential data cannot reach a model that is not cleared for it. See [data residency](/security/data-residency) and [provider routing](/core-concepts/provider-routing).

**Budgets and limits.** Spend and rate limits apply per user, per team and per organization, so a surprise bill shows up as a refused request and a webhook alert rather than an invoice.

**Agents and tools.** Agents that call tools go through the same front door. The MCP gateway applies allow and block lists, grants per team or key, and logs each tool call. See the [MCP gateway guide](/guides/mcp-gateway).

## A worked scenario

A bank-sized IT team wants to know what AI their business units use.

| Step | What happens |
|---|---|
| 1 | Platform team deploys the gateway and publishes one endpoint and a short onboarding note. |
| 2 | Each business unit gets a team, a service user and application keys with a budget. |
| 3 | The policy starts in log-only mode with a model allowlist and personal data detection. |
| 4 | After a few weeks the analytics show which teams use which models and where policy would have fired. |
| 5 | The team turns on enforcement, and the unapproved models and risky prompts stop at the gateway with a clear reason. |

## What to do now

1. Publish one approved endpoint and make it the easiest way to call a model.
2. Issue per-team keys with budgets, so every call has an owner.
3. Start policy in log-only mode and read the activity before enforcing.
4. Keep provider keys inside the gateway so apps cannot call providers directly with them.
5. Review usage by team monthly, and add the models people actually need to the allowlist.

## Where it fits

A gateway governs traffic sent through it. Tools that employees open in a browser with a personal account are outside its view, so pair it with your network and endpoint controls. The strongest setup makes the approved endpoint the default for anything built inside your company.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

Needs Docker, no provider key. Console at http://localhost:5173. If it helps, star the repo or open an issue.

## Sources

- Smarsh, [New Smarsh Research Finds Enterprises Are Deploying AI Faster Than They Can Govern It](https://www.smarsh.com/press-release/new-smarsh-research-finds-enterprises-are-deploying-ai-faster-than-they-can-govern-it) (July 7, 2026). Source of the 55%, 26% and 30% figures and the shadow AI definition.
- OpenProxyAI docs: [Policies and guardrails](/core-concepts/policies-and-guardrails), [Rate limiting and budgets](/core-concepts/rate-limiting-and-budgets), [Audit logging](/security/audit-logging), [Data residency](/security/data-residency), [MCP gateway](/guides/mcp-gateway), [Compliance templates](/security/compliance-templates).

These statements are based on the sources above and on OpenProxyAI's behavior at the post date. OpenProxyAI ships controls and templates, not certifications, and using it does not make an organization compliant.
