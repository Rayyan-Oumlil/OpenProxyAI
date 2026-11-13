---
slug: postgres-rls-with-connection-pools
title: "Row-level security and connection pools: the mistakes that leak across tenants"
tags: [security, engineering]
description: "Four ways Postgres row-level security fails once a connection pool is involved, and how OpenProxyAI avoids each: transaction-local org settings, a non-bypass role, a separate system session, and tests on a real database."
---

Row-level security (RLS) is easy to demo and easy to get wrong in production. The demo uses one connection and one tenant. Production uses a pool, where one database connection serves tenant A now and tenant B a moment later. Most RLS leaks come from that gap: a setting that outlived its request, a role that skips the policy, or a background job that nobody scoped. This post covers what OpenProxyAI does about each, from the code. It builds on the earlier post [Row-level security: making data leaks impossible by construction](/blog/row-level-security-by-construction), which explains why the boundary belongs in the database.

{/* truncate */}

![A pooled database connection serving organization A and then organization B. The organization setting is set inside each transaction and gone when it ends.](/img/blog/postgres-rls-with-connection-pools.svg)

## Mistake 1: scoping a pooled connection with a session-level setting

A policy needs to know which tenant is asking. The usual trick is a custom setting, such as `app.current_org_id`, that the policy reads. The mistake is setting it for the whole session. A session-level setting belongs to the connection. When the pool hands that connection to the next request, the setting is still there. If the next request forgets to set its own, it runs as the previous tenant.

PostgreSQL's `set_config` function has a flag for exactly this. The documentation says: "If `is_local` is `true`, the new value will only apply during the current transaction. If you want the new value to apply for the rest of the current session, use `false` instead." ([administration functions](https://www.postgresql.org/docs/current/functions-admin.html))

OpenProxyAI uses the transaction-local form. In `backend/app/database.py`:

```python
_SET_ORG_SQL = text("SELECT set_config('app.current_org_id', :org_id, true)")
```

The last argument is `true`, so the value dies with the transaction. A comment in the same file also explains why it clears the value the same way when no org is given: a plain `RESET` is session-scoped "and would leak to pooled connections".

The cost of this choice is that the scope disappears at every commit. A route that sets the org once, commits, and keeps querying would lose it. So the code registers a listener on the session's `after_begin` event that sets the org again at the start of every transaction. A test, `test_org_scope_survives_commit`, runs a query before and after a commit and checks both see the same rows.

## Mistake 2: a database role that skips the policy

The second mistake is the quietest one, because everything appears to work. PostgreSQL's documentation says: "Superusers and roles with the BYPASSRLS attribute always bypass the row security system when accessing a table. Table owners normally bypass row security as well, though a table owner can choose to be subject to row security with ALTER TABLE ... FORCE ROW LEVEL SECURITY." ([row security policies](https://www.postgresql.org/docs/current/ddl-rowsecurity.html))

A typical setup has one login role that owns the tables and runs migrations. If the application connects as that role, no policy is ever evaluated. OpenProxyAI handles it in two layers:

- **A separate role for requests.** The migration that introduced RLS (`f8a9b0c1d2e3`) creates a plain `app_user` role. The request engine runs `SET ROLE` to that role on every new connection (`set_app_role` in `database.py`, role name from `DB_APP_ROLE`). The test `test_request_engine_runs_as_app_role` checks `current_user` is the app role.
- **`FORCE ROW LEVEL SECURITY` on the tables.** The RLS migrations run `ENABLE` and `FORCE` on each table, then create a policy named `rls_org_isolation`. `FORCE` covers the owner case, in case a connection ever runs as the table owner.

The CI workflow comments that its login role "is a superuser, which is exactly the case these tests must survive". So the test suite runs with the most dangerous login role on purpose, and the request path still has to be isolated.

## What the policy does when no org is set

Every table policy in the migrations has the same shape:

```sql
org_id = NULLIF(current_setting('app.current_org_id', true), '')::uuid
```

It is used for both `USING` (which rows are visible) and `WITH CHECK` (which rows may be written). Two details matter.

- `current_setting(..., true)` does not raise an error when the setting is missing. The PostgreSQL docs say it returns NULL in that case.
- `NULLIF(..., '')` turns an empty string into NULL, so an empty value behaves like a missing one.

