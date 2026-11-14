---
title: Analytics
description: Usage overview, request logs, cache and policy analytics, exports, provider reconciliation, and a structured query endpoint for your own logs and scores.
---

# Analytics

The analytics API answers "what did we spend, who used it, what was blocked and why" for your organization. Use the ready-made endpoints for dashboards and exports, and the structured query endpoint when you need a custom cut, such as cost per model this week or the average thumbs score by model. All endpoints are under `/api/v1/analytics`, use a session token (see the [overview](/api-reference/overview)), and only ever return your own organization's data.

| Endpoint | Who | Purpose |
|---|---|---|
| `GET /overview` | Any user | Spend, volume, latency and breakdowns |
| `GET /logs`, `GET /logs/{log_id}` | Any user | Request log, list and detail |
| `GET /cache` | Any user | Cache hits, misses and estimated savings |
| `GET /policy` | Any user | Policy event counts |
| `GET /policy/export` | Admin | Policy events as JSON or CSV |
| `GET /compliance/export` | Admin | Audit-oriented CSV |
| `POST /reconcile` | Any user | Compare gateway usage with a provider export |
| `GET /query/catalog`, `POST /query` | Admin | Structured, read-only queries |

## Overview

```
GET /api/v1/analytics/overview
```

| Query parameter | Default | Notes |
|---|---|---|
| `period_days` | 30 | 1 to 90. |
| `team_id` | none | Limit to one team. Admins can use any team; other users must be a member (403 otherwise, 404 for an unknown team). |
| `session_id` | none | Limit to one session (up to 64 characters). |

```bash
curl "https://api.openproxy.ai/api/v1/analytics/overview?period_days=7" \
  -H "Authorization: Bearer $OPENPROXY_SESSION_TOKEN"
```

The response has `overview`, `by_model`, `by_user`, `by_key`, `by_team`, `daily_trend` and `generated_at`.

| Section | Contents |
|---|---|
| `overview` | `total_requests`, `successful_requests`, `failed_requests`, `policy_blocked_requests`, `policy_flagged_requests`, `total_tokens`, `total_cost_usd`, `avg_latency_ms`, `avg_ttft_ms`, `p50_latency_ms`, `p95_latency_ms`, `p99_latency_ms`, `projected_month_end_cost_usd`, `forecast_basis_days` |
| `by_model` | `model`, `provider`, `requests`, `tokens`, `cost_usd` |
| `by_user` | `user_id`, `email`, `requests`, `tokens`, `cost_usd` |
| `by_key` | `api_key_id`, `name`, `key_prefix`, `requests`, `tokens`, `cost_usd` |
| `by_team` | `team_id`, `name`, `requests`, `tokens`, `cost_usd` |
| `daily_trend` | `date`, `requests`, `tokens`, `cost_usd`, `avg_latency_ms` |

## Request logs

```
GET /api/v1/analytics/logs
GET /api/v1/analytics/logs/{log_id}
```

These read the [audit log](/security/audit-logging): every request with its policy decision, routing outcome and cost.

| Query parameter | Notes |
|---|---|
| `page`, `page_size` | Page from 1; size 1 to 200, default 50. |
| `model` | Exact model. |
| `status` | `success` (status below 400) or `error`. |
| `policy_action` | `allow`, `log_only` or `block`. |
| `policy_reason` | Reason code, 1 to 120 characters. |
| `label_key`, `label_value` | Filter on a request label (up to 64 characters each). |
| `team_id`, `session_id` | As for the overview. |
| `start_date`, `end_date` | Dates, `YYYY-MM-DD`. |
| `include_archived` | Default `false`; archived entries are hidden otherwise. |

The reply is `{"items": [...], "total", "page", "page_size", "total_pages"}`. Each item has `id`, `created_at`, `model`, `provider`, `status`, `prompt_tokens`, `completion_tokens`, `total_tokens`, `cost_usd`, `latency_ms`, `ttft_ms`, `error_message`, `policy_action`, `policy_reason` and `policy_triggered_rules`. The detail call adds `request_id`, `user_id`, `api_key_id`, `status_code` and `request_metadata`; an unknown id is 404. The log entries kept follow your plan's retention (7, 30, 90 or 365 days).

