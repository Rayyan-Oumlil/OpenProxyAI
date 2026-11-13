---
slug: mcp-grants-beat-shared-tokens
title: "Per-user, per-tool grants beat one shared MCP service token"
tags: [security, architecture]
description: A shared MCP token makes every agent as powerful as the most powerful user. How per-subject grants, deny-wins rules, request scoping and bundles shrink the blast radius, with real request bodies and error codes.
---

Most teams connect agents to MCP tool servers (Model Context Protocol, the standard way agents call tools) with one service token. It is easy to set up. It also means every agent, for every user, can do whatever the most privileged user can do. If one agent is tricked or its key leaks, the damage is the token's full reach, not the user's.

The fix is to decide access per caller and per tool, and to make each extra control only able to remove access. This post shows how the OpenProxyAI MCP gateway does that, with request bodies that match the real schemas.

{/* truncate */}

![Diagram of four layers (organization policy, grants, request scope header, bundle endpoint) that each can only remove tools from the set the previous layer allowed.](/img/blog/mcp-grants-beat-shared-tokens.svg)

## The problem: one token, one blast radius

With a shared token, authorization lives in the tool server, and the tool server sees one identity. It cannot tell a support agent from an admin's coding agent. So you either give the token everything, or you give each agent its own server and token and manage them by hand.

The blast radius of a hijacked agent is then the token's scope. A prompt injection (text in a web page, ticket or tool description that tells the model to do something else) does not need to break anything. It only needs the agent to be allowed to do the thing.

## How the layers work

The gateway authenticates the agent with an OpenProxyAI API key, then checks every `tools/list` and `tools/call` against layers, in this order (`backend/app/services/mcp_grants.py`):

| Layer | Rule | Reason code on refusal |
|---|---|---|
| 1. Organization policy | `mcp_blocked_tools` wins, then `mcp_allowed_tools` | `tool_blocked` |
| 2. Grants | A matching `deny` wins. If any `allow` grant applies to the caller, the tool must match one | `tool_grant_denied`, `tool_not_granted` |
| 3. Request scope | Header `X-OpenProxy-MCP-Tools`: the tool must match one of its patterns | `tool_out_of_scope` |
| 4. Bundle | The tool must match a pattern of the bundle in the URL | `tool_not_in_bundle` |

Details that matter:

- **Subjects.** A grant targets a `role` (`admin`, `developer`, `viewer`), a `team`, a `user` or an `api_key`. All grants that apply to the caller are combined. A grant for a team applies only if the API key has a team.
- **Deny wins.** A matching `deny` beats any `allow`, at any level. A test checks this with an allow on a team and a deny on an API key.
- **Allow grants are opt-in.** If no `allow` grant applies to the caller, the caller is not restricted by layer 2. Turning grants on breaks nobody. The first `allow` grant for a subject starts restricting that subject.
- **Scope only intersects.** A client may send the header to ask for less than it has. A larger list changes nothing. A malformed or repeated header is a 400, never ignored, because ignoring it would give a wider tool set than the client asked for. Property tests assert that scope and bundle never widen access.
- **Bundles confine a key.** A bundle is a named list of tool patterns served at `POST /v1/mcp/{slug}`. Once a key is attached to any bundle, the bare `/v1/mcp` endpoint is refused for it. Unknown, inactive and not-attached bundles all give the same answer, so slugs cannot be guessed.
- **Patterns** are globs over `<server>__<tool>`, such as `github__*`.
- **Grants are read on every request**, so removing a grant takes effect on the next call.

On `tools/list`, tools a layer would refuse are left out. A `tools/call` refused by layers 1 to 4 is a JSON-RPC error `-32001`, recorded with status `446`, and the call never reaches the upstream server. The audit row records the allow, deny, scope and bundle patterns that applied.

## A worked example

Goal: a ticket-triage agent may search GitHub and file Jira issues. Developers in general may use GitHub and create Jira issues. Nobody on that key may delete anything on GitHub.

Create the grants (admin JWT, `POST /api/v1/mcp-grants`):

```json
{"subject_type": "role", "subject_id": "developer", "tool_pattern": "github__*", "effect": "allow"}
```

```json
{"subject_type": "role", "subject_id": "developer", "tool_pattern": "jira__create_issue", "effect": "allow"}
```

