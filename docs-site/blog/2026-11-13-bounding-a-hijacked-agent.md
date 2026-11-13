---
slug: bounding-a-hijacked-agent
title: "You cannot stop every prompt injection, but you can cap what a hijacked agent does"
tags: [security, engineering]
description: Assume some prompt injection gets through. Which controls in OpenProxyAI cap spend, call rate, tool reach and side effects, what each one returns when it fires, and what none of them can do.
---

Prompt injection means text that the model reads as data but obeys as instructions. A web page, an email or a tool result can carry it. Filters catch known phrasing. They do not catch everything, and a determined attacker only needs one phrase you did not list.

So plan for the day one works. The question becomes: what is the worst a hijacked agent can do before someone notices? This post walks through the controls in OpenProxyAI that put a ceiling on that, what each returns when it fires, and what each one does not cover.

{/* truncate */}

![An agent in the center with four caps around it: spend above, tools reachable on the left, calls per minute on the right, side-effect tools blocked after untrusted output below.](/img/blog/bounding-a-hijacked-agent.svg)

## The idea: bound damage, do not detect

None of the caps below detect an injection. They do not read the agent's intent. They limit four things a hijacked agent could use: money, volume, reach and side effects. Each is enforced by the gateway, outside the model, so a persuaded model cannot talk its way past them.

OpenProxyAI also ships a deterministic scanner for tool descriptions and tool results (`scan_mode` per MCP server). It matches known patterns such as "ignore previous instructions" phrasing, invisible Unicode and long base64 runs, and its default is to log only. It is worth turning on, but the guide itself says heuristics have false positives. It is a filter, not a cap, so it is not in the table.

## The layered table

| Control | What it bounds | How to configure | Limit |
|---|---|---|---|
| Daily org budget and rate | Total dollars per day, requests and tokens per minute, for the whole org | `DEFAULT_BUDGET_DAILY_USD` (50.0), `DEFAULT_RATE_LIMIT_RPM` (60), `DEFAULT_RATE_LIMIT_TPM` (100000) | Env settings, same for every org on the deployment. Not per key |
| Per-user daily budget | Dollars per day for one user, so for the keys that user owns | `budget_daily_usd` on the user | Only if set |
| Per-team limits | Requests and tokens per minute for a team | `per_team_limits` in the org policy, for example `{"rpm": 60, "tpm": 50000}` | Applies to requests with a team |
| Team monthly budget | Dollars per month for a team | `budget_monthly_usd` on the team | Only if set |
| MCP rate limit | Tool-call requests per minute, per API key | `MCP_RATE_LIMIT_PER_MINUTE` (120) | Fixed window. Counts every MCP request |
| Grants and bundles | Which tools a key can list or call | Admin API, see [the grants post](/blog/mcp-grants-beat-shared-tokens) | Matches tool names, not arguments |
| Tool pinning | Which tool definitions agents see | `pin_mode` per server (`warn` default, `enforce`) | Protects definitions, not results |
| Trust rules (taint) | Side-effect tools after untrusted output | `sink` and `trusted_output` rules | Only tools you mark as `sink` |

## Spend and volume

The LLM limits are checked in one place before the provider call (`backend/app/services/rate_limiter.py`, called from the request gate). The order is: org requests per minute, org tokens per minute, org daily budget, user daily budget, team requests and tokens per minute, team monthly budget, then per-model limits when the policy sets them.

When one fires, the gateway answers `429` with a JSON body naming the limit, plus a `Retry-After` header:

```json
{"error": "rate_limit_exceeded", "limit_type": "user_budget_daily_usd", "detail": "Daily user budget reached. Resets in 3600 seconds.", "retry_after": 3600}
```

That body is built from the code, with a made-up number of seconds. The `limit_type` values include `requests_per_minute`, `tokens_per_minute`, `budget_daily_usd`, `user_budget_daily_usd`, `team_requests_per_minute`, `team_tokens_per_minute` and `team_budget_monthly_usd`.

The streaming path has an extra check. Before it streams, it estimates the cost of the request (prompt plus `max_tokens`, or 4096 if unset) and answers `402` with `budget_exceeded` if that estimate is more than what is left of the org or user daily budget. The docs list `402` for budgets and `429` for rate limits. The main gate in the code returns `429` with a `limit_type` for both. Match on `limit_type`, not only on the status code.

Spend is added to the counters after a call finishes, from the audit step. The check before a call compares the counter to the budget. So requests already in flight when the budget is reached will still complete. The overshoot is bounded by what runs concurrently, not zero.

The per-minute counters are fixed windows (the minute number is part of the key). A burst split across a window boundary can briefly pass the limit. Treat the numbers as ceilings per window, not smooth rates.