## Cache and policy

```
GET /api/v1/analytics/cache?period_days=7
GET /api/v1/analytics/policy?period_days=30
```

The cache response is `period_days`, `exact_hits`, `semantic_hits`, `misses`, `hit_rate` and `estimated_savings_usd`; `period_days` is 1 to 90, default 7. See [Caching](/core-concepts/caching).

The policy response is `period_days`, `total_policy_events`, `by_action` (`action`, `count`), `by_reason` (`reason_code`, `action`, `count`) and `generated_at`; `period_days` is 1 to 90, default 30. These feed the policy activity in the console; see [Policies and guardrails](/core-concepts/policies-and-guardrails).

## Exports

Both exports are admin only (403 otherwise).

### Policy events

```
GET /api/v1/analytics/policy/export?format=csv&period_days=30&action=block
```

| Parameter | Notes |
|---|---|
| `format` | `json` (default) or `csv`. |
| `period_days` | 1 to 365, default 30. |
| `start_date`, `end_date` | Override the period. A start after the end is 422. |
| `action` | `allow`, `log_only` or `block`. |
| `reason_code` | Partial, case-insensitive match. |

Fields: `id`, `request_id`, `created_at`, `model`, `provider`, `status_code`, `policy_action`, `policy_reason`, `policy_triggered_rules`. JSON returns `{"items": [...], "total": n}`; CSV joins the rules with `;` and neutralizes cells that start with a spreadsheet formula character. At most 10,000 events are returned; when more exist the response carries `X-Result-Truncated: true`, so narrow the window.

### Compliance report

```
GET /api/v1/analytics/compliance/export?period_days=90
```

A CSV (`period_days` 1 to 365, default 30) for handing to an auditor. Columns: `record_type`, `timestamp`, `subject`, `action`, `detail`, `model`, `provider`, `status`, `budget_monthly_usd`, `actual_cost_period_usd`. Record types are `policy_violation`, `user_access`, `provider_key_rotation` and `budget_vs_actual`. It is a data export, not a certification; see [Audit logging](/security/audit-logging).

## Reconciliation

```
POST /api/v1/analytics/reconcile
```

Compares gateway usage with a provider's own usage export, to confirm nothing was under- or over-counted (for example after an outage of a reporting component). Send one record per day and model.

```json
{
  "provider": "openai",
  "records": [
    {"date": "2026-11-01", "model": "gpt-4o", "requests": 120, "input_tokens": 54000, "output_tokens": 18000, "cost_usd": 14.2}
  ]
}
```

`records` must not be empty (422). The report covers the earliest to the latest date you sent, and every delta is **gateway minus provider**, so a positive number means the gateway counted more. It returns `provider`, `period_start`, `period_end`, `total_rows`, `mismatch_rows`, `rows` and `summary`. Each row has `date`, `model` and, for requests, input tokens, output tokens and cost, the gateway value, the provider value, the `delta_` and the `pct_delta_` (null when the provider value is 0). A row counts as a mismatch when requests or tokens differ; cost differences are shown but not counted. `summary` holds the totals.

## Structured query

```
GET  /api/v1/analytics/query/catalog
POST /api/v1/analytics/query
```

Admins only. A read-only way to answer your own questions without exporting the database. It is deliberately **not** a SQL console: you send a structured query, and every choice in it (view, column, operator, aggregate) is looked up in a fixed list. Nothing you send is treated as SQL text, so there is no injection surface and no way to reach another organization's rows or an unlisted table.

### A query