```json
{"subject_type": "api_key", "subject_id": "3f2a9c1e-0000-4000-8000-000000000001", "tool_pattern": "github__delete_*", "effect": "deny"}
```

The `subject_id` for an API key is its UUID (the one above is a placeholder). Then create a bundle (`POST /api/v1/mcp-bundles`) and attach the key (`PUT /api/v1/mcp-bundles/{bundle_id}/keys/{api_key_id}`, no body):

```json
{"slug": "triage-bot", "name": "Triage bot", "description": "Read issues, file tickets",
 "tools": ["github__search", "github__get_issue", "jira__create_issue"]}
```

The agent now connects to `POST /v1/mcp/triage-bot`. What happens next, per the code and the route tests:

| Call | Result | Why |
|---|---|---|
| `github__search` | allowed | Role allow, in bundle |
| `github__delete_repo` | `tool_grant_denied` | Deny on the key, checked first |
| `jira__search` | `tool_not_granted` | Allow grants exist and none match |
| `github__list_prs` | `tool_not_in_bundle` | Passes grants (`github__*`), not in the bundle |
| any request on bare `/v1/mcp` | HTTP 403, `-32005` | The key is confined to bundles |

The two refusals differ by layer. `jira__search` fails at grants. `github__list_prs` passes grants and fails the bundle check.

Now the agent narrows itself for one task by sending `X-OpenProxy-MCP-Tools: github__search`. A call to `github__get_issue` is in the bundle and granted, but outside the scope. The body below is built from the route code and the scope test, not captured from a running stack:

```json
{"jsonrpc": "2.0", "id": 7, "error": {"code": -32001, "message": "Tool github__get_issue is not available to this caller", "data": {"reason_code": "tool_out_of_scope", "triggered_rules": ["tool_grants"]}}}
```

Refused with the bare endpoint, same code path:

```json
{"jsonrpc": "2.0", "id": null, "error": {"code": -32005, "message": "This API key is confined to MCP bundles: use /v1/mcp/{bundle}"}}
```

If the triage agent is hijacked, the worst it can do is search GitHub and create Jira issues, for as long as its key lives. A shared token would have given it everything the token could do.

## What this does not do

- **The upstream credential is still shared.** The gateway stores one `auth_header` per tool server and sends it on every allowed call. Grants decide which tools reach the server. The server still sees one identity. Per-user identity at the upstream is not part of this.
- **Grants match tool names, not arguments.** A grant on `github__create_issue` cannot say "only in this repository". Argument checks exist in organization policy (blocked keywords, PII), not in grants.
- **Patterns are not checked against real tools.** The API only validates the characters of a pattern. A typo matches nothing, so a `deny` with a typo denies nothing.
- **Role grants follow the key owner's role.** Rights follow whoever owns the key, so mint keys per agent, not per team.
- **It is not an injection detector.** It limits what a tricked agent can reach. It does not notice the trick. See the companion post on bounding a hijacked agent.

## What to do now

1. List which tools each agent actually needs. Write that as an `allow` grant for its key, or as a bundle.
2. Add `deny` grants for destructive patterns (`*__delete_*`, `*__drop_*`) on every key that does not need them.
3. Attach keys to bundles for unattended agents, so the bare endpoint is closed to them.
4. Have clients send `X-OpenProxy-MCP-Tools` per task.
5. Read the audit rows for `tool_not_granted` and `tool_out_of_scope` to find agents asking for more than you thought.

Related reading: [MCP tool descriptions are untrusted input](/blog/mcp-tool-descriptions-are-untrusted-input) and [MCP 2026-07-28 for gateway operators](/blog/mcp-2026-07-28-for-gateway-operators).

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

Needs Docker, no provider key. Console at http://localhost:5173.

## Sources

- [MCP gateway guide](/guides/mcp-gateway): layers, bundles, error codes (section 6 and the error code table).
- [MCP admin API](/api-reference/mcp-admin): grant and bundle request bodies.
- [API keys](/api-reference/api-keys): how keys are created.
- [Errors and status codes](/api-reference/errors-and-status-codes): the status code table.

These statements are based on the OpenProxyAI source (`mcp_grants.py`, `mcp_bundles.py`, the MCP routes and schemas) and its tests (`test_mcp_grants.py`, `test_mcp_routes.py`, `test_mcp_bundles_db.py`), read on 2026-11-13. Example responses are built from that code, not captured from a running system.
