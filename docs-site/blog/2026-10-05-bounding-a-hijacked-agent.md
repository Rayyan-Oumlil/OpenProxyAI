---
slug: bounding-a-hijacked-agent
image: /img/blog/og/bounding-a-hijacked-agent.png
title: "You cannot stop every prompt injection, but you can cap what a hijacked agent does"
tags: [security, engineering]
description: Assume some prompt injection gets through. How OpenProxyAI caps spend, call rate, tool reach and side effects at the gateway, so a persuaded agent still has a small ceiling.
---

Prompt injection means text that the model reads as data but obeys as instructions. A web page, an email or a tool result can carry it. Filters catch known phrasing. They do not catch everything, and a determined attacker only needs one phrase you did not list.

So plan for the day one works. The question becomes: what is the worst a hijacked agent can do before someone notices? OpenProxyAI answers with controls that put a ceiling on that, enforced at the gateway where the model cannot argue with them.

{/* truncate */}

![An agent in the center with four caps around it: spend above, tools reachable on the left, calls per minute on the right, side-effect tools blocked after untrusted output below.](/img/blog/bounding-a-hijacked-agent.svg)

## The idea: bound damage, do not detect

The caps below do not try to read the agent's intent. They limit four things a hijacked agent could use: money, volume, reach and side effects. Each is enforced by the gateway, outside the model, so a persuaded model cannot talk its way past them.

OpenProxyAI also offers a scanner for tool descriptions and tool results that looks for known injection patterns. It is a useful filter on top. The caps are what hold when the filter misses.

## The layered table

| Control | What it bounds |
|---|---|
| Organization budget and rate limits | Dollars per day, requests and tokens per minute, for the whole organization |
| Per-user daily budget | Dollars per day for one user, shared by the keys that user owns |
| Team limits and monthly budget | Requests, tokens and dollars for a team |
| MCP call rate | Tool-call requests per minute, per API key |
| Grants and bundles | Which tools a key can list or call. See [the grants post](/blog/mcp-grants-beat-shared-tokens) |
| Tool pinning | Which tool definitions agents see |
| Trust rules | Side-effect tools after untrusted output |

## Spend and volume

Model limits are checked before the provider call, so a refused request costs nothing. When a limit fires, the gateway answers `429` with a JSON body that names the limit and a `Retry-After` header. A clear, machine-readable refusal means a well-written client backs off, and a looping agent stops burning money. See [rate limiting and budgets](/core-concepts/rate-limiting-and-budgets) for the full list of limits.

Give unattended agents their own user with a small daily budget. If that agent is hijacked, the worst day it can have is the budget you chose.

## Tool calls

Tool calls have their own rate limit per API key, separate from model quota, so tool use never starves chat and the other way round. Over the limit, the call is refused with `429` and `Retry-After`.

Reach is capped by [grants and bundles](/blog/mcp-grants-beat-shared-tokens): a refused call returns a clear JSON-RPC error and never reaches the tool server. Pinning stops a server from changing a tool description after you approved it. See [tool descriptions are untrusted input](/blog/mcp-tool-descriptions-are-untrusted-input).

## Side effects: taint tracking

This is the structural defence. The attack it targets: the agent reads untrusted content through one tool, the content tells it to call a tool with side effects (send, write, delete), and the agent obeys.

You declare two kinds of rule per tool pattern. Mark the tools whose output you trust as `trusted_output`. Mark the tools with side effects as `sink`.

- Results from any tool that is not trusted mark the session as tainted. Untrusted is the default.
- A `sink` refuses to run in a tainted session, and also when there is no session at all, so a client cannot drop the session to launder the taint.
- For plain chat completions, if the conversation already holds output from an untrusted tool, sink tools are removed before the model sees them.

A refused sink returns a JSON-RPC error, is recorded in the audit log with status `446`, and never reaches the tool server. The agent can read the web and it can send email, but not email after reading the web.

## What to do now

1. Set a daily budget on users who run unattended agents, and a monthly budget on teams.
2. Set team limits in the policy.
3. Lower the MCP call rate if your agents need far fewer calls per minute.
4. Mark every tool with side effects as `sink`, and mark only tools whose output you trust as `trusted_output`.
5. Put unattended keys in bundles with the smallest tool list that works.
6. Set pinning to enforce for servers you do not control.
7. Watch your audit log and webhooks for repeated limit hits and blocked sinks: they are the early signal that something is off.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

Needs Docker, no provider key. Console at http://localhost:5173. If this is useful, star the repo or open an issue with the controls you would add.

## Sources

- [Rate limiting and budgets](/core-concepts/rate-limiting-and-budgets): the limits and daily reset.
- [MCP gateway guide](/guides/mcp-gateway): pinning, scanning, grants, trust rules, rate limit.
- [MCP admin API](/api-reference/mcp-admin): trust rule and grant request bodies.
- [Errors and status codes](/api-reference/errors-and-status-codes): `402` and `429`.

These statements are based on OpenProxyAI's behavior at the post date.
