---
slug: agent-identity-entra-okta
image: /img/blog/og/agent-identity-entra-okta.png
title: "Agent identity is here from Entra and Okta. Pair it with per-agent keys"
tags: [security, product]
description: "Microsoft Entra Agent ID and Okta for AI Agents give agents first-class identities. Here is what each vendor says, and how SSO, SCIM and one API key per agent fit around them."
---

Identity vendors now treat AI agents as identities, not as shared passwords. Microsoft documents Entra Agent ID as generally available. Okta announced on 13 November 2026 that Okta for AI Agents works with third-party identity providers out of the box. For a platform lead, the question is practical: where does an agent's identity end and where does the model call begin? This post sums up what the vendors say and shows how a gateway gives every agent its own key, limits and audit trail next to them.

{/* truncate */}

![An identity provider handles sign-in and agent identities. OpenProxyAI gives each agent its own key with limits, sits in front of model providers, and records every call in an audit trail by key.](/img/blog/agent-identity-entra-okta.svg)

## What the vendors say

**Microsoft Entra Agent ID.** Microsoft's documentation describes it as an identity and security framework that extends Entra to AI agents so organizations can authenticate, authorize, govern and protect them. Per those pages:

- Agent identity blueprints act as templates for creating individual agent identities.
- It supports OAuth 2.0, the Model Context Protocol (MCP) and agent-to-agent (A2A) communication.
- Agents on non-Microsoft platforms, such as AWS Bedrock and n8n, can be integrated through a sidecar SDK or workload identity federation.
- Conditional Access and ID Protection extend to agents, and agent authentication and activity are logged for compliance and audit.
- Microsoft's "what's new" page says agent registry experiences are converging under Microsoft Agent 365, with Entra continuing as the identity foundation.

**Okta for AI Agents.** Okta's 16 March 2026 press release says the product reached general availability on 30 April 2026. Okta's GA post lists these capabilities: an AI agent registry, shadow agent discovery, short-lived scoped tokens in place of hardcoded credentials, access certification, and a kill switch that revokes an agent across connected systems. The 13 November 2026 press release adds support for third-party identity providers that support Cross App Access, naming Ping, Descope and Oracle, so employee and agent identities can live in an identity provider you already run.

## Where the gateway fits

An identity provider answers "who or what is this agent, and may it sign in or get a token". A gateway answers a different set of questions about every model call: which model, with which data, within what budget, and what was recorded. The two layers help each other.

| Question | Where it is answered |
|---|---|
| Who is this person or agent in our directory | Your identity provider |
| Who may sign in to the AI admin console | Single sign-on through your identity provider |
| Who gets an account, and when does it end | SCIM provisioning from your identity provider |
| Which agent made this model call | The agent's own API key at the gateway |
| What may that agent send, where, and how much | Policy, data classes and limits at the gateway |

## How OpenProxyAI handles each layer

**SSO for people.** Connect an OpenID Connect identity provider and your team signs in to the admin console through it. A person who signs in for the first time is created with the developer role; an existing person keeps their role. See [Single sign-on and SCIM](/guides/sso-and-scim) and [SSO and SCIM for AI access](/blog/sso-and-scim-for-ai-access).

**SCIM for lifecycle.** Okta and Microsoft Entra ID can create, update and deactivate OpenProxyAI users through SCIM 2.0. A leaver is deactivated without anyone opening the console, and their request history stays. Provisioning never grants a role, so a directory change cannot make someone an admin.

**One key per agent.** Each agent gets its own API key. A key carries named permissions (for example, model calls only, or model calls plus MCP tools), an optional team and an optional expiry. The full key is shown once. Revoke it and that agent stops, while every other agent keeps working. See [API keys and provider keys](/api-reference/keys).

**Tools by grant, not by shared token.** If agents call tools through the MCP gateway, grants limit which keys, users, teams or roles may call which tools, and each call lands in the audit log. See [MCP gateway](/guides/mcp-gateway) and [MCP grants beat shared tokens](/blog/mcp-grants-beat-shared-tokens).

**Limits and spend per key.** A key tied to a team counts against that team's budget. Rate limits and budgets return a clear status when reached, so a runaway agent hits a wall instead of a surprise invoice. See [Rate limiting and budgets](/core-concepts/rate-limiting-and-budgets).

**An audit trail by key.** Every request records which key called, the model and provider, tokens, cost, the policy decision and the routing decision. Entries are written once and are not edited. See [Audit logging](/security/audit-logging).

## A worked scenario

A company runs three agents: a ticket summarizer, a code reviewer and a finance analyst. In its identity provider, each agent has an owner. At the gateway, each agent has its own key. The summarizer's key can call models only, with the team budget of customer support. The finance analyst's key is tagged to a stricter data class and routed only to models cleared for it. The code reviewer's key has MCP permission and a grant for two repository tools. When the code reviewer misbehaves, the team revokes one key. The audit trail shows exactly what it called, and the other two agents never notice.

## What to do now

- Decide which agents need identity-provider identities and name an owner for each.
- Create one gateway key per agent. Give it the smallest permissions and an expiry.
- Turn on SSO for the console and SCIM for user lifecycle.
- Put each agent's traffic in a data class and approve models for it.
- Review the audit trail by key weekly for the first month.

## Good to know

The identity vendors and OpenProxyAI work at different layers. This post does not describe a direct integration between OpenProxyAI and Entra Agent ID or Okta for AI Agents. SSO and SCIM connect people and accounts, and API keys identify agents at the gateway.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

Needs Docker, no provider key. Console at http://localhost:5173. If it helps, star the repo or open an issue describing how you want agent identity to connect.

## Sources

- [Microsoft Learn: What is Microsoft Entra Agent ID](https://learn.microsoft.com/en-us/entra/agent-id/what-is-microsoft-entra-agent-id): framework, protocols, third-party integration.
- [Microsoft Learn: What's new in Microsoft Entra Agent ID](https://learn.microsoft.com/en-us/entra/agent-id/whats-new-agent-id): general availability, Conditional Access, Agent 365 convergence.
- [Okta: new blueprint for the secure agentic enterprise, 16 March 2026](https://www.okta.com/newsroom/press-releases/showcase-2026/): general availability on 30 April 2026.
- [Okta: Okta for AI Agents is now Generally Available](https://www.okta.com/blog/ai/okta-for-ai-agents-general-availability/): capability list.
- [Okta: third-party identity provider support, 13 November 2026](https://www.okta.com/newsroom/press-releases/okta-for-ai-agents-now-works-out-of-the-box-with-multiple-third-party-identity-providers/): Cross App Access and named providers.
- Related: [Single sign-on and SCIM](/guides/sso-and-scim), [API keys](/api-reference/keys).

These statements are based on the vendor pages as read on 13 November 2026 and on OpenProxyAI's behavior at that date.
