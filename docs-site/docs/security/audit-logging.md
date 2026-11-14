---
title: Audit Logging
description: What OpenProxyAI records for every request and every administrative change, how to query and export it, and how long it is kept.
---

# Audit Logging

OpenProxyAI keeps two append-only records: a **request log** with one row per request that reaches the gateway, and an **admin audit log** of administrative changes. By default the request log holds metadata only (model, tokens, cost, status, policy decision, routing). Prompts and answers are not stored unless an admin turns on [payload capture](/guides/payload-capture). This page shows what is recorded, how to find a request, how to export for an audit, and how retention works.

## The two logs

| | Request log | Admin audit log |
|---|---|---|
| Records | Every request: allowed, blocked or failed | Administrative changes made by people or by SCIM provisioning |
| One row per | Request | Change |
| Who can read it | Any signed-in user of the organization | Admins only (others get 403) |
| Retention | By plan, see below | Not archived by the retention job |
| Endpoint | `GET /api/v1/analytics/logs` | `GET /api/v1/admin/audit-log` |

The request row is written after the response has gone back to your application (see [Request Pipeline](/core-concepts/request-pipeline)), so logging never adds latency to a live call. A row can appear a moment after the response.

## What a request row contains

| Field | Meaning |
|---|---|
| `id` | The log entry id, used by the detail endpoint |
| `created_at` | When the request was logged |
| `model`, `provider` | What was called, after routing |
| `status` | `success` (status code below 400) or `error` |
| `prompt_tokens`, `completion_tokens`, `total_tokens` | Token counts |
| `cost_usd` | Computed cost |
| `latency_ms`, `ttft_ms` | Total latency and time to first token (streaming) |
| `error_message` | Why it failed, if it did |
| `policy_action` | `allow`, `log_only` or `block` |
| `policy_reason`, `policy_triggered_rules` | Reason code and the rules that fired |

The detail view adds `request_id`, `user_id`, `api_key_id`, `status_code` and `request_metadata`. Depending on what applied to the request, the metadata holds the policy decision, the data class, the routing decision, behavior settings, cache result, stage timings, labels, team id, session id and experiment info. It does not hold prompt or answer text. A request blocked by the policy has status code 446.

## What the admin audit log records

Each entry has `actor_email`, `action`, `resource_type`, `resource_id`, `before` and `after` snapshots, `ip_address` and `created_at`. Secrets are never put in snapshots: provider keys, webhook secrets and tokens are left out.

| Area | Actions |
|---|---|
| Organization | `organization.updated`, `policy.updated`, `apply_compliance_template`, `webhook.updated`, `billing.plan_changed` |
| Users and teams | `user.updated`, `user.role_changed`, `user.deactivated`, `team.created`, `team.updated`, `team.deleted`, `team.member_added`, `team.member_removed`, `invite.sent`, `invite.revoked` |
| SSO and SCIM | `user.scim_created`, `user.scim_deactivated`, `user.scim_reactivated` (the actor is the provisioning token, not a person), `scim.token_rotated`, `scim.token_revoked` |
| Provider keys | `provider_key.created`, `provider_key.updated`, `provider_key.deleted`, `provider_key.rotated` |
| Models | `model_registry.created`, `model_registry.updated`, `model_registry.deleted` |
| MCP | `mcp_server.*`, `mcp_tool.*`, `mcp_grant.created` and `.deleted`, `mcp_bundle.*` (including `key_attached` and `key_detached`), `mcp_trust_rule.created` and `.deleted` |
| Policy plugins | `policy_plugin.uploaded`, `.enabled`, `.disabled`, `.deleted` |
| Evaluation | `dataset.created`, `.deleted`, `.imported`, `evaluator.created`, `.deleted`, `eval_run.created`, `.cancelled` |
| Experiments | `experiment.created`, `.updated`, `.deleted`, `.started`, `.stopped`, `.winner_found` |
| Other | `conversation.deleted`, `batch_job.cancelled`, `prompt_template.promoted_with_override`, `analytics.queried` |

