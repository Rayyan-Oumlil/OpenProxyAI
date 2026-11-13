---
title: MCP admin API
description: Register MCP servers, review pinned tools, manage grants, bundles and trust rules. Admin JWT required for every write.
---

# MCP admin API

These endpoints manage the [MCP gateway](/guides/mcp-gateway). Authenticate with an admin session token (`Authorization: Bearer <JWT>`). Anyone in the organization can read; **only admins can create, change or delete**. Every write is recorded in the [admin audit log](/security/audit-logging).

Names and slugs use lowercase letters, digits and single hyphens, at most 40 characters. Tool patterns are globs over `<server>__<tool>` using letters, digits and `_ * ? . -`, up to 200 characters.

## Servers

```
GET    /api/v1/mcp-servers
POST   /api/v1/mcp-servers
PATCH  /api/v1/mcp-servers/{server_id}
DELETE /api/v1/mcp-servers/{server_id}
```

Create body:

| Field | Type | Notes |
|---|---|---|
| `name` | string | Required. Becomes the prefix of every tool name. |
| `url` | string | Required. Streamable HTTP endpoint, HTTPS, public address. |
| `auth_header` | string | Optional. Sent to this server only. Stored encrypted, never returned. |
| `pin_mode` | `off` / `warn` / `enforce` | Default `warn`. |
| `scan_mode` | `off` / `log` / `redact` / `block` | Default `log`. |

`PATCH` takes any of `is_active`, `pin_mode`, `scan_mode`; at least one is required. The response never contains the credential, only `has_auth: true | false`. A duplicate name is 409.

### Pinned tools

```
GET  /api/v1/mcp-servers/{server_id}/tools
POST /api/v1/mcp-servers/{server_id}/sync
POST /api/v1/mcp-servers/{server_id}/tools/{tool_id}/approve
POST /api/v1/mcp-servers/{server_id}/tools/{tool_id}/block
```

Each tool has a `status` of `pending`, `approved`, `drifted` or `blocked`, its current `definition`, the `approved_snapshot`, and both hashes (`current_hash`, `approved_hash`), so you can see exactly what changed. `sync` fetches the server's tool list now instead of waiting for the next scheduled run (409 if pinning is off for the server, 502 if the server cannot be reached). `approve` accepts the current definition; `block` refuses the tool in `warn` and `enforce` mode alike.

## Grants

```
GET    /api/v1/mcp-grants
POST   /api/v1/mcp-grants
DELETE /api/v1/mcp-grants/{grant_id}
```

```json
{"subject_type": "role", "subject_id": "developer", "tool_pattern": "github__*", "effect": "allow"}
```

`subject_type` is `role`, `team`, `user` or `api_key`. For `role`, `subject_id` is `admin`, `developer` or `viewer`; for the others it is a UUID. A matching `deny` always wins. If any `allow` grant applies to the caller, the tool must match one. A duplicate grant is 409.

## Bundles

```
GET    /api/v1/mcp-bundles
POST   /api/v1/mcp-bundles
PATCH  /api/v1/mcp-bundles/{bundle_id}
DELETE /api/v1/mcp-bundles/{bundle_id}
PUT    /api/v1/mcp-bundles/{bundle_id}/keys/{api_key_id}
DELETE /api/v1/mcp-bundles/{bundle_id}/keys/{api_key_id}
```

Create body: `slug` and `name` (required), `description`, and `tools`, a list of up to 200 patterns. `PATCH` changes `name`, `description`, `is_active` or `tools`. The response lists `api_key_ids`. Attaching a key confines it to `POST /v1/mcp/{slug}`.

## Trust rules

```
GET    /api/v1/mcp-trust-rules
POST   /api/v1/mcp-trust-rules
DELETE /api/v1/mcp-trust-rules/{rule_id}
```

```json
{"tool_pattern": "web__fetch", "rule": "trusted_output"}
```

`rule` is `trusted_output` (results do not taint the session) or `sink` (refuses to run in a tainted or session-less context). See [step 7 of the MCP guide](/guides/mcp-gateway).
