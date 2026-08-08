---
title: Row-Level Security
description: How org data isolation is enforced at the database layer, not just in application code.
---

# Row-Level Security

Every organization's data is isolated using PostgreSQL row-level security (RLS) policies, enforced at the database layer — not only in application-level query filters.

## Why this matters

Application-level isolation (a `WHERE org_id = ?` clause added by convention in every query) is only as strong as every engineer remembering to add it correctly, every time, in every query, forever. Database-level RLS makes the org boundary a property of the database itself: a query that forgets to scope by organization doesn't leak another org's rows — RLS returns none, because the database enforces the boundary independently of what the application code asked for.

## How it's applied

Every database session that touches an RLS-protected table sets the current organization context once, at the start of the session, before any query runs against that table. From that point, every query in that session is automatically scoped — there is no per-query opt-in.

## Background jobs

Background tasks (log archival, webhook retries, scheduled analytics refreshes) run outside the request-response cycle and open their own database sessions rather than reusing one tied to a specific request — each sets its own scoped context appropriately for the org(s) it's operating on.

## What this guarantees

A bug in one part of the application that forgets to filter by organization fails safe — it returns no rows for the wrong org, rather than silently returning another organization's data.