The entry is written in the same transaction as the change, so a change cannot succeed without its record.

### Read the admin audit log

```bash
curl "https://your-gateway/api/v1/admin/audit-log?action=policy.updated&page_size=20" \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

```json
{
  "items": [
    {
      "id": "6f1c2d1e-5a0b-4f57-9b0e-1d2f3a4b5c6d",
      "actor_email": "admin@example.com",
      "action": "policy.updated",
      "resource_type": "policy",
      "resource_id": null,
      "before": {"...": "previous values"},
      "after": {"...": "new values"},
      "ip_address": "203.0.113.7",
      "created_at": "2026-11-13T14:02:11+00:00"
    }
  ],
  "total": 1, "page": 1, "page_size": 20, "total_pages": 1
}
```

Filters: `action`, `resource_type`, `page` and `page_size` (1 to 200, default 50). Newest first. The `before` and `after` contents vary by action. `ip_address` uses the forwarded client address only when the operator has set `TRUSTED_PROXY=true`.

## Find a request

Every response carries `X-OpenProxyAI-Request-Id`. Store it next to the answer you showed. The same id is what you send with [feedback](/api-reference/feedback) and what appears as `request_id` on the log entry.

The request id is not the log entry `id`. The list endpoint has no request-id filter and does not return `request_id`, so to go from a header value to a row:

1. Narrow the list with `start_date`, `end_date`, `model`, `status`, `team_id` or `label_key` and `label_value`.
2. Open each candidate with the detail endpoint and compare `request_id`.
3. For a blocked or flagged request, the policy export (below) returns `request_id` next to each event, which is the faster route.

In the admin console, the log detail panel shows both the log id and the request id with copy buttons.

### List and filter

```bash
curl "https://your-gateway/api/v1/analytics/logs?status=error&model=gpt-4o&start_date=2026-11-01&end_date=2026-11-13&page_size=25" \
  -H "Authorization: Bearer $TOKEN"
```

```json
{
  "items": [
    {
      "id": "0b9a7a52-2c1f-4d0e-8e0a-6c1d8f2b9e11",
      "created_at": "2026-11-13T13:40:02.114000Z",
      "model": "gpt-4o",
      "provider": "openai",
      "status": "error",
      "prompt_tokens": 412,
      "completion_tokens": 0,
      "total_tokens": 412,
      "cost_usd": 0.0,
      "latency_ms": 38,
      "ttft_ms": null,
      "error_message": "rate_limited:<limit type>",
      "policy_action": "allow",
      "policy_reason": null,
      "policy_triggered_rules": null
    }
  ],
  "total": 1, "page": 1, "page_size": 25, "total_pages": 1
}
```

| Parameter | Behavior |
|---|---|
| `page`, `page_size` | Page from 1; size 1 to 200, default 50. Newest first |
| `model` | Exact match |
| `status` | `success` or `error` |
| `policy_action` | `allow`, `log_only` or `block` |
| `policy_reason` | Case-insensitive substring of the reason code |
| `label_key` with `label_value` | Match a label sent in `x-openproxy-labels` (both required) |
| `team_id` | Requests attributed to a team; non-admins must be a member of it |
| `session_id` | Requests sent with `x-openproxy-session-id` |
| `start_date`, `end_date` | Inclusive calendar dates |
| `include_archived` | `true` also returns rows past the retention window |

### Get one entry

```bash
curl https://your-gateway/api/v1/analytics/logs/0b9a7a52-2c1f-4d0e-8e0a-6c1d8f2b9e11 \
  -H "Authorization: Bearer $TOKEN"
```

The response is the list item plus `request_id`, `user_id`, `api_key_id`, `status_code` and `request_metadata`. An unknown id, or an id from another organization, returns 404.

## Export for a compliance review

Both exports are admin-only (403 otherwise).

### Compliance export

```bash
curl -o compliance-report.csv \
  "https://your-gateway/api/v1/analytics/compliance/export?period_days=90" \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

