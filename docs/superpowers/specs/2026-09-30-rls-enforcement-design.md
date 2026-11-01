# RLS Enforcement — Design

- **Date:** 2026-09-30
- **Status:** Approved under standing authorization (owner delegated decisions)
- **Scope:** `backend/` database access, one migration, CI integration job, docs.

## Problem

Row-level security exists in the schema but does not protect anything in practice:

1. **The app connects as a role that bypasses RLS.** In docker-compose the app user is the Postgres image's `POSTGRES_USER`, a superuser. Superusers bypass RLS even with `FORCE ROW LEVEL SECURITY`. The app never switches to the `app_user` role the migrations create.
2. **`app_user` could not run the app anyway.** It only has grants on the eight RLS tables, not on `organizations`, `users`, `teams`, etc.
3. **Several writers never set the org.** `audit_logger` (request_logs insert, webhook + anomaly dispatch), `cache_service` L3 insert, `cost_tracker` budget alert, `spend_batch_service` flush. Under real enforcement their inserts fail the `WITH CHECK` clause.
4. **Some jobs read across orgs before setting one.** `key_rotation_scheduler` and `provider_health_service` list provider keys for all orgs; `adaptive_sampling_service` aggregates `request_logs` for all orgs.
5. **The audit log is no longer append-only.** Migration `f8a9b0c1d2e3` replaced the insert/select-only policies on `request_logs` with a `FOR ALL` policy, so the app role may UPDATE and DELETE its own org's logs.
6. **The RLS integration tests never run.** They are marked `integration` and CI runs `-m "not integration"`; CI's Postgres image also lacks pgvector, so migrations could not run there.

## Decisions

| # | Decision | Why | Rejected alternative |
|---|---|---|---|
| D1 | Request-path engine runs `SET ROLE <DB_APP_ROLE>` on every new pooled connection (SQLAlchemy `connect` event). Default `DB_APP_ROLE=app_user`. | One place, every session inherits it; works whether the login role is a superuser (compose) or an owner (Cloud SQL). | A separate login role in every deployment: needs secrets/infra changes in compose, Helm and Cloud Run at once. |
| D2 | A second engine, `system_engine` / `SystemSessionLocal`, keeps the login role and is used **only** by jobs that must read across orgs. Every use is greppable. | Cross-org maintenance is legitimate (health checks, sampling); hiding it behind SECURITY DEFINER functions per query would multiply SQL. | Giving `app_user` `BYPASSRLS`: defeats the purpose. |
| D3 | Writers set the org before inserting (`set_session_org_id`), including a per-org loop in the batch flush. | Keeps inserts under `WITH CHECK`; a bug writing to the wrong org fails loudly. | Moving writers to the system engine: would silently allow cross-org writes. |
| D4 | New migration grants `app_user` DML on all tables and sequences (plus default privileges for future ones) and `SELECT` on `mv_daily_spend`; then on `request_logs` revokes `UPDATE, DELETE` and grants `UPDATE (archived_at)` only. | Makes the role usable; restores append-only logs with a column-level grant so archiving still works. | Separate UPDATE-only policy: policies cannot restrict columns. |
| D5 | `DB_APP_ROLE` is validated as a plain SQL identifier at startup; an empty value is rejected. | The value is interpolated into `SET ROLE`; fail hard instead of running without isolation. | Allow empty to disable: silent fallback to no isolation. |
| D6 | CI uses `pgvector/pgvector:pg16`, runs `alembic upgrade head`, then runs the RLS integration tests in a separate step. | Proves the real migrations + policies + role switch together. | Mocked RLS tests: cannot prove Postgres semantics. |
| D7 | Local verification without Docker: unit tests for the Python wiring, plus a scratch Postgres 15 cluster (installed binaries, trust auth, temp dir) proving the Postgres semantics the design relies on (superuser + `SET ROLE` is subject to RLS; column-level UPDATE grant). | Docker is not installed; the full migration chain needs pgvector, which the local PG15 lacks. | Installing Docker/pgvector on the owner's machine without asking. |

## Out of scope

- Changing the login user in compose/Helm/Cloud Run (D1 makes it unnecessary).
- Row-level policies for tables that are not org-scoped today.

## Verification

- Unit: engine listener issues `SET ROLE app_user`; system engine does not; setting validation; each fixed writer calls `set_session_org_id` with the right org before adding rows; cross-org jobs use `SystemSessionLocal`.
- Scratch PG15: `SET ROLE` semantics and column-level grant behave as assumed.
- CI (runs on push): full migrations on pgvector Postgres + `tests/test_rls_isolation.py`, extended with: app session cannot read another org's rows; app session cannot UPDATE log content or DELETE logs; app session can set `archived_at`; system session reads across orgs.
