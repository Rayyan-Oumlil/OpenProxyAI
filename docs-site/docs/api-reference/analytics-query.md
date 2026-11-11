---
title: Analytics query
description: POST /api/v1/analytics/query. Ask your own request logs and scores questions without exporting the database.
---

# Analytics query

```
GET  /api/v1/analytics/query/catalog
POST /api/v1/analytics/query
```

Admins only, with a user token. A read-only way to answer "what did each model cost this week", "which status codes did we see", "what is the average thumbs score by model". It is **not** a SQL console, deliberately: you send a structured query, and every choice in it (the view, columns, operators, aggregates) is looked up in a fixed list. Nothing you send is ever treated as SQL text, so there is no injection surface and no way to reach another organization's rows or a table that is not listed.

## A query

```json
{
  "view": "requests",
  "select": ["model", {"agg": "count", "as": "calls"}, {"agg": "sum", "column": "cost_usd", "as": "spend"}, {"agg": "p95", "column": "latency_ms"}],
  "where": [{"column": "status_code", "op": "=", "value": 200}],
  "group_by": ["model"],
  "order_by": [{"column": "spend", "dir": "desc"}],
  "limit": 20,
  "since": "2026-11-01T00:00:00Z"
}
```

```json
{"columns": ["model", "calls", "spend", "p95_latency_ms"], "rows": [["openai/gpt-4o", 120, 14.2, 910.0]], "row_count": 1, "truncated": false}
```

| Field | |
|---|---|
| `view` | `requests` (your request log) or `scores` (feedback and evaluation scores). |
| `select` | Column names and aggregates: `count`, `sum`, `avg`, `min`, `max`, `p50`, `p95`. `sum`, `avg` and the percentiles need a number; `min` and `max` a number or a time. Up to 12. |
| `where` | Up to 12 conditions: `=`, `!=`, `>`, `>=`, `<`, `<=` and `in` (a list of up to 50). Ordered comparisons need a number or a time. |
| `group_by` | With an aggregate, it must list exactly the plain columns you selected. |
| `order_by` | Only a column you selected, or an aggregate's `as` name. |
| `limit` | 1 to 1,000. `truncated` is true when the limit was reached. |
| `since`, `until` | The window. Default the last 30 days; at most 365 days. |

`GET /query/catalog` lists the views and their columns with their types, so a client can build the form from it.

## What it cannot do

- Joins, subqueries, functions beyond the aggregates above, and anything that writes.
- Read free text users typed. `error_message`, the request metadata and score comments are not columns here. `data_class` and `source` from the metadata are, as plain columns.
- Read another organization's data. Every query is limited to your organization by an explicit filter and again by row-level security.

## Safety

Each query runs in a **read-only transaction with a 5-second statement timeout** (a slow one is a 408 `query_timeout`: narrow the window or add filters). Each one is written to the [admin audit log](/api-reference/organizations) as `analytics.queried` with the query you sent, never the rows it returned. A query the compiler rejects is a 422 `invalid_query` that says what to change, and is not audited as run.

For individual scores with their comments, use [`GET /api/v1/scores`](/api-reference/feedback).
