---
slug: postgres-rls-with-connection-pools
title: "Row-level security and connection pools: the mistakes that leak across tenants"
tags: [security, engineering]
description: "Row-level security is easy to demo and easy to get wrong behind a connection pool. How OpenProxyAI keeps every tenant's data scoped to the request, even when connections are shared."
---

Row-level security (RLS) is easy to demo and easy to get wrong in production. The demo uses one connection and one tenant. Production uses a pool, where one database connection serves tenant A now and tenant B a moment later. Most RLS leaks come from that gap: a setting that outlived its request, a role that skips the policy, or a background job that nobody scoped. This post covers what OpenProxyAI does about each. It builds on the earlier post [Row-level security: making data leaks impossible by construction](/blog/row-level-security-by-construction), which explains why the boundary belongs in the database.

{/* truncate */}

![A pooled database connection serving organization A and then organization B. The organization scope is set inside each transaction and gone when it ends.](/img/blog/postgres-rls-with-connection-pools.svg)

## Mistake 1: scoping a pooled connection for the whole session

A policy needs to know which tenant is asking, so the application tells PostgreSQL the current organization. The trap is scoping it for the whole session. A session-level value belongs to the connection. When the pool hands that connection to the next request, the value is still there, and a request that forgets to set its own runs as the previous tenant.

PostgreSQL has a transaction-local form for exactly this. Its documentation says that when the local flag is true, "the new value will only apply during the current transaction." ([administration functions](https://www.postgresql.org/docs/current/functions-admin.html))

OpenProxyAI scopes the organization inside each transaction, so the value disappears when the transaction ends and cannot leak to whoever receives the connection next. It is re-applied at the start of every transaction, so a request that commits and keeps working stays correctly scoped.

## Mistake 2: a database role that skips the policy

The second mistake is the quietest one, because everything appears to work. PostgreSQL's documentation says: "Superusers and roles with the BYPASSRLS attribute always bypass the row security system when accessing a table. Table owners normally bypass row security as well, though a table owner can choose to be subject to row security with ALTER TABLE ... FORCE ROW LEVEL SECURITY." ([row security policies](https://www.postgresql.org/docs/current/ddl-rowsecurity.html))

A typical setup has one login role that owns the tables and runs migrations. If the application connects as that role, no policy is ever evaluated. OpenProxyAI protects against this in two layers:

- **A separate role for requests.** Request traffic runs as a plain application role that is subject to the policies, not as the role that owns the tables.
- **Forced row-level security on the tables.** Policies apply even to the table owner, in case a connection ever runs as that role.

The test suite runs with a deliberately powerful login role, so the request path has to prove its isolation under the most dangerous conditions.

## What the policy does when no organization is set

Every table policy has the same shape: a row is visible and writable only when its organization matches the organization of the current request. It applies both to which rows a request can see and to which rows it may write.

When a request never set its organization, the comparison matches nothing. The result fails closed: such a request sees no rows and cannot write any. Tests confirm this, and confirm that a session scoped to organization A cannot insert a row for organization B. The database itself refuses.

## Reaching the organization before anyone is authenticated

There is a chicken-and-egg problem. To read an API key row you need an organization, and to know the organization you need to read the key. OpenProxyAI solves it with a minimal lookup that holds only what is needed to resolve a key to its organization, without relying on any privileged bypass. The organization is then set on the session, and the real key record is loaded with row-level security in force. For token-based requests, the organization comes from the verified token before the first query.

## Mistake 3: background jobs with nobody to scope them

A job that runs for every tenant has no request to borrow a scope from. There are two honest options, and OpenProxyAI uses both on purpose.

- **Scoped sessions.** Batch work, audit logging and evaluation runs open a session already scoped to one organization. Using the wrong organization fails loudly instead of leaking.
- **A separate system session for reads that must cross tenants.** The provider health check, for example, lists active keys across organizations, then writes each result back through a normal session scoped to that key's organization.

Tests show the contrast: the same query that returns nothing for a scoped request returns rows for the system session, which is reserved for these jobs.

## Proving it against a real database

The isolation tests run on PostgreSQL, not on a mock. They create two organizations and check that, with organization A set, none of B's rows are visible in any of the tenant tables. They also cover append-only request logs and records written under the same identifier by two organizations.

A silent skip would defeat the point, so CI marks these tests as required. If the database is missing, the run fails instead of skipping.

## What to do now

- Search your own code for session-level settings that carry a tenant identifier. Replace them with a transaction-local setting.
- Check which role your application connects as. It should not be a superuser and should not have the bypass attribute.
- Enable forced row-level security on tables the application role owns.
- Write the "no organization set returns nothing" test first. It catches a forgotten scope.
- Run your tests with a powerful login role in CI, so the isolation has to hold under the worst case.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

Needs Docker, no provider key. Console at http://localhost:5173. If tenant isolation matters to you, star the repo or open an issue with your use case.

## Sources

- [PostgreSQL: Row Security Policies](https://www.postgresql.org/docs/current/ddl-rowsecurity.html): who bypasses RLS and what `FORCE` changes.
- [PostgreSQL: System Administration Functions](https://www.postgresql.org/docs/current/functions-admin.html): transaction-local settings.
- [Row-level security: making data leaks impossible by construction](/blog/row-level-security-by-construction): the earlier post on the idea.
- [Row-Level Security](/security/row-level-security): product documentation.

These statements are based on OpenProxyAI's behavior at the post date, and on the PostgreSQL documentation pages above.
