---
title: Audit Logging
description: Every request, response, and policy decision is logged and replay-able — and never edited after the fact.
---

# Audit Logging

Every request that passes through OpenProxyAI is logged — the request, the response, every policy decision made, the routing decision, and the final cost.

## Immutability

Audit log entries are write-once. Nothing in the request pipeline updates or deletes a log entry after it's written — a request's history in the audit log is exactly what happened, not a mutable status field that can drift from reality.

## Asynchronous, never blocking

Logging happens after the response has already been returned to your application (see [Request Pipeline](/core-concepts/request-pipeline), stage 6). A slow or unavailable logging backend never adds latency to a live request.

## Retention

Retention length is plan-dependent and configurable per organization — the [FedRAMP-aligned compliance template](/security/fedramp-template), for example, defaults to 7-year retention. Old logs are archived on an hourly background schedule according to your org's configured retention window.

## Querying the audit log

```
GET /api/v1/analytics/logs
GET /api/v1/analytics/logs/{log_id}
GET /api/v1/admin/audit-log
```

## Exporting for a compliance review

```
GET /api/v1/analytics/compliance/export
```

Produces an export suitable for handing to an internal or external auditor, scoped to a date range and (optionally) a specific team or policy.