```bash
curl -X POST https://api.openproxy.ai/api/v1/analytics/query \
  -H "Authorization: Bearer $OPENPROXY_SESSION_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "view": "requests",
    "select": ["model", {"agg": "count", "as": "calls"}, {"agg": "sum", "column": "cost_usd", "as": "spend"}, {"agg": "p95", "column": "latency_ms"}],
    "where": [{"column": "status_code", "op": "=", "value": 200}],
    "group_by": ["model"],
    "order_by": [{"column": "spend", "dir": "desc"}],
    "limit": 20,
    "since": "2026-11-01T00:00:00Z"
  }'
```

```json
{"columns": ["model", "calls", "spend", "p95_latency_ms"], "rows": [["openai/gpt-4o", 120, 14.2, 910.0]], "row_count": 1, "truncated": false}
```

| Field | Rules |
|---|---|
| `view` | `requests` (your request log) or `scores` (feedback and evaluation scores). |
| `select` | Column names and aggregates, 1 to 12. Aggregates: `count`, `sum`, `avg`, `min`, `max`, `p50`, `p95`. `count` may omit the column; the others need one. `sum`, `avg` and the percentiles need a number; `min` and `max` a number or a time. `as` names the result (lowercase letters, digits and `_`, up to 41 characters); without it the name is `<agg>_<column>`. |
| `where` | Up to 12 conditions with `=`, `!=`, `>`, `>=`, `<`, `<=` and `in` (a list of 1 to 50). Ordered comparisons need a number or a time. |
| `group_by` | With an aggregate, it must list exactly the plain columns you selected. Without an aggregate it is not allowed. |
| `order_by` | Up to 4, only a column you selected or an aggregate's `as` name; `dir` is `asc` (default) or `desc`. |
| `limit` | 1 to 1,000, default 100. `truncated` is true when the limit was reached. |
| `since`, `until` | The window. Default is the last 30 days; at most 365 days, and `since` must be before `until`. |

### Views and columns

`GET /query/catalog` returns the views with each column's type, plus the aggregates and operators, so a client can build a form from it.

| View | Columns |
|---|---|
| `requests` | `created_at`, `day`, `model`, `provider`, `status_code`, `prompt_tokens`, `completion_tokens`, `total_tokens`, `cost_usd`, `latency_ms`, `ttft_ms`, `user_id`, `api_key_id`, `data_class`, `source` |
| `scores` | `created_at`, `day`, `score_name`, `value`, `source`, `experiment_id`, `variant_id` |

### Limits and safety

- No joins, subqueries, functions beyond the listed aggregates, or anything that writes.
- Free text users typed is not queryable: error messages, request metadata and score comments are not columns. For scores with their comments use [`GET /api/v1/scores`](/api-reference/feedback).
- Every query is limited to your organization twice over: by an explicit filter and again by row-level security (see [Row-level security](/security/row-level-security)).
- Each query runs in a **read-only transaction with a 5-second statement timeout**.
- Each run is written to the admin audit log as `analytics.queried`, with the query you sent and never the rows it returned.

## Errors and troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| 403 | The endpoint needs the admin role, or you are not a member of the requested team. | Use an admin session, or a team you belong to. |
| 404 | Unknown `team_id` or log id. | Check the id. |
| 422 `invalid_query` | The query is outside the allowed list; the `detail` says what (unknown column, `group_by` mismatch, an `order_by` that is not selected, a window over 365 days). | Follow the message and resend. A rejected query is not run. |
| 408 `query_timeout` | The query took over 5 seconds. | Narrow the window or add `where` filters. |
| 422 on reconcile or policy export | Empty `records`, or `start_date` after `end_date`. | Fix the input. |
| Export is cut short | More than 10,000 policy events; `X-Result-Truncated: true` is set. | Narrow the date range or filter by `action`. |

## Next steps

- [Audit logging](/security/audit-logging) for what each log entry contains
- [Rate limiting and budgets](/core-concepts/rate-limiting-and-budgets) to act on what the numbers show
- [Feedback](/api-reference/feedback) for the scores you can query
- [Errors and status codes](/api-reference/errors-and-status-codes)
