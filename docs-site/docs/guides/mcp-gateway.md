---
title: MCP gateway
description: Put every MCP tool server behind one endpoint, with tool policies and an audit row per call.
---

# MCP gateway

Agents that use the [Model Context Protocol](https://modelcontextprotocol.io) usually connect to each tool server separately, with a separate credential for each. The OpenProxyAI MCP gateway gives them **one endpoint and one API key** for all of your organization's tool servers. Every tool call is checked against your policy and written to the audit log, like a model call.

- **Endpoint:** `POST /v1/mcp`. This is the MCP Streamable HTTP transport, protocol `2025-11-25` (older `2025-06-18` and `2025-03-26` clients are also accepted).
- **Authentication:** an OpenProxyAI API key, sent as `Authorization: Bearer opai_…`.
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
| `PATCH` | `/api/v1/mcp-servers/{id}` (`{"is_active": false}`) | admin |
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

## Audit trail

Every `tools/call` writes a row to the request log, with:

- **model:** the namespaced tool name
- **provider:** `mcp:<server>`
- **status_code:** `200`, `446`, `502` or `400`
- **metadata:** `request_metadata.type = "mcp_tool_call"` plus the policy decision

Tool calls therefore appear in the log viewer, analytics and compliance exports next to model calls.
