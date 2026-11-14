---
slug: pci-ssc-ai-guidance-agents-cardholder-data
image: /img/blog/og/pci-ssc-ai-guidance-agents-cardholder-data.png
title: "PCI SSC's new AI guidance: approval and least agency for agents"
tags: [security, engineering]
description: "The PCI Security Standards Council published Security Considerations for AI Systems on 7 October 2026. What it asks of agents near cardholder data, and how a gateway puts tool limits, approval boundaries and logs in one place."
---

On 7 October 2026, the PCI Security Standards Council published new guidance called Security Considerations for AI Systems. It speaks directly to teams that put AI agents near payment data. Its message is practical: decide what each AI system may touch, name a person who is accountable, require human approval where the stakes are high, and keep controls outside the AI so a clever prompt cannot talk its way past them. This post walks through what the guidance asks and how a gateway in front of your models and tools helps you meet each point.

{/* truncate */}

![An agent holding a read-only key reaches only read tools through the gateway. A payment action tool sits behind a separate key that an approval service uses only after a person says yes. Every call, allowed or refused, lands in the audit log.](/img/blog/pci-ssc-ai-guidance-agents-cardholder-data.svg)

## What the guidance says

The Council describes the document as advisory. Existing PCI requirements take precedence, and the guidance is not a new set of mandatory rules. The points below come from Help Net Security's report on the document, published on 9 October 2026, and from the Council's own announcement.

- **Least agency.** Limit each AI system to the access and capabilities its task needs. Define its purpose, permissions and data access before you choose or deploy it.
- **Accountability.** A suitable person should formally accept responsibility for the AI's output, and the organization should specify which actions need human approval.
- **Approval for cardholder data.** For agents with access to cleartext cardholder data, explicit human approval is recommended for any action involving that data. The guidance also describes a monitored alternative, where authorized actions run without per-action approval but with defined limits, shutdown triggers and a way to reverse changes.
- **Independent controls.** Access restrictions should be enforced by controls such as identity policies and network isolation, and data loss prevention should work independently of the AI.
- **Keep three things apart.** Avoid combining sensitive data access, external communication and unrestricted input from untrusted sources in one AI system.
- **Know your AI.** Keep an inventory of models, versions, hosting and data-use and retention terms, and have controls to find and restrict shadow AI, meaning tools used without approval.
- **Credentials and logs.** Keep secrets out of prompts, outputs and logs, and make logs useful for investigations without retaining sensitive payment information.

## Where a gateway fits

A gateway cannot make an agent safe on its own. What it can do is hold the controls outside the model, in one place, where a prompt cannot reach them. That matches the guidance's idea of independent controls.

| Guidance point | What OpenProxyAI provides |
|---|---|
| Least agency for tools | A tool allowlist and blocklist for the organization, plus grants that allow or deny tools by role, team, user or API key. A deny always wins, and a call to a tool the caller may not use is refused and logged. |
| Separate approval boundary | Bundles: a named set of tools exposed at its own endpoint. A key attached to a bundle reaches tools only through that bundle. |
| Keep sensitive data, outside action and untrusted input apart | Trust rules. A tool that sends or changes things can be marked as a sink, and a sink refuses to run once the session has seen output from a tool you did not mark as trusted. |
| Data loss prevention outside the AI | Policy checks on prompts and on tool arguments. In enforce mode, a request containing a valid payment card number is refused before any provider or tool sees it, and personal data in answers can be redacted. |
| AI inventory | A model registry listing each approved model with its region, risk rating, retention terms and owner. One gateway also means one list of what is in use. |
| Shadow AI | Provider keys live in the gateway. Applications get gateway keys instead, so a team without a gateway key has no sanctioned path to a model. |
| Credentials | Provider keys are stored encrypted and never shown back, or read from a secrets manager. The key an agent uses to reach the gateway is never forwarded to a tool server. |
| Useful logs | One audit row per model call and per tool call: who, which key, which tool or model, the decision, the status, the cost. By default it keeps metadata, not the text of prompts, so the log supports an investigation without holding card data. |

## The approval pattern, concretely

The guidance asks you to say which actions need a person. The approval screen itself lives in your application, because only you know what a refund or a payout looks like to your staff. The gateway's job is to make sure that screen cannot be skipped.

Take a support agent that can look up an order and can issue a refund.

1. The agent's key is attached to a bundle that holds only the lookup tools. A direct call to the refund tool is refused and logged.
2. When the agent wants a refund, your application shows a person the details.
3. If the person approves, a separate service uses a different key, attached to a bundle that holds the refund tool, and makes the call.
4. Both calls appear in the audit log with the tool name, the decision and the key that made them, so you can show who could do what, and when it happened.

The refund tool is also marked as a sink. If the agent's session read output from a tool you did not mark as trusted, the sink refuses to run in that session at all. That is the guidance's "keep apart" rule enforced by the platform rather than by a prompt.

One more control worth knowing: admins can pin each tool's definition and approve it before agents see it. If a tool server changes a description later, the changed tool is held back until an admin reviews it. That approves tool definitions, which is different from approving individual actions, and the two work well together.

## What to do now

- [ ] Read the guidance and note which of your agents touch payment data.
- [ ] Write down, per agent, which tools it needs. Deny the rest.
- [ ] Decide which actions need a person. Put those tools behind a separate key and bundle.
- [ ] Mark every tool with side effects as a sink.
- [ ] Turn on policy checks for card numbers and personal data, in log-only mode first to see the hits, then enforce.
- [ ] Move provider keys into the gateway or a secrets manager and remove them from application settings.
- [ ] Name the person accountable for each agent's output.
- [ ] Review the audit log on a schedule, and export it if your retention need is longer than your plan's window.

## Good to know

OpenProxyAI ships policy templates and controls, not a PCI assessment. Whether a system is in scope, and how to meet PCI DSS, is a question for your own program and assessor. The gateway governs what passes through it, so keep agents on gateway keys and route their tools through the gateway for the limits above to apply. Keyword and pattern checks are best kept specific, and are one layer among several.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

This needs Docker and no provider key. The console opens at http://localhost:5173. If it helps, star the repo or open an issue with the controls you want next.

## Sources

- [PCI SSC Publishes Additional Guidance on Securing AI in Payment Environments](https://www.pcisecuritystandards.org/about_us/press_releases/pci-ssc-publishes-additional-guidance-on-securing-ai-in-payment-environments/), PCI Security Standards Council, 7 October 2026. Publication, advisory status, accountability.
- [PCI SSC calls for human approval of AI agent actions involving cardholder data](https://helpnetsecurity.com/2026/10/09/pci-ssc-payment-environments-ai-security-guidance), Help Net Security, 9 October 2026. Summary of the recommendations. We read this report, not the full document, so check the guidance itself for exact wording.
- Internal: [MCP gateway](/guides/mcp-gateway), [Policies and guardrails](/core-concepts/policies-and-guardrails), [Audit logging](/security/audit-logging), [Compliance templates](/security/compliance-templates), [Bounding a hijacked agent](/blog/bounding-a-hijacked-agent).

These statements are based on the sources above and on OpenProxyAI's behavior at the date of this post.