`period_days` is 1 to 365 (default 30). The CSV has the columns `record_type, timestamp, subject, action, detail, model, provider, status, budget_monthly_usd, actual_cost_period_usd`, with these record types:

| `record_type` | Content |
|---|---|
| `policy_violation` | Requests the policy blocked or flagged in log-only mode, with reason code (up to 10,000 rows) |
| `user_access` | Users created or signed in during the period, with role and active state |
| `provider_key_rotation` | Provider key rotations from the admin audit log |
| `budget_vs_actual` | Monthly budget against actual spend for the period |

Cells that start with a spreadsheet formula character are prefixed with an apostrophe, so the file is safe to open in Excel.

### Policy export

```bash
curl -o policy-events.csv \
  "https://your-gateway/api/v1/analytics/policy/export?format=csv&action=block&start_date=2026-11-01&end_date=2026-11-13" \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

Parameters: `format` (`json` or `csv`), `period_days` (1 to 365, default 30), `start_date`, `end_date`, `action`, `reason_code`. Each event has `id`, `request_id`, `created_at`, `model`, `provider`, `status_code`, `policy_action`, `policy_reason` and `policy_triggered_rules`. Output is capped at 10,000 events; when more matched, the response carries `X-Result-Truncated: true`, so narrow the dates and export again.

## Retention and archiving

Retention comes from the organization's plan:

| Plan | Request log retention |
|---|---|
| Community | 7 days |
| Team | 30 days |
| Business and metered | 90 days |
| Enterprise | 365 days |

An hourly background job marks rows older than the window as archived. Archiving hides them from the default list, the exports and the analytics views; it does not erase them. Pass `include_archived=true` to the list endpoint to see them. The [compliance templates](/security/compliance-templates) record a longer retention target in the policy but do not change this window. If your framework needs longer history than your plan keeps, export on a schedule or stream to a SIEM.

## Append-only behavior

The gateway connects to the database with a role that cannot delete rows from either log, and cannot update admin audit entries at all. On the request log, the only column that role can change is the archive marker. Nothing in the request path rewrites a row after it is written, so an entry shows what happened rather than a status that can drift. This is a database privilege, so it also holds against a bug in the application. An operator with the database owner credentials can still modify data, which is why you should also ship logs to a system you control.

## Stream to a SIEM

To get events into Splunk, Sentinel or a similar tool as they happen, use telemetry and SIEM export, which sends identifiers and reason codes (not prompt text). See [Telemetry and SIEM](/guides/telemetry-and-siem).

## Tenant isolation

Every query on both logs is scoped to the caller's organization, and the request log is additionally protected by row-level security in the database, so one organization cannot read another's rows even through a faulty query. Details in [Row-level security](/security/row-level-security).

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `GET /admin/audit-log` returns 403 | Caller is not an admin | Use an admin token |
| Exports return 403 | Same | Use an admin token |
| An old request is missing from the list | It is past the plan's retention window and archived | Add `include_archived=true` |
| Cannot find a row from a request id | No request-id filter on the list | Narrow by date and model, check `request_id` in the detail, or use the policy export |
| Detail returns 404 | You passed the request id, or the entry belongs to another organization | Use the log entry `id` from the list |
| No prompt or answer in a row | Only metadata is kept by default | Enable [payload capture](/guides/payload-capture), which stores a redacted sample |
| A request just made is not listed | The row is written after the response | Retry after a moment |
| Policy export shows `X-Result-Truncated: true` | More than 10,000 events matched | Narrow the date range |
| `team_id` filter returns 403 or 404 | Team not in your organization, or you are not a member | Use an admin token or a member account |

## Next steps

- [Payload capture](/guides/payload-capture) to keep redacted prompts and answers
- [Telemetry and SIEM](/guides/telemetry-and-siem) to stream events out
- [Policies and guardrails](/core-concepts/policies-and-guardrails) for what produces a policy decision
- [Row-level security](/security/row-level-security) for tenant isolation
