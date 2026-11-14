---
slug: give-each-team-its-own-mcp-tool-set
title: "Give each team its own MCP tool set, from one gateway"
tags: [product, security]
description: "Register your MCP tool servers once, then expose a separate set of tools to each team with bundles and grants. Support gets support tools, finance gets finance tools, and nobody gets the rest."
---

Once agents start calling tools, the next question is who gets which tools. Support agents need the ticket system. Finance agents need reports. Platform engineers need repositories and pipelines. Nobody wants a support bot that can reach the ledger because someone reused a token. With OpenProxyAI you register every MCP tool server once, then give each team its own tool set, with each tool call checked and logged.

{/* truncate */}

![Three teams, support, finance and platform, each with their own bundle endpoint that exposes a different set of tools from the same registered servers.](/img/blog/give-each-team-its-own-mcp-tool-set.svg)

## The problem

MCP, the Model Context Protocol, is the standard way agents discover and call tools. The default setup is one agent talking directly to one or more tool servers, each with its own credential. That scales badly in a company.

- Every team ends up with its own copy of the connection details.
- The simplest fix, a shared service token, makes every agent as powerful as the most privileged one.
- Nobody can answer a plain question: which teams can call which tools?

The better pattern is to put the tool servers behind one gateway and make access a decision you can read.

## Step 1: register the servers once

An admin registers each tool server with the gateway, along with the credential the gateway should use for it. That credential is stored encrypted and is never shown again. Your agents do not hold it. They authenticate to the gateway with a gateway key, and the gateway talks to each server with the credential an admin stored for that server alone.

Tools from all servers show up in one list, named by server and tool, so a search tool on a server called github appears as `github__search`. The names make rules easy to write.

## Step 2: shape what each team can see

There are two tools for this, and they work well together.

**Grants** say who may use which tools. A grant is an allow or deny rule for a role, a team, a user or a single API key, matched against tool names with simple wildcards. A matching deny always wins. If any allow grant applies to the caller, the tool must match one of them. If none applies, the caller is not restricted, so turning grants on does not break anyone by surprise.

**Bundles** are named tool sets, each served at its own endpoint. Create a bundle for support, list the tool patterns it contains, and attach the support team's keys to it. A key attached to a bundle can reach tools only through that bundle's endpoint. The general endpoint is refused for it, otherwise attaching a bundle would confine nothing.

| You want | Use |
|---|---|
| Hard walls between teams | A bundle per team, with keys attached |
| A rule for a whole role, such as viewers | A grant on that role |
| One dangerous tool off for everyone | An organization-level block pattern |
| A single agent that needs even less | A request-level scope that can only narrow |

Every layer can only remove tools that the previous layer allowed. So your organization policy sets the outer wall, grants narrow it, a bundle narrows it further, and a request can ask for less but never more. The reasoning behind that design is in [MCP grants beat shared tokens](/blog/mcp-grants-beat-shared-tokens).

## A worked rollout

Imagine three teams and four registered servers: tickets, a knowledge base, finance reports and a code host.

1. An admin registers the four servers.
2. Create three bundles. Support gets the ticket and knowledge-base tools. Finance gets the report tools, limited to the read-style ones. Platform gets the code host and tickets.
3. Create a gateway key for each team's agents and attach it to the team's bundle.
4. Add one deny rule at the organization level for anything that deletes. It applies to everyone, including platform.
5. Point each team's agent configuration at its bundle endpoint with its own key.

Now the support agent's tool list contains support tools and nothing else. If someone asks it to open a repository, the tool is not on its list. If its key leaks, the blast radius is one team's tools, not the company's.

Unknown, inactive and not-attached bundles all answer in the same way, so a caller cannot guess slugs to find out what exists.

## Every call is recorded

Whichever team makes the call, each tool call is written to the same request log that holds your model calls. The row shows the tool name, the server, the outcome and the policy decision. Blocked calls use the same 446 status as a policy block on a model. When a security reviewer asks which team called which tool in March, the answer is a filter, not a research project. See [an audit trail your auditor can read](/blog/an-audit-trail-your-auditor-can-read) for how those records are presented once you build up history.

Tool definitions can also be pinned, so a server cannot change what a tool says it does after an admin approved it. That matters because tool descriptions are text agents read as instructions. See [MCP tool descriptions are untrusted input](/blog/mcp-tool-descriptions-are-untrusted-input).

## What to do now

- List your MCP servers and the teams that use each one.
- Write down the tool set each team actually needs. It is usually shorter than expected.
- Register the servers with the gateway and create one bundle per team.
- Attach each team's keys to its bundle, and retire shared tokens.
- Add organization-level blocks for destructive tools, and use deny grants for exceptions.
- Review the request log after a week to see which tools each team really calls.

## Good to know

A key attached to a bundle can use that bundle's endpoint only. That is the point, but plan for it: an agent that needs tools from two bundles needs a key attached to both. Tool names include the server name, so use lowercase letters, digits and single hyphens for server names, and your patterns stay simple.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

It needs Docker and no provider key. The console is at http://localhost:5173, and the demo includes a registered MCP server you can inspect under the MCP servers page. If you try bundles, star the repo or open an issue with what you would like to see next.

## Sources

- [MCP gateway guide](/guides/mcp-gateway): registration, policy, grants, bundles and the audit trail.
- [MCP admin API](/api-reference/mcp-admin): how to manage servers, grants and bundles from code.
- [Admin console overview](/admin-console/overview): where these pages live in the console.
- [Bounding a hijacked agent](/blog/bounding-a-hijacked-agent): why small tool sets limit the damage.

These statements are based on the OpenProxyAI documentation and the product's behavior at the post date.
