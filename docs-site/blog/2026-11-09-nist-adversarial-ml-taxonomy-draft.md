---
slug: nist-adversarial-ml-taxonomy-draft
image: /img/blog/og/nist-adversarial-ml-taxonomy-draft.png
title: "NIST drafts a shared vocabulary for attacks on AI agents. Comments close 18 December"
tags: [security, product]
description: "On 9 November 2026 NIST released a draft taxonomy of adversarial machine learning, with a focus on agentic systems. Use its attacker-capability lens to map your own gateway controls."
---

On 9 November 2026, NIST released an initial public draft of SP 2400-102, "Adversarial Machine Learning: A Taxonomy and Terminology of Attacks and Mitigations". It gives security teams a common language for how AI systems get attacked, and the draft says its focus is attacks on agentic systems and the matching mitigations. Public comments are open until 18 December 2026. Even before it is final, the way the draft describes an attacker, by goals, capabilities and knowledge, is a practical tool for reviewing the controls you already run.

{/* truncate */}

![Four attacker capabilities (sends prompts, plants text in a document, controls a tool server, holds a stolen key) each mapped to a gateway control: guardrails, injection detection with tool scans, definition pinning with grants, key limits with revocation.](/img/blog/nist-adversarial-ml-taxonomy-draft.svg)

## What happened

| Fact | Detail |
|---|---|
| Document | NIST SP 2400-102 ipd (initial public draft), "Adversarial Machine Learning: A Taxonomy and Terminology of Attacks and Mitigations" |
| Date | Released 9 November 2026 |
| Comment deadline | 18 December 2026 |
| Purpose | A common language to inform future standards and practice guides |
| What the taxonomy covers | Types of machine learning methods, stages of an attack's life cycle, and attackers' goals, objectives, capabilities and knowledge. It also has a glossary and describes mitigations |
| Focus | Attacks on agentic systems and corresponding mitigations (Section 4 of the draft) |
| Audience | People who design, develop, deploy, evaluate and govern these systems |

The page keywords include data poisoning, evasion, privacy breach and large language models. We have read NIST's announcement and abstract, not the full text of the draft, so this post does not claim to describe its individual attack categories. Read the draft itself before you cite it.

A week earlier, on 2 November 2026, NIST also published Internal Report 8621. It summarizes a workshop of more than 400 participants on managing incidents involving advanced AI systems, and lists future work such as updating NIST's incident response guidance, monitoring and evidence collection, and incident information sharing. Together the two documents show where NIST is heading: shared terms first, then incident practice.

## What it means

Security programs for AI have been held back by loose words. One team says "jailbreak" and means a user trick. Another says "injection" and means a poisoned web page. A vendor questionnaire says "adversarial" and means all of it. A shared taxonomy gives you three things:

1. **Better questionnaires.** You can ask a vendor which attacker capability each control assumes, instead of whether it "protects against prompt injection".
2. **Cleaner threat models.** For each agent, write down what an attacker could know and do. Can they send input? Control a document the agent reads? Run a tool server? Hold a stolen key?
3. **A path to standards.** NIST says the aim is to inform later standards and guides. Teams that already use the vocabulary will have less to relearn.

Treat it as a draft. Terms and structure may change before the final version, and NIST wants comments.

## How OpenProxyAI helps

OpenProxyAI is an open-source, self-hosted gateway that all model and tool calls pass through. The attacker-capability lens turns neatly into a table of controls. This is our own mapping for planning, not a mapping taken from the draft.

| If the attacker can... | Control at the gateway |
|---|---|
| Send prompts directly | Policy checks on every request: model allowlist, blocked keywords, personal-data checks and prompt-injection detection. Roll out in log-only mode first, then enforce. Blocks return HTTP 446 with a plain-language reason |
| Plant text in a document or page the agent reads | Injection detection on inputs, and a rule that tools with side effects refuse to run once untrusted tool output has been seen in the session |
| Control or change a tool server | Pinned tool definitions, so an agent only sees what an admin approved. Scans of tool descriptions and results for hidden instructions. Per-key grants that limit which tools a caller can reach |
| Hold a stolen API key | Per-key permissions and expiry, request and spend limits, and instant revocation. Every request carries the key id in the log |
| Learn from repeated queries | Rate and token limits per organization and team, and budgets, so high-volume probing runs into a limit and appears in the logs |

Here is how a team might use it. A platform lead picks their three most important agents and writes one line per attacker capability: what the agent can reach, and which control stands in the way. They find that the invoice agent has strong limits on who can call it, but nothing about untrusted text in the documents it reads. They turn on injection detection in log-only mode, mark the email tool as a side-effect tool, and review a week of hits before enforcing. When NIST publishes the final taxonomy, they relabel the table with its terms and keep the controls.

For deeper background, see [prompt injection defense in production](/blog/prompt-injection-defense-in-production), [MCP tool descriptions are untrusted input](/blog/mcp-tool-descriptions-are-untrusted-input) and [the OWASP Top 10 for agentic applications](/blog/owasp-top-10-for-agentic-applications).

Good to know: injection detection is a heuristic and can produce false positives, which is why log-only mode exists. Use it as one layer next to key limits and tool controls, not as the only one.

## What to do now

- [ ] Read the draft and decide whether to send NIST a comment before 18 December 2026
- [ ] For each agent, write down what an attacker could send, plant, control or steal
- [ ] Map each capability to a control you run today, and note the gaps
- [ ] Turn on injection and personal-data checks in log-only mode and review the hits
- [ ] Pin the tool definitions you have approved and scan tool output
- [ ] Give every agent its own key with limits, and practice revoking one
- [ ] Add the NIST terms to your vendor questionnaire, such as the one in our [AI vendor security questionnaire](/blog/ai-vendor-security-questionnaire)

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

Needs Docker, no provider key. The console is at http://localhost:5173. If it is useful, star the repo or open an issue on GitHub.

## Sources

- NIST, [Adversarial Machine Learning Taxonomy and Terminology draft (NIST SP 2400-102)](https://www.nist.gov/news-events/news/2026/11/adversarial-machine-learning-taxonomy-and-terminology-draft-nist-sp-2400): the 9 November 2026 announcement, the 18 December 2026 comment deadline and the stated focus.
- NIST CSRC, [SP 2400-102 ipd](https://csrc.nist.gov/pubs/sp/2400-102/e2026/ipd): abstract, release date and scope of the taxonomy.
- NIST, [Workshop on SI incident management: NIST publishes IR 8621](https://www.nist.gov/news-events/news/2026/11/workshop-si-incident-management-nist-publishes-ir-8621): the 2 November 2026 report and its areas for future work.
- OpenProxyAI docs: [Policies and guardrails](/core-concepts/policies-and-guardrails), [MCP gateway](/guides/mcp-gateway), [Rate limiting and budgets](/core-concepts/rate-limiting-and-budgets), [Authentication](/getting-started/authentication).

These statements are based on the sources above and on OpenProxyAI's behavior at the post date.
