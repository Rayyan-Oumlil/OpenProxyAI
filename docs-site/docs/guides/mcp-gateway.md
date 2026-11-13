---
title: MCP gateway
description: Put every MCP tool server behind one endpoint, with tool policies and an audit row per call.
---

# MCP gateway

Agents that use the [Model Context Protocol](https://modelcontextprotocol.io) usually connect to each tool server separately, with a separate credential for each. The OpenProxyAI MCP gateway gives them **one endpoint and one API key** for all of your organization's tool servers. Every tool call is checked against your policy and written to the audit log, like a model call.

- **Endpoint:** `POST /v1/mcp`. This is the MCP Streamable HTTP transport, protocol `2025-11-25` (older `2025-06-18` and `2025-03-26` clients are also accepted).
- **Authentication:** an OpenProxyAI API key with the `proxy:mcp` permission, sent as `Authorization: Bearer opai_…`.
- **Supported methods:** `initialize`, `ping`, `tools/list` and `tools/call`.

## 1. Register your tool servers

Only admins can register servers. The server's URL must use HTTPS and resolve to a public address. The optional `auth_header` is the credential the gateway sends to that server. It is stored encrypted and is never returned by the API.

```bash
curl -X POST https://gateway.your-company.com/api/v1/mcp-servers \
  -H "Authorization: Bearer $ADMIN_JWT" -H "Content-Type: application/json" \
  -d '{"name": "github", "url": "https://mcp.github.example.com/mcp", "auth_header": "Bearer ghp_…"}'
```

| Method | Path | Who |
|---|---|---|
| `GET` | `/api/v1/mcp-servers` | any member |
| `POST` | `/api/v1/mcp-servers` | admin |
| `PATCH` | `/api/v1/mcp-servers/{id}` (`is_active`, `pin_mode`, `scan_mode`) | admin |
| `DELETE` | `/api/v1/mcp-servers/{id}` | admin |

Server names may only use lowercase letters, digits and single hyphens. That rule keeps the tool names below unambiguous. Every create, update and delete is recorded in the admin audit log.

## 2. Point your agent at the gateway

Tools from all active servers appear in one list, named `<server>__<tool>`. For example, the `search` tool on the `github` server appears as `github__search`.

```json
{
  "mcpServers": {
    "company-tools": {
      "url": "https://gateway.your-company.com/v1/mcp",
      "headers": { "Authorization": "Bearer opai_…" }
    }
  }
}
```

**Your agent's key never leaves the gateway.** The `Authorization` header above authenticates the agent to the gateway only. The gateway does not pass it, or any other header from the agent (cookies, `X-API-Key`, the agent's `Mcp-Session-Id`, forwarding headers), to a tool server. Each server receives only the `auth_header` an admin stored for that server, or no credential at all if none was stored, and never another server's. Upstream sessions are the gateway's own. A regression test (`tests/test_mcp_token_isolation.py`) runs the real route and client against a recording server to hold this.

If a server can't be reached, `tools/list` still returns the tools from the other servers. The unreachable servers are listed in `result._meta["openproxyai/unavailableServers"]`, so a single broken server never empties your agent's toolbox.

## 3. Control which tools agents can use

Tool policy is part of the organization's [policy configuration](../core-concepts/policies-and-guardrails). It follows the same `off` / `log_only` / `enforce` modes as your model policy.

```bash
curl -X PATCH https://gateway.your-company.com/api/v1/organizations/current/policy \
  -H "Authorization: Bearer $ADMIN_JWT" -H "Content-Type: application/json" \
  -d '{"mcp_allowed_tools": ["github__*", "jira__create_issue"], "mcp_blocked_tools": ["*__delete_*"]}'
```

The gateway checks these rules in order:

1. **Blocked patterns** win. A tool matching `mcp_blocked_tools` is always refused.
2. **Allowlist:** if `mcp_allowed_tools` is not empty, a tool must match one of its patterns.
3. **Guardrails on arguments:** the call's arguments go through the same blocked-keyword and PII checks as prompts.

In `enforce` mode, tools the policy would refuse are left out of `tools/list`. A refused `tools/call` is never forwarded to the server. It returns a JSON-RPC error:

```json
{"jsonrpc": "2.0", "id": 7, "error": {"code": -32001, "message": "Tool github__delete_repo is blocked by organization policy.", "data": {"reason_code": "tool_blocked", "triggered_rules": ["mcp_blocked_tools"]}}}
```

| Code | Meaning |
|---|---|
| `-32001` | Blocked by policy. It is recorded with status `446`, the same code as a model guardrail block. |
| `-32002` | The upstream server failed or couldn't be reached. It is recorded with status `502`. |
| `-32602` | Unknown tool, or the arguments are not a JSON object. |
| `-32601` | Method not supported (resources and prompts are not proxied). |

