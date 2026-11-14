---
slug: owasp-top-10-for-agentic-applications
title: "OWASP's Top 10 for Agentic Applications: the five risks a gateway can reduce"
tags: [security, product]
description: "OWASP published its first Top 10 for Agentic Applications on December 9, 2025. Here is what the list says, and which of its risks a gateway's keys, tool rules, pinning, limits and audit trail help with."
---

On December 9, 2025, the OWASP GenAI Security Project published the OWASP Top 10 for Agentic Applications. It is a peer-reviewed list of the biggest security risks for AI systems that plan, call tools and act on other systems. If your teams are moving from chatbots to agents, this is the list your security review will start quoting. This post summarizes it, then maps the risks a gateway can really help with, and says where a gateway is not the right tool.

{/* truncate */}

![Five risks from the OWASP list, each paired with the gateway control that applies: goal hijack with prompt checks, tool misuse with allow lists and grants, identity abuse with scoped keys, supply chain with tool pinning, and cascading failures with limits and budgets.](/img/blog/owasp-top-10-for-agentic-applications.svg)

## What OWASP published

The list has ten entries, ASI01 to ASI10. The titles, as written in the OWASP document:

| ID | Risk |
|---|---|
| ASI01 | Agent Goal Hijack |
| ASI02 | Tool Misuse and Exploitation |
| ASI03 | Identity and Privilege Abuse |
| ASI04 | Agentic Supply Chain Vulnerabilities |
| ASI05 | Unexpected Code Execution (RCE) |
| ASI06 | Memory & Context Poisoning |
| ASI07 | Insecure Inter-Agent Communication |
| ASI08 | Cascading Failures |
| ASI09 | Human-Agent Trust Exploitation |
| ASI10 | Rogue Agents |

A theme runs through the document: agents cannot reliably tell instructions from the content they read, so every input is a possible instruction. The guidance leans on "least agency", which means giving an agent only as much autonomy, access and tooling as the task needs.

That is a good match for a gateway. An agent reaches the world through two doors: calls to models and calls to tools. A gateway sits in front of both doors.

## Which risks a gateway can reduce

We looked at each entry and kept only the ones where OpenProxyAI has a control that applies. No gateway "covers" a Top 10 list, and we do not claim it.

### ASI01 Agent Goal Hijack

Injected text can redirect an agent. OpenProxyAI can check prompts for injection patterns, block keywords and personal data at the policy stage, and scan MCP tool descriptions and tool results for hidden instructions. A trust rule also keeps a tool with side effects, such as send or delete, from running after the session has read output from an untrusted tool. This lowers the odds. It does not make injection impossible, and the list itself says as much.

### ASI02 Tool Misuse and Exploitation

An agent can misuse a tool it is allowed to use. The MCP gateway gives every agent one endpoint and applies allow and block rules to tool names, plus the same keyword and personal data checks to tool arguments. Grants narrow what a role, team, user or key may call, and named bundles expose only a chosen set of tools. Rate limits and budgets cap runaway loops. Every tool call writes an audit row.

### ASI03 Identity and Privilege Abuse

Agents inherit broad credentials. With OpenProxyAI, each agent gets its own API key with permissions you choose, optionally tied to a team and its budget. The agent's key authenticates it to the gateway only. It is never forwarded to a tool server, and each tool server sees only the credential an admin stored for it, which is kept encrypted. A leaked agent key can be revoked and stops working on the next call.

### ASI04 Agentic Supply Chain Vulnerabilities

Tools and their descriptions come from third parties and can change after you approved them. The MCP gateway can pin each tool definition. A changed definition is marked as drifted, and agents keep getting the approved version. In the strict mode, nothing is served until an admin approves it. Scanning of descriptions and results adds a second layer. Server addresses must be HTTPS and public.

### ASI08 Cascading Failures

One bad call can spread. Limits on requests, tokens and dollars are checked before any provider call, with separate counters for tool traffic. Provider failover keeps one failing key from taking the whole app down. Together they bound how far one runaway agent can go.

## A worked scenario

A support agent reads customer emails and can create tickets and issue refunds through two tool servers.

1. The agent gets its own key, tied to the support team, with a daily dollar budget.
2. The ticket tools are allowed. The refund tool is allowed only for one grant, a small reviewer role. It is marked as a tool with side effects.
3. An email contains hidden text telling the agent to refund an order. The scan flags the result, and because the session has read output from a tool that is not trusted, the refund tool refuses to run.
4. The refused call, and the flagged result, are in the audit log with the key, the tool and the reason.

None of this depends on the model "doing the right thing". The checks sit outside the model.

## Where a gateway is not the main control

Several entries live inside the agent runtime, not on the wire to models and tools: code execution (ASI05), memory and context stores (ASI06), messages between agents (ASI07) and how people come to trust an agent (ASI09). Rogue behavior (ASI10) is helped by budgets and audit, but needs monitoring of the agent itself. Plan controls for those in the agent framework and the runtime. Use the gateway for what it sees: model calls and tool calls.

## What to do now

- Read the OWASP document with your agent owners and mark which of the ten apply to what you run.
- Give every agent its own key, with the smallest permissions and a budget.
- Put tool servers behind one endpoint, with an allow list. Start with pin and scan in report mode, then move to enforcement once the noise is low.
- Mark tools with side effects, and keep untrusted tool output away from them.
- Turn on policy in log-only mode first, read the hits, then enforce.
- Review the audit log for blocked calls each week.

## Good to know

Policy checks run on the text of a request, so keep keyword lists specific. Scanners are heuristics and can flag harmless text, which is why report mode is a good first step.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

Needs Docker and no provider key. The console is at http://localhost:5173. If it is useful, star the repo or open an issue with the risks you want to see covered next.

## Sources

- OWASP GenAI Security Project, [OWASP Top 10 for Agentic Applications for 2026](https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/), published December 9, 2025. Risk titles taken from the document.
- OpenProxyAI docs: [MCP gateway](/guides/mcp-gateway), [Policies and guardrails](/core-concepts/policies-and-guardrails), [Rate limiting and budgets](/core-concepts/rate-limiting-and-budgets), [Authentication](/getting-started/authentication), [Audit logging](/security/audit-logging).

Statements about the OWASP list are based on the document linked above. Statements about OpenProxyAI are based on its documented behavior. OpenProxyAI ships controls, not certifications, and using it does not make anyone compliant with any framework.
