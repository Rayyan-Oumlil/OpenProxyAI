---
slug: nist-ai-agent-standards-initiative
title: "NIST's AI agent standards initiative: what it means for identity and logs"
tags: [security, product]
description: "NIST's CAISI launched an AI Agent Standards Initiative with identity and authorization at its core. Here is what NIST said, and how per-agent keys, grants and an audit trail already give you a head start."
---

On February 17, 2026, NIST's Center for AI Standards and Innovation (CAISI) announced the AI Agent Standards Initiative. Its goal is to help AI agents that act on their own be adopted with security and interoperability built in. Two of its first public requests are about security threats and about agent identity and authorization. If you run agents in production, the message is clear: standards bodies now treat "who is this agent and what may it do" as a first-class question. You do not need to wait for final guidance to start answering it.

{/* truncate */}

![Three NIST pillars on the left and the matching OpenProxyAI controls on the right: agent identity maps to per-agent API keys, authorization maps to per-tool grants, and evidence maps to the audit log.](/img/blog/nist-ai-agent-standards-initiative.svg)

## What NIST announced

From NIST's announcement and program page, as published on February 17, 2026:

- **Who.** CAISI at NIST leads the initiative. NIST's Information Technology Laboratory coordinates with it, and the program page names the National Science Foundation as a partner.
- **Three pillars.** Encourage industry-led agent standards and U.S. leadership in international standards bodies. Support community-led, open source protocols for agents. Research AI agent security and identity, so that new uses can be adopted with trust across sectors.
- **Two open requests for input.** A Request for Information on AI agent security, open until March 9. A draft concept paper on AI agent identity and authorization, open for comment until April 2.
- **What comes next.** CAISI plans listening sessions starting in April on sector-specific barriers to adoption. NIST says it will announce more research, guidelines and deliverables in the coming months.

This is a launch, not a standard. There is no checklist to follow yet, and nothing here is a requirement. What it gives you is a direction of travel.

## What it signals

Read the pillars together and three themes stand out for anyone deploying agents.

**Identity.** The program page describes research on "agent authentication and identity infrastructure". An agent that calls tools and models needs an identity that is separate from the human who started it, so you can tell one agent from another and revoke one without touching the rest.

**Authorization.** The concept paper is titled around identity and authorization together. Knowing who the agent is does not settle what it may do. Permissions should be narrow, explicit and easy to change.

**Evidence.** NIST's announcement does not talk about logging. Our reading is that it is the natural third leg. Whenever you grant an agent authority, someone will later ask what it did with it. Without a record, the first two themes cannot be checked.

## How OpenProxyAI maps to the three themes

OpenProxyAI is an open-source, self-hosted gateway that sits between your applications and your model and tool providers. These are controls it ships today. They are not an implementation of any NIST guidance, because none exists yet.

| Theme | What you can do | Outcome |
|---|---|---|
| Identity | Give each agent its own API key, optionally tied to a team and limited to the permissions it needs. People sign in through single sign-on, with automatic user provisioning (SCIM). | Every request carries a named caller, and one key can be revoked on its own. |
| Authorization | Write per-tool grants for a role, team, user or API key. A deny always wins, and the organization policy sets the outer limit. A caller can also narrow its own tool list per request, never widen it. | A hijacked agent can only reach what its key was granted. |
| Evidence | Every request, policy decision, routing decision and cost is written to an audit log that is never edited afterward. Admin changes have their own log. | You can answer "what did this agent do, and why was it allowed" from a record. |

Two details make this practical rather than theoretical.

First, tool calls are checked against the grants on every call, so removing a grant takes effect on the next request, not at the next deploy. The audit row for a tool call records which allow, deny and scope rules applied. The [grants post](/blog/mcp-grants-beat-shared-tokens) shows real request bodies, and [bounding a hijacked agent](/blog/bounding-a-hijacked-agent) shows how the limits stack when an agent is tricked.

Second, the log is built for review. It can be queried from the console or the API, and a compliance export can be scoped to a date range and a team. See [audit logging](/security/audit-logging) for retention by plan.

## A worked example

A support team runs a ticket-triage agent. The platform team does the following.

1. Creates a key just for that agent and attaches it to the support team.
2. Adds a grant that lets the key search the knowledge base and file tickets.
3. Adds a deny for anything that deletes data.
4. Applies the organization policy in log-only mode first, so they can see what would be blocked.

Three weeks later the agent reads a web page that contains hidden instructions to export customer records. The tool call is refused, the audit log shows which rule refused it, and the platform team revokes that one key. No other agent is affected. The agent had its own identity, narrow authority and a record, which is exactly the trio the initiative points at.

## What to do now

- List your agents and give each its own key. Retire shared keys.
- For each agent, write down the tools it needs, then grant only those.
- Add deny rules for destructive actions, since deny wins over allow.
- Start new rules in log-only mode and review the hits before enforcing.
- Decide who reads the audit log and how often.
- If your organization has a view on agent security or identity, NIST's request for input on security and its concept paper on identity are open. Check the dates above.

## Good to know

Grants are checked for tool calls made through the OpenProxyAI tool gateway. Keep agent tool access flowing through it so the rules and the record apply to everything. And because NIST has not published guidance yet, treat any gateway as a way to build good habits now, not as a claim of alignment.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

Needs Docker, no provider key. Console at http://localhost:5173. If it helps, star the repo or open an issue with what your agents need.

## Sources

- [NIST, AI Agent Standards Initiative (program page)](https://www.nist.gov/caisi/ai-agent-standards-initiative): pillars, the request for information and the concept paper.
- [NIST news, "Announcing the AI Agent Standards Initiative for interoperable and secure innovation"](https://nist.gov/news-events/news/2026/02/announcing-ai-agent-standards-initiative-interoperable-and-secure): published February 17, 2026.
- [MCP gateway guide](/guides/mcp-gateway): tool access and grants.
- [Audit logging](/security/audit-logging): what is recorded and retention by plan.
- [Authentication](/getting-started/authentication): API keys and permissions.
- [Configuring SSO](/guides/sso-and-scim) and [configuring SCIM](/guides/sso-and-scim): human identity.

These statements are based on the NIST pages above as published on February 17, 2026, and on OpenProxyAI's behavior at that date. OpenProxyAI ships controls, not certifications, and using it does not make anyone compliant with a standard.