## Tool calls

Tool calls have their own counter, so tool use does not use up the model quota (and the other way round). Each API key gets `MCP_RATE_LIMIT_PER_MINUTE` requests per minute, 120 by default. The check runs before the body is parsed, so every POST counts, including `ping`. Over the limit:

```json
{"jsonrpc": "2.0", "id": null, "error": {"code": -32006, "message": "Rate limit exceeded"}}
```

It comes with HTTP 429 and `Retry-After`. If Redis fails, the error propagates instead of letting traffic through unmetered (stated in `mcp_rate_limit.py`).

Reach is capped by [grants and bundles](/blog/mcp-grants-beat-shared-tokens): refused calls return `-32001` with reason codes such as `tool_not_granted`. Pinning adds `-32004` under `pin_mode: enforce` for tools whose definition is pending, drifted or blocked. This stops a server from changing a tool description after you approved it. It does not stop an injection that arrives in a tool result.

## Side effects: taint tracking

This is the structural defence. The attack it targets: the agent reads untrusted content through one tool, the content tells it to call a tool with side effects (send, write, delete), and the agent obeys.

You declare two things per tool pattern (`POST /api/v1/mcp-trust-rules`):

```json
{"tool_pattern": "web__fetch", "rule": "trusted_output"}
```

```json
{"tool_pattern": "email__send", "rule": "sink"}
```

The rules in `mcp_taint.py`:

- Every result from a tool that is not `trusted_output` marks the MCP session as tainted. Untrusted is the default.
- A `sink` refuses to run in a tainted session. It also refuses with no session at all, so a client cannot drop the session id to launder the taint.
- Blocked or failed calls do not taint. Only a delivered result does.
- Sessions live in Redis for one hour and are bound to the key that opened them.
- For plain chat completions, if the conversation holds a tool message from an untrusted tool, sink tools are removed from the request before the model sees them. This follows the policy `enforcement_mode`: `off` does nothing, `log_only` reports only.

A refused sink returns `-32009`, with reason code `sink_blocked_tainted_session` or `sink_requires_session`, HTTP 200 with status `446` in the audit row, and the call never reaches the upstream.

## What this does not do

- **Nothing here detects an injection.** The caps work the same whether the instruction was malicious or not.
- **LLM limits are not per API key.** They are per org, per user and per team. A hijacked agent running on a key shares the user's budget with that user's other work.
- **Org rate and budget defaults come from environment settings.** No per-org override exists in the code paths read for this post.
- **Budgets can overshoot** by the cost of calls in flight, and the window limits are fixed windows.
- **Taint only protects tools you mark as `sink`.** An unmarked tool with side effects is not covered. If nothing is marked, nothing is blocked.
- **Taint does not see everything.** It tracks tool results in an MCP session or a chat conversation. An injection in the user's own message, or in a result from a tool you marked `trusted_output`, does not taint.
- **A sink in a clean session runs.** Taint is a gate on a bad sequence, not a review of each call.
- **Data can still leave through allowed read tools or the model's own answer.** These controls cap tool reach, not what the model says.
- **No alert on its own.** Limits return errors. Watch your audit log and webhooks for repeated `limit_type` or `-32009` events to learn that something is wrong.

## What to do now

1. Set `budget_daily_usd` on users who run unattended agents, and `budget_monthly_usd` on teams.
2. Set `per_team_limits` in the policy.
3. Lower `MCP_RATE_LIMIT_PER_MINUTE` if your agents need far fewer than 120 calls a minute.
4. Mark every tool with side effects as `sink`, and mark only tools whose output you trust as `trusted_output`.
5. Put unattended keys in bundles with the smallest tool list that works.
6. Set `pin_mode` to `enforce` for servers you do not control. See [tool descriptions are untrusted input](/blog/mcp-tool-descriptions-are-untrusted-input).

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

Needs Docker, no provider key. Console at http://localhost:5173.

## Sources

- [Rate limiting and budgets](/core-concepts/rate-limiting-and-budgets): the limits and daily reset.
- [MCP gateway guide](/guides/mcp-gateway): pinning, scanning, grants, trust rules, rate limit.
- [MCP admin API](/api-reference/mcp-admin): trust rule and grant request bodies.
- [Errors and status codes](/api-reference/errors-and-status-codes): `402` and `429`.

These statements are based on the OpenProxyAI source (`rate_limiter.py`, `request_gate.py`, `audit_logger.py`, `llm_service.py`, `mcp_rate_limit.py`, `mcp_taint.py`, `mcp_gateway.py`, the MCP routes) and its tests, read on 2026-11-13. Example bodies are built from that code, not captured from a running system.
