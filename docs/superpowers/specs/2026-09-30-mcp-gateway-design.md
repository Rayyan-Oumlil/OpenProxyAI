# MCP Gateway (backlog B1) — Design

- **Date:** 2026-09-30
- **Status:** Approved under standing authorization (owner delegated decisions)
- **Protocol:** MCP 2025-11-25, Streamable HTTP transport, JSON-RPC 2.0.

## Goal

One MCP endpoint per organisation that fronts every MCP tool server the org registers, so agents get
one URL and one API key, and every tool call is policy-checked and audited like a model call.

## Scope (v1)

| In | Out (later backlog) |
|---|---|
| `POST /v1/mcp`: `initialize`, `notifications/*`, `ping`, `tools/list`, `tools/call` | Resources, prompts, sampling, server→client streams (`GET /v1/mcp` returns 405) |
| Admin API to register/list/toggle/delete upstream servers | Admin console UI |
| Tool allow/block patterns + keyword/PII guardrails on arguments | Guardrails on tool *results* (B4) |
| Audit row per `tools/call` in `request_logs` | Per-agent identity beyond the API key (B3), A2A (B5) |

## Components

| Unit | Responsibility |
|---|---|
| `app/utils/ssrf.py` | HTTPS-only URL check that rejects private, loopback, link-local and CGN addresses (moved from `webhook_service`, shared). |
| `app/models/mcp_server.py` + migration `u2p3q4r5s6t7` | `mcp_servers(id, org_id, name, url, auth_header_encrypted, is_active, created_at)`, unique `(org_id, name)`, RLS `FOR ALL` + `FORCE`. |
| `app/services/mcp_client.py` | One upstream call = `initialize` → `notifications/initialized` → request, carrying `Mcp-Session-Id` and `MCP-Protocol-Version`; parses JSON or SSE responses; raises `McpUpstreamError` on transport/JSON-RPC errors. |
| `PolicyConfig.mcp_allowed_tools` / `mcp_blocked_tools` + `PolicyService.evaluate_tool_call()` | fnmatch patterns on the namespaced tool name; then the existing keyword/PII checks on the JSON-serialised arguments. Follows `enforcement_mode` (off / log_only / enforce) like model policy. |
| `app/services/mcp_gateway.py` | `list_tools()` aggregates and namespaces (`<server>__<tool>`), filters by policy, reports failed servers in `_meta`. `call_tool()` resolves the server, applies policy, forwards, returns the upstream result or a JSON-RPC error. |
| `app/routes/mcp.py` | JSON-RPC dispatch on `POST /v1/mcp` (API-key auth), 405 on `GET`/`DELETE`, fire-and-forget audit row per `tools/call`. |
| `app/routes/mcp_servers.py` | `GET/POST /api/v1/mcp-servers`, `PATCH/DELETE /api/v1/mcp-servers/{id}` (admin for writes). Auth header is write-only (`has_auth` in responses). |

## Decisions

| # | Decision | Why |
|---|---|---|
| M1 | Stateless gateway: each upstream call runs its own initialize handshake; the gateway issues a fresh `Mcp-Session-Id` on `initialize` but does not require it afterwards. | Correct with any compliant upstream; no session store to scale. Cost: one extra round-trip per call (acceptable for v1). |
| M2 | Tool names are `<server>__<tool>`; server names are `^[a-z0-9-]{1,40}$` so the split on the first `__` is unambiguous. | Clients see one flat tool list without collisions. |
| M3 | A failing upstream during `tools/list` is reported in `result._meta["openproxyai/unavailableServers"]`; the other servers' tools are still returned. | One broken server must not blank every agent's toolbox; the failure is explicit, not silent. |
| M4 | Policy block → JSON-RPC error `-32001` (`message`: detail, `data`: `{reason_code, triggered_rules}`); upstream not contacted. Unknown tool → `-32602`. Upstream failure → `-32002`. | Protocol errors per MCP; codes in the implementation-defined range. |
| M5 | Every `tools/call` writes a `request_logs` row: `model` = namespaced tool, `provider` = `mcp:<server>`, zero tokens/cost, `status_code` 200 / 446 / 502, `request_metadata.type = "mcp_tool_call"` with policy metadata. | Tool calls appear in the existing log viewer, analytics and audit exports. |
| M6 | Upstream URLs must be HTTPS and pass the SSRF check at registration **and** at call time. Auth headers are Fernet-encrypted. | Same bar as webhooks and provider keys; re-checking at call time closes DNS changes after registration. |

## Testing

Upstream MCP servers are simulated with `httpx.MockTransport` (JSON and SSE responses, session header,
JSON-RPC errors). Route tests use the existing FastAPI TestClient pattern with dependency overrides.
The new table is added to the RLS integration test's table list (runs in CI).
