---
title: Analytics
description: Usage overview, request logs, cache and policy analytics, and compliance export.
---

# Analytics

```
GET /api/v1/analytics/overview
GET /api/v1/analytics/logs
GET /api/v1/analytics/logs/{log_id}
GET /api/v1/analytics/cache
GET /api/v1/analytics/policy
GET /api/v1/analytics/policy/export
GET /api/v1/analytics/compliance/export
```

## Overview

`overview` returns aggregate spend, request volume, and cache hit rate for the organization, typically scoped to a period.

## Logs

`logs` and `logs/{log_id}` query the underlying [audit log](/security/audit-logging) — every request, its policy decisions, routing outcome, and cost.

## Cache

`cache` breaks down hit rate by tier (L1/L2/L3) — see [Caching](/core-concepts/caching).

## Policy

`policy` and `policy/export` report policy hit counts and are the basis for the per-policy activity shown in the admin console — see [Policies & Guardrails](/core-concepts/policies-and-guardrails).

## Compliance export

`compliance/export` produces an export scoped to a date range (and optionally a team or policy) suitable for handing to an auditor — see [Audit Logging](/security/audit-logging).

## Reconciliation

```
POST /api/v1/analytics/reconcile
```

Reconciles logged spend against provider-reported usage — useful after a period where a sidecar (like the analytics dual-write) was degraded, to confirm nothing was under- or over-counted.
