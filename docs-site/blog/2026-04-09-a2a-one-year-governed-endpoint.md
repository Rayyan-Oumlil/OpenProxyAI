---
slug: a2a-one-year-governed-endpoint
title: "A2A turns one: what a Linux Foundation agent standard means for your gateway"
tags: [architecture, product]
description: "The Linux Foundation marked one year of the Agent2Agent protocol on April 9, 2026, with more than 150 supporting organizations. What it means for teams running agents, and where a governed endpoint fits."
---

On April 9, 2026, the Linux Foundation marked the first year of the Agent2Agent (A2A) protocol. It reported more than 150 supporting organizations, a first stable specification (version 1.0) and production use in several industries. A2A is the open standard that lets agents from different vendors find each other and work together. If your teams are building more than one agent, you will be asked how they should talk, and how you will keep track of what they do.

{/* truncate */}

![Agent A and Agent B talk directly over an agent-to-agent protocol, while each sends its model and tool calls through the OpenProxyAI governed endpoint to model providers and MCP tool servers.](/img/blog/a2a-one-year-governed-endpoint.svg)

## What the Linux Foundation announced

The announcement, headlined "A2A Protocol Surpasses 150 Organizations, Lands in Major Cloud Platforms, and Sees Enterprise Production Use in First Year", says:

- More than 150 organizations support the standard, up from more than 50 a year earlier.
- Version 1.0 is the project's first stable specification.
- Microsoft integrated A2A into Azure AI Foundry and Copilot Studio, and AWS added support through Amazon Bedrock AgentCore Runtime.
- The release reports production deployments in supply chain, financial services, insurance and IT operations.
- SDKs cover five languages: Python, JavaScript, Java, Go and .NET.

For background, the protocol was created by Google and launched in April 2025. The Linux Foundation announced that it would host it on June 23, 2025, with the stated goal of keeping it vendor neutral.

## What it means for teams running agents

A stable, vendor-neutral standard lowers the cost of mixing agents from different vendors. A planning agent from one vendor can hand work to a specialist from another. That is good news for flexibility, and it raises three questions for the people who run the platform.

| Question | Why it matters |
|---|---|
| Who is the caller? | Each agent needs its own identity, not a shared key. |
| What can it reach? | Every agent ends up calling models and tools. Those calls need limits. |
| What did it do? | When several agents act in a chain, you need one place to look. |

Whatever protocol agents use to talk to each other, each of them still does the same two things in the end: it calls a model, and it calls tools. Those are the places where money is spent and data moves.

## Where a governed endpoint fits

OpenProxyAI gives agents one OpenAI-compatible endpoint for model calls and one MCP endpoint for tool calls. The same ideas that protect a single application then apply to each agent in a team of agents.

- **One key per agent.** Keys carry permissions, can be tied to a team and its budget, and can be revoked on the next call.
- **Budgets and rate limits.** A looping agent hits a limit and gets a clear answer instead of a surprise invoice. See [Rate limiting and budgets](/core-concepts/rate-limiting-and-budgets).
- **Policy on prompts.** Model allow lists, blocked keywords, personal data and prompt-injection checks apply to every agent's requests, in log-only mode first or enforcing from the start.
- **Tool rules through the [MCP gateway](/guides/mcp-gateway).** Allow and block rules, grants per role, team, user or key, pinned tool definitions and scanning of results. The agent's own key is not passed to tool servers.
- **One audit trail.** Model calls and tool calls appear side by side in the request log, with the key, the decision and the cost.
- **Routing by data class.** Under enforced routing, a request goes only to a model cleared for its data. See [Provider routing](/core-concepts/provider-routing).

## A worked scenario

A procurement team runs three agents: one reads supplier emails, one drafts purchase orders and one checks budgets. A fourth agent from a different vendor is added to negotiate prices.

1. Each agent gets its own key, tied to the procurement team, with a daily dollar budget.
2. All four point their model calls at the gateway, and each sends a label with its name, which is recorded on the request log.
3. All four use the MCP endpoint for tools. Only the drafting agent is granted the tool that creates purchase orders.
4. A week later, the finance lead filters the log by label, sees spend per agent and sees the refused calls, without asking four vendors for four reports.

## What to do now

- List the agents in use or planned, and who owns each.
- Give each one its own key, with a budget.
- Move model calls to one endpoint, and tool calls to the MCP gateway.
- Write the tool allow list from the task, not from what the tool server offers.
- Read the log after the first week and adjust.
- When you evaluate a new agent product, ask how it identifies itself and whether its model and tool calls can go through your endpoint.

## Good to know

A gateway governs the model calls and tool calls an agent makes. Messages that agents send directly to each other travel between those agents, so choose and review those links in the agent framework you use.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

Needs Docker and no provider key. The console is at http://localhost:5173. If it helps, star the repo or open an issue about the agent setups you want to see.

## Sources

- Linux Foundation, [A2A Protocol Surpasses 150 Organizations, Lands in Major Cloud Platforms, and Sees Enterprise Production Use in First Year](https://www.linuxfoundation.org/press/a2a-protocol-surpasses-150-organizations-lands-in-major-cloud-platforms-and-sees-enterprise-production-use-in-first-year), April 9, 2026.
- Linux Foundation, [Linux Foundation Launches the Agent2Agent Protocol Project](https://www.linuxfoundation.org/press/linux-foundation-launches-the-agent2agent-protocol-project-to-enable-secure-intelligent-communication-between-ai-agents), June 23, 2025.
- OpenProxyAI docs: [MCP gateway](/guides/mcp-gateway), [Authentication](/getting-started/authentication), [Request pipeline](/core-concepts/request-pipeline), [Audit logging](/security/audit-logging).

Statements about A2A are based on the Linux Foundation releases linked above. Statements about OpenProxyAI are based on its documented behavior.