## 4. Pin tool definitions so they cannot change under you

A tool description is text the agent reads as instructions. If a server changes it after you approved it, the agent's behavior changes and no code review saw it. **Pinning** stores a hash of each tool's whole definition and serves only what an admin approved. Set it per server with `pin_mode`:

| `pin_mode` | What happens |
|---|---|
| `off` | Live definitions are served. No pinning. |
| `warn` (default) | Trust on first use: a new tool is approved automatically. A later change marks it `drifted`; agents keep getting the approved version and calls still go through, flagged in the audit row. |
| `enforce` | Nothing is trusted until an admin approves it. `pending`, `drifted` and `blocked` tools are hidden, and calls to them are refused with `-32004`. |

A tool an admin blocked is refused in `warn` and `enforce` alike. Every 15 minutes the gateway re-fetches each pinned server's tool list, so drift is found even when no agent is calling (`MCP_TOOL_SYNC_INTERVAL_MINUTES`; turn it off with `MCP_TOOL_SYNC_ENABLED=false`). Review tools in the console under MCP servers, or with the [MCP admin API](/api-reference/mcp-admin).

## 5. Scan descriptions and results for injection

Descriptions and results are both text the server controls. Set `scan_mode` per server: `off`, `log` (report only, the default), `redact` (sanitise and serve) or `block` (withhold a result that looks like an injection, error `-32007`).

The scanner is deterministic and makes no model call. It looks for invisible Unicode tag characters, zero-width and bidi control characters, "ignore previous instructions" phrasing, hidden `<important>`/`<system>` markup, "do not tell the user", markdown images whose URL carries a long query string, long base64 runs, and oversized or deeply nested payloads. Findings are category names only; the matched text is not copied anywhere. Heuristics have false positives, which is why `log` is the default.

## 6. Narrow who can call what: grants, scope and bundles

Each layer can only remove tools the previous one allowed.

1. **Organization policy:** `mcp_allowed_tools` and `mcp_blocked_tools`, as above.
2. **Grants:** `allow` or `deny` rules for a role, team, user or API key. A matching `deny` always wins. If any `allow` grant applies to the caller, the tool must match one of them; with no applicable `allow` grant the caller is not restricted, so turning grants on breaks nobody.
3. **Request scope:** a client may send `X-OpenProxy-MCP-Tools: github__*,jira__create_issue` to ask for less than it was granted, never more.

Patterns are globs over the namespaced tool name (`github__*`, `*__delete_*`).

A **bundle** is a named set of tool patterns exposed at its own endpoint, `POST /v1/mcp/{slug}`. A key attached to at least one bundle can reach tools only through an attached bundle's endpoint; the bare `/v1/mcp` is refused for it, otherwise attaching a bundle would confine nothing. Unknown, inactive and not-attached bundles all answer the same way, so slugs cannot be probed.

## 7. Stop an injected result from steering a tool with side effects

Mark tools with a trust rule:

- `trusted_output`: results from this tool do not taint the session.
- `sink`: a tool with side effects (send, write, delete).

Every result from a tool that is not `trusted_output` taints the MCP **session**. A `sink` refuses to run in a tainted session, or with no session at all (so a client cannot drop the session id to launder the taint), error `-32009`. Sessions live in Redis for an hour and are bound to the key that opened them. The same rule applies to plain chat completions: if the conversation holds a tool message from an untrusted tool, sink tools are removed from the request before the model sees them.

## Rate limit

Each API key gets 120 MCP requests per minute (`MCP_RATE_LIMIT_PER_MINUTE`), counted apart from your model quota. Over the limit, the answer is JSON-RPC `-32006` with a `Retry-After` header.

## More error codes

| Code | Meaning |
|---|---|
| `-32004` | Tool not approved (pending, drifted or blocked) under `pin_mode: enforce`. |
| `-32005` | HTTP 403. The request's `Origin` is not in `CORS_ORIGINS` (browsers always send one; agents send none), the API key lacks the `proxy:mcp` permission, or the key is confined to bundles and called the bare `/v1/mcp`. |
| `-32006` | HTTP 429. MCP rate limit reached. |
| `-32007` | Result withheld by `scan_mode: block`. |
| `-32008` | Bundle not found for this key. |
| `-32009` | A sink was refused in a tainted or session-less context. |

## Audit trail

Every `tools/call` writes a row to the request log, with:

- **model:** the namespaced tool name
- **provider:** `mcp:<server>`
- **status_code:** `200`, `446`, `502` or `400`
- **metadata:** `request_metadata.type = "mcp_tool_call"` plus the policy decision

Tool calls therefore appear in the log viewer, analytics and compliance exports next to model calls.