A comparison with NULL is never true, so no row matches. The result is fail closed: a request that never set its org sees nothing, and cannot write. The test `test_request_session_without_org_sees_nothing` shows this on `api_keys`. The `WITH CHECK` half is tested by `test_rls_rejects_insert_for_another_org`: a session scoped to organization A tries to insert a row for B, and the database refuses with a row-level security error.

## How the org reaches Postgres before anyone is authenticated

There is a chicken-and-egg problem. To read an API key row you need an org. To know the org you need to read the key. An earlier version used a `SECURITY DEFINER` function that bypassed RLS. A later migration (`q8l9m0n1o2p3`) replaced it with a small `api_key_lookup` table that has no RLS and holds only the key hash, the org id and the key id. The code in `auth_service.validate_api_key` looks the hash up there, sets the org on the session, then loads the real key row with RLS in force. For JWT requests, `dependencies.py` takes the org from the token claim and sets it before the first query.

## Mistake 3: background jobs with nobody to scope them

A job that runs for every tenant has no request to borrow a scope from. There are two honest options, and OpenProxyAI uses both on purpose.

- **Scoped writes.** `org_scoped_session(org_id)` opens a request-role session already scoped to one org. Its docstring says a wrong org "fails loudly instead of leaking". Batch work, audit logging and evaluation runs use it.
- **A separate system session for reads that must cross tenants.** `system_engine` keeps the login role and is documented as "Only for jobs that must read across orgs". The provider health check, for example, lists active keys for every org through the system session, and then writes each result back through a normal session scoped to that key's org.

The test `test_system_session_reads_across_orgs` shows the contrast: the same query that returns nothing for a scoped request session returns rows for the system session.

## How the tests prove it against a real database

The isolation tests (`backend/tests/test_rls_isolation.py`) run on PostgreSQL, not on a mock. They create two organizations, then check that with organization A set, a count of B's rows in each of 16 listed tables is zero. They also check append-only request logs, upsert collisions on `request_scores`, and captured payloads written under the same request id by two orgs.

A silent skip would defeat the point, so the file reads `RLS_TESTS_REQUIRED`. When it is set and the database URL is missing or not PostgreSQL, the file raises an error instead of skipping. CI sets it. Many other `*_db.py` test files follow the same pattern for newer tables.

## What this does not do

- **Nothing stops code from using the system session by mistake.** It bypasses RLS by design. The protection is a convention plus review, not a database rule.
- **The explicit isolation test lists 16 tables.** Newer tables have their own database tests, but this post did not verify that every table in the schema has one.
- **The schema doc is behind the code.** `docs/architecture/database-schema.md` lists six tables and says the app runs `SET LOCAL`, while the code calls `set_config` with the local flag, and many more tables carry the same policy in later migrations.
- **A multi-org flush on one session depends on ordering.** `spend_batch_service` re-sets the org between groups on a single session. This post read the comment there but did not trace flush timing, so treat that path as something to test.
- **RLS is not authentication.** It limits which rows a scoped session can see. The org still has to come from a verified token or key.

## What to do now

- Search your own code for session-level `SET` of any tenant variable. Replace it with a transaction-local setting.
- Check which role your application connects as. Run `SELECT current_user` from the app, and check that role is not a superuser and has no `BYPASSRLS`.
- Add `FORCE ROW LEVEL SECURITY` to tables the application role owns.
- Write the "no org set returns nothing" test first. It is the one that catches a forgotten scope.
- Run the tests as a superuser login role in CI, as above.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

Needs Docker and no provider key. The console is at http://localhost:5173.

## Sources

- [PostgreSQL: Row Security Policies](https://www.postgresql.org/docs/current/ddl-rowsecurity.html): who bypasses RLS and what `FORCE` changes.
- [PostgreSQL: System Administration Functions](https://www.postgresql.org/docs/current/functions-admin.html): `set_config`, `is_local`, and `current_setting` with `missing_ok`.
- [Row-level security: making data leaks impossible by construction](/blog/row-level-security-by-construction): the earlier post on the idea.
- [Row-Level Security](/security/row-level-security): product documentation.
- Repo files: `backend/app/database.py`, `backend/alembic/versions/f8a9b0c1d2e3_add_rls_policies.py`, `backend/alembic/versions/q8l9m0n1o2p3_fix_get_api_key_by_hash_rls_bypass.py`, `backend/tests/test_rls_isolation.py`, `.github/workflows/ci.yml`.

These statements are based on the OpenProxyAI source and docs read on November 13, 2026, and on the PostgreSQL documentation pages above opened the same day.
