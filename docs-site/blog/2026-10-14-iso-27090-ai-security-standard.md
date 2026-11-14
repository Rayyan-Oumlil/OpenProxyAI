---
slug: iso-27090-ai-security-standard
image: /img/blog/og/iso-27090-ai-security-standard.png
title: "ISO/IEC 27090 is out: security guidance for AI systems, and the runtime layer"
tags: [security, product]
description: "ISO published ISO/IEC 27090 on 14 October 2026, guidance on threats to AI systems themselves. See what it covers and which runtime controls a gateway gives you to act on it."
---

ISO published ISO/IEC 27090 on 14 October 2026. It is guidance on a question security teams keep asking: how do you protect the AI system itself, not just use AI to defend something else? Auditors and customers tend to adopt ISO language fast, so expect to see its threat names in questionnaires soon. This post explains what the standard is, what it does not claim to be, and which of its ideas you can turn into running controls at the gateway layer.

{/* truncate */}

![Model traffic from apps and agents passes through the gateway, where five runtime controls apply (scoped keys, rate and budget limits, guardrails, tool controls, audit trail) before reaching model providers.](/img/blog/iso-27090-ai-security-standard.svg)

## What happened

| Fact | Detail |
|---|---|
| Standard | ISO/IEC 27090:2026, "Cybersecurity, Artificial intelligence (AI), Addressing security threats and compromises to AI systems" |
| Date | First edition published 14 October 2026, according to ISO's record |
| Nature | Guidance, not requirements you can be certified against |
| Focus | Protecting AI systems themselves. It is not about using AI to defend other technology |
| Audience | Organizations of any size that develop or use AI, not only generative AI or chatbots |
| Threats named | Data poisoning (manipulating the data used to train or update a model) and model theft (extracting or reproducing a model, including through repeated queries) |
| Lifecycle | Development, operation and model updates, since data collected in use may later feed retraining |
| Relationship | Complements ISO/IEC 27001 and 27002. AI management-system requirements stay with ISO/IEC 42001 |

Our reading comes from ISO's product page and a summary of the standard by an AI governance firm, linked below. We have not reproduced the standard text, which is sold by ISO.

## What it means

Two things stand out.

**First, it frames AI security as a lifecycle problem.** Threats appear at training time, at run time and when a model is updated. A team that only reviews the model before launch misses the other two.

**Second, it is guidance that sits next to ISO/IEC 27001.** If your company already runs an information security management system, AI threats now have a named place in it. Your next audit may ask how you handle them. "We use a trusted provider" will be a thin answer. A better answer lists the controls you run yourself at the point where applications meet models.

That point is the gateway. Training data is out of its reach, but the run-time half of the lifecycle crosses it on every request.

## How OpenProxyAI helps

OpenProxyAI is an open-source, self-hosted gateway. Applications and agents send every model call, and every tool call, through one endpoint. That gives you a small set of controls to map to the standard's run-time concerns.

| Run-time concern | What the gateway offers |
|---|---|
| Who can call a model | One API key per application or agent, with permissions, an expiry date and instant revocation. A revoked or expired key gets a 401 on the next request |
| High-volume querying, including extraction attempts | Requests-per-minute and tokens-per-minute limits per organization and team, plus daily and monthly budgets. Refusals return 429 with the name of the limit that fired |
| Hostile input | Prompt-injection detection, blocked keywords and personal-data checks, with a log-only mode to measure before you enforce. A policy block returns HTTP 446 with a plain-language reason |
| Data leaving the building | Data-class routing so sensitive prompts reach only approved models, and response guardrails that withhold or redact personal data |
| Agent tools | One MCP endpoint for all tool servers, allow and block lists, per-key grants, pinning of approved tool definitions, and scans of tool descriptions and results |
| Evidence | A request log and an admin audit log, plus export of security events to your SIEM |

Here is a worked example. A support team runs an assistant that answers customer questions with a model. A bad actor starts sending thousands of crafted queries through a stolen application key, hoping to map the model's behavior. With the gateway in place, the key has its own request and spend caps, so the volume hits a limit and returns 429 quickly. The per-key request log shows the spike, an admin revokes the key, and the replacement key goes live. The security event stream carries the limit hits into the SIEM for the incident record. Nothing in the application had to change.

For the tool side, see [MCP tool descriptions are untrusted input](/blog/mcp-tool-descriptions-are-untrusted-input) and [MCP grants beat shared tokens](/blog/mcp-grants-beat-shared-tokens). For hijacked agents, read [bounding a hijacked agent](/blog/bounding-a-hijacked-agent).

Where it fits: the gateway covers the run-time access layer. Data poisoning at training time and model weights stored elsewhere need controls in your training and storage pipelines. Policy checks run on the request and response text, so keep keyword lists specific.

## What to do now

- [ ] Add AI-specific threats (poisoning, theft, injection) to your risk register and map each to an owner
- [ ] Give every application and agent its own key, with an expiry date and only the permissions it needs
- [ ] Set rate limits and budgets per team so a single stolen key cannot run unbounded
- [ ] Turn on prompt-injection and personal-data checks in log-only mode, review the hits, then enforce
- [ ] Put all MCP tool servers behind one endpoint and pin the tool definitions you have approved
- [ ] Stream security events to your SIEM and test one revoke-and-replace drill for a key
- [ ] Read how your auditor will cite ISO/IEC 27001 and 27090 together, and ask ahead of time

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

Needs Docker, no provider key. The console is at http://localhost:5173. If it is useful, star the repo or open an issue on GitHub.

## Sources

- ISO, [ISO/IEC 27090:2026](https://www.iso.org/standard/27090): title, first edition and the 14 October 2026 publication date.
- Nemko Digital, [ISO/IEC 27090 published as new AI cybersecurity standard](https://digital.nemko.com/news/isoiec-27090-published-as-new-ai-cybersecurity-standard): scope, threats named and relationship to ISO/IEC 27001, 27002 and 42001.
- OpenProxyAI docs: [Authentication](/getting-started/authentication), [Rate limiting and budgets](/core-concepts/rate-limiting-and-budgets), [Policies and guardrails](/core-concepts/policies-and-guardrails), [MCP gateway](/guides/mcp-gateway), [Telemetry and SIEM](/guides/telemetry-and-siem), [Audit logging](/security/audit-logging).

These statements are based on the sources above and on OpenProxyAI's behavior at the post date.
