---
slug: mcp-grants-beat-shared-tokens
title: "Per-user, per-tool grants beat one shared MCP service token"
tags: [security, architecture]
description: A shared MCP token makes every agent as powerful as the most powerful user. How per-subject grants, deny-wins rules, request scoping and bundles shrink the blast radius.
---

Most teams connect agents to MCP tool servers (Model Context Protocol, the standard way agents call tools) with one service token. It is easy to set up. It also means every agent, for every user, can do whatever the most privileged user can do. If one agent is tricked or its key leaks, the damage is the token's full reach, not the user's.

The fix is to decide access per caller and per tool, and to make each extra control only able to remove access. This post shows how the OpenProxyAI MCP gateway does that.

{/* truncate */}

![Diagram of four layers (organization policy, grants, request scope header, bundle endpoint) that each can only remove tools from the set the previous layer allowed.](/img/blog/mcp-grants-beat-shared-tokens.svg)

## The problem: one token, one blast radius

With a shared token, authorization lives in the tool server, and the tool server sees one identity. It cannot tell a support agent from an admin's coding agent. So you either give the token everything, or you give each agent its own server and token and manage them by hand.

The blast radius of a hijacked agent is then the token's scope. A prompt injection (text in a web page, ticket or tool description that tells the model to do something else) does not need to break anything. It only needs the agent to be allowed to do the thing.

## How the layers work

The gateway authenticates the agent with an OpenProxyAI API key, then checks every tool listing and tool call against four layers, in order:

| Layer | Rule |
|---|---|
| 1. Organization policy | The blocked list wins, then the allowlist |
| 2. Grants | A matching deny wins. If any allow grant applies to the caller, the tool must match one |
| 3. Request scope | The client may send the `X-OpenProxy-MCP-Tools` header to ask for fewer tools |
| 4. Bundle | The tool must be in the bundle named in the URL |

Details that matter:

- **Subjects.** A grant targets a role, a team, a user or an API key. All grants that apply to the caller are combined.
- **Deny wins.** A matching deny beats any allow, at any level.
- **Allow grants are opt-in.** Turning grants on breaks nobody. The first allow grant for a subject starts restricting that subject.
- **Scope only intersects.** A client can ask for less than it has. Asking for more changes nothing, and a malformed header is rejected rather than ignored.
- **Bundles confine a key.** A bundle is a named list of tool patterns served at its own endpoint. Once a key is attached to a bundle, the general MCP endpoint is closed to it. Unknown and not-attached bundles give the same answer, so names cannot be guessed.
- **Patterns** are globs over server and tool name, such as `github__*`.
- **Changes are immediate.** Removing a grant takes effect on the next call.

Tools a layer would refuse are left out of the tool list. A refused call returns a JSON-RPC error with a reason code, is recorded with status `446`, and never reaches the tool server.

## A worked example

Goal: a ticket-triage agent may search GitHub and file Jira issues. Developers in general may use GitHub and create Jira issues. Nobody on that key may delete anything on GitHub.

- Allow the `developer` role on `github__*`.
- Allow the `developer` role on `jira__create_issue`.
- Deny `github__delete_*` on the triage agent's API key.
- Create a bundle called `triage-bot` with three tools: `github__search`, `github__get_issue`, `jira__create_issue`, and attach the key to it.

The agent now connects to its bundle endpoint. What happens next:

| Call | Result | Why |
|---|---|---|
| `github__search` | allowed | Role allow, in bundle |
| `github__delete_repo` | refused (`tool_grant_denied`) | Deny on the key, checked first |
| `jira__search` | refused (`tool_not_granted`) | Allow grants exist and none match |
| `github__list_prs` | refused (`tool_not_in_bundle`) | Passes grants, not in the bundle |
| any request on the general endpoint | HTTP 403 | The key is confined to bundles |

Now the agent narrows itself for one task by sending `X-OpenProxy-MCP-Tools: github__search`. A call to `github__get_issue` is in the bundle and granted, but outside the scope, so it is refused with `tool_out_of_scope`.

If the triage agent is hijacked, the worst it can do is search GitHub and create Jira issues, for as long as its key lives. A shared token would have given it everything the token could do.

## What to do now

1. List which tools each agent actually needs. Write that as an allow grant for its key, or as a bundle.
2. Add deny grants for destructive patterns (`*__delete_*`, `*__drop_*`) on every key that does not need them.
3. Attach keys to bundles for unattended agents, so the general endpoint is closed to them.
4. Have clients send `X-OpenProxy-MCP-Tools` per task.
5. Read the audit rows for refused calls to find agents asking for more than you thought.

Good to know: grants decide which tools reach a server, so mint one API key per agent and the rights follow that agent.

Related reading: [MCP tool descriptions are untrusted input](/blog/mcp-tool-descriptions-are-untrusted-input) and [MCP 2026-07-28 for gateway operators](/blog/mcp-2026-07-28-for-gateway-operators).

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

Needs Docker, no provider key. Console at http://localhost:5173. Star the repo if you want to follow along, or open an issue with the grants you need.

## Sources

- [MCP gateway guide](/guides/mcp-gateway): layers, bundles, error codes.
- [MCP admin API](/api-reference/mcp-admin): grant and bundle request bodies.
- [API keys](/api-reference/api-keys): how keys are created.
- [Errors and status codes](/api-reference/errors-and-status-codes): the status code table.

These statements are based on OpenProxyAI's behavior at the post date.
