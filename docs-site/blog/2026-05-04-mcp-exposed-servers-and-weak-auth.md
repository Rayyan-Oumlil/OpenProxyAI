---
slug: mcp-exposed-servers-and-weak-auth
title: "CSA on the MCP security crisis: how to put tool servers behind one door"
tags: [security, architecture]
description: "A Cloud Security Alliance research note dated May 4, 2026 describes exposed MCP servers, optional authentication and unguarded tool definitions. Here is what it says and how OpenProxyAI's MCP gateway answers each point."
---

The Cloud Security Alliance (CSA) published a research note on May 4, 2026 titled "MCP Security Crisis: Systemic Design Flaws in AI Agent Infrastructure." It collects findings from several security teams about the Model Context Protocol (MCP), the standard that lets AI agents call tools. The headline is simple: many MCP servers are reachable, many have no authentication, and the protocol has few built-in defenses against a tool that changes or lies. This post covers what the note says and how to put your tool servers behind one governed door.

{/* truncate */}

![An agent connects with one key to the gateway, which applies allow lists, grants, pinned tool definitions, result scanning and an audit row before reaching tool servers.](/img/blog/mcp-exposed-servers-and-weak-auth.svg)

## What the research note says

From the [CSA note](https://labs.cloudsecurityalliance.org/research/csa-research-note-mcp-security-crisis/), with the source of each figure as CSA gives it:

- OX Security's April 2026 disclosure estimates about 200,000 vulnerable instances, tied to how the official SDKs handle one transport. CSA says this is an estimate drawn mainly from that vendor research.
- A July 2025 internet scan, cited by CSA from Dark Reading, found 1,862 publicly reachable servers answering unauthenticated requests.
- The MCP authorization specification defines an OAuth 2.1 framework but marks authorization optional, so many servers accept connections and list their tools without checking credentials.
- The protocol lacks native defenses against tool poisoning, rug pull attacks (a tool that changes after you approved it) and one server's tool impersonating another's.

CSA's recommendations include taking an inventory of every MCP server, giving each server scoped credentials, pinning versions, alerting on changes to tool definitions, and mediating actions between servers through an explicit policy layer rather than trusting the agent's own judgment.

## What it means for your team

Three problems come out of this, and none needs a deep protocol change to address:

1. **Too many doors.** Each agent holds credentials for each tool server, and nobody has a single list of what exists.
2. **No guard on what a tool says.** A tool description is text an agent reads as instructions. If it changes after approval, behavior changes with no code review.
3. **No record.** When a tool does something unexpected, there is nothing to look at afterward.

## How OpenProxyAI answers each point

OpenProxyAI's [MCP gateway](/guides/mcp-gateway) puts every tool server behind one endpoint and one API key per agent.

| CSA concern | What the gateway does |
|---|---|
| Exposed servers, optional auth | The agent authenticates to the gateway with its own key. The gateway does not forward that key or any other agent header to a tool server. Each server receives only the credential an admin stored for it, which is kept encrypted and never shown again. |
| Inventory | Only admins can register tool servers. Registered servers must use HTTPS and resolve to a public address. Every create, update and delete is written to the admin audit log. |
| Scoped access | Organization allow and block lists apply first. Then grants allow or deny tools for a role, team, user or API key, and a matching deny always wins. Bundles expose a named set of tools at their own endpoint, so a key can be confined to exactly that set. |
| Tools that change | Pinning records each tool definition when an admin approves it. If a definition changes, agents keep getting the approved version and the change is flagged. In the strictest mode, nothing is served until an admin approves it. The gateway re-checks pinned servers on a schedule, so a change is found even when no agent is calling. |
| Poisoned descriptions and results | Each server can be set to log, sanitize or block descriptions and results that look like injected instructions. |
| Cross-tool abuse | Trust rules mark tools that have side effects. A session that has received output from an untrusted tool cannot then run one of those tools. |
| No record | Every tool call writes a row to the request log with the tool name, the server, the status and the policy decision, next to your model calls. |

![The OpenProxyAI console page listing registered MCP servers with their status and settings.](/img/blog/console-mcp-servers.png)

## A worked scenario

A team has an agent that reads tickets and can post to chat. Today it holds a token for each tool server.

1. An admin registers the ticket server and the chat server in the gateway, each with its own stored credential. The agent gets one key.
2. The agent's key is granted read tools on the ticket server and the chat post tool only. A delete tool is blocked for everyone by an organization rule.
3. Both servers' tools are pinned. Later, the chat server changes the text of its post tool. The agent keeps the approved version, and the admin sees the change flagged for review.
4. A ticket contains hidden instructions to post a secret. The result is scanned, the session is marked as having seen untrusted output, and the chat post tool, which has side effects, is refused for that session.
5. Every step above appears in the request log.

## What to do now

- Inventory every MCP server your teams use, including ones added through developer tools.
- Require authentication on every one, and keep their credentials out of agents.
- Route agents through one endpoint, and give each its own key.
- Allow tools by pattern, deny the dangerous ones, and use grants for roles and teams.
- Pin tool definitions and review changes.
- Mark side-effect tools so untrusted output cannot trigger them.
- Read [OWASP's top ten for agentic applications](/blog/owasp-top-10-for-agentic-applications) and our post on a [governed A2A endpoint](/blog/a2a-one-year-governed-endpoint) for the wider picture.

## Good to know

The gateway governs tool servers that are reached through it, which are remote servers over HTTPS. Local tool processes started on a developer's own machine are not behind it, so include them in the inventory separately.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

This needs Docker and no provider key. The console is at http://localhost:5173. If it helps, star the repo or open an issue with the controls you want next.

## Sources

- [MCP Security Crisis: Systemic Design Flaws in AI Agent Infrastructure](https://labs.cloudsecurityalliance.org/research/csa-research-note-mcp-security-crisis/), Cloud Security Alliance, May 4, 2026. All external figures and recommendations above.
- [MCP gateway](/guides/mcp-gateway): grants, pinning, scanning, bundles and trust rules.
- [MCP admin API](/api-reference/mcp-admin): managing servers and tool approvals.
- [Policies and guardrails](/core-concepts/policies-and-guardrails): the organization policy.

These statements are based on the sources above and on OpenProxyAI's behavior as of May 4, 2026.
