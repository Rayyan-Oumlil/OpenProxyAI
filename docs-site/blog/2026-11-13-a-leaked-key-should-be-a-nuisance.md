---
slug: a-leaked-key-should-be-a-nuisance
title: "Keys will leak: design so a leaked application key is a nuisance, not a breach"
tags: [security, engineering]
description: What a leaked OpenProxyAI application key can and cannot do, how revocation takes effect, a ten minute incident walkthrough with real API calls, and the limits we found, including what is not audited.
---

Application keys end up in public repositories, chat logs and screenshots. That will happen to you at some point, so the useful question is how much damage one leaked key can do and how fast you can stop it. In OpenProxyAI a key is checked against the database on every request, so revoking it works on the next call. What the key could do before that depends on choices you make when you set it up. This post walks through both, using only behavior we read in the code and tests, and says plainly where the controls are thin.

{/* truncate */}

![A timeline of the first ten minutes after a key leaks: the key is public at minute 0, its id is found at minute 2, it is revoked at minute 4, the next call is refused at minute 5, and logs are queried by key id at minute 10. The key keeps working, within its scope, until the revoke.](/img/blog/a-leaked-key-should-be-a-nuisance.svg)

## The problem

An application key lets software call the gateway as a person. A leaked key is a stranger spending your model budget, reading what your policies allow, and possibly calling your tools. Two things set the damage: what the key is allowed to reach, and how long it works after you notice.

## How a key works

Each fact below comes from the key code and its tests.

- **Format.** `opai_<env>_<8 hex id>_<32 hex secret><4 character checksum>`, where env is `dev` or `prod`. The checksum is a hash of the rest of the key, so it catches typos. It is not a secret.
- **Storage.** The database keeps a SHA-256 hash of the key and an 18 character prefix. The full key is returned once, at creation. If you lose it, you cannot get it back.
- **Why a fast hash.** Our reasoning, not a claim from the code: the secret part is 128 random bits, so there is nothing to guess, and a slow password hash would only add cost to every request.
- **Checks on every request.** The gateway looks up the hash, loads the key, and refuses it if the key is inactive, expired, or its owner is inactive. A test asserts that a revoked or expired key stops working at once, even inside the window where "last used" is not rewritten. Only "last used" is throttled (one write a minute). Authorization is not cached.

## What a key can be limited by

| Lever | What exists |
|---|---|
| Permission strings | `proxy:mcp` is required for `/v1/mcp`. `proxy:llm` is required for the files and batches routes and for feedback. The default is `proxy:llm`. |
| Team | A key can carry a `team_id`. Its requests then count against that team, and the owner must be a member of the team when the request runs. |
| Expiry | `expires_at` is accepted by the API and enforced on every request. |
| Per-key rate limit | MCP only: 120 requests per minute per key by default (`MCP_RATE_LIMIT_PER_MINUTE`). |
| MCP scope | Tool grants can target an `api_key`, and a key attached to a bundle can only use tools through that bundle. See [MCP gateway](/guides/mcp-gateway). |
| Budgets | Per user (`budget_daily_usd`), per team (monthly), and per organization (daily). Not per key. |

The practical design: give each application its own service user with a small daily budget, issue its keys from that user, and put the key on a team. The demo stack does a version of this. Its intern key belongs to a user with a $0.01 daily budget and only the `proxy:llm` permission (see the demo guide in the repository). The budget belongs to the user, so every key that user owns shares it.

Read [Rate limiting and budgets](/core-concepts/rate-limiting-and-budgets) for how the org and team limits behave. Whatever those limits are, a leaked key can spend up to them.

## An incident, step by step

This is hypothetical. A key lands in a public repository. We did not run these calls against a live gateway for this post. The request shapes come from the route code and tests.

**Minutes 0 to 2: find the key's id.** The secret is public, so you know its prefix. The key's owner can list their own keys:

```bash
curl -s https://your-gateway/api/v1/api-keys \
  -H "Authorization: Bearer $SESSION_TOKEN"
```

The list returns `id`, `name`, `key_prefix`, `permissions`, `is_active`, `expires_at` and `team_id`. It lists only the caller's own keys, even for an admin. An admin who does not own the key can read the analytics overview, which has a `by_key` section with the key id, name, prefix, requests, tokens and cost for the busiest keys:

```bash
curl -s "https://your-gateway/api/v1/analytics/overview?period_days=1" \
  -H "Authorization: Bearer $ADMIN_SESSION_TOKEN"
```

**Minute 4: revoke.**

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X DELETE \
  https://your-gateway/api/v1/api-keys/$KEY_ID \
  -H "Authorization: Bearer $ADMIN_SESSION_TOKEN"
```

A `204` means the key is inactive. Only the owner or an admin can do this. Anyone else gets a `404`, so an id does not confirm that a key exists. The console does the same from the API keys page, and its confirmation says anything using the prefix stops working immediately. Requests already running, including a stream that has started, are not interrupted. New requests get a `401`.

**Minute 5: check.** Send any request with the leaked key. Expect `401` with "Invalid credentials".

**If the whole account is suspect,** deactivate the user with `PATCH /api/v1/users/{user_id}` and `{"is_active": false}`. Every key that user owns stops working, and the change is written to the audit log as `user.deactivated`.

**Minute 10 and after: what did it do?** Request logs record the `api_key_id`. Admins can query them:

```json
POST /api/v1/analytics/query
{
  "view": "requests",
  "select": ["model", "status_code", {"agg": "count", "as": "calls"}, {"agg": "sum", "column": "cost_usd", "as": "spend"}],
  "where": [{"column": "api_key_id", "op": "=", "value": "<key id>"}],
  "group_by": ["model", "status_code"],
  "since": "2026-11-13T00:00:00Z"
}
```

Look at which models were called, whether any calls were blocked by policy, the spend, and the first and last timestamps. The query itself is written to the admin audit log, with the query spec and not the rows. Tool calls through the MCP gateway are written to the audit log as well, per the MCP guide.

Then issue a replacement. There is no rotate endpoint for application keys: create a new key under a different name (an active key name must be unique per user), deploy it, and revoke the old one. The rotate endpoint in the API reference is for provider keys, a different thing.

## What this does not do

- **No per-key budget or rate limit for model calls.** Limits apply to the user, team and organization. A leaked key can spend what its owner's remaining budget allows.
- **No IP allowlist for keys.** We searched the backend and found none for application keys.
- **Creating and revoking a key is not in the admin audit log.** The routes do not write an entry. A revoked key keeps its row with `is_active` set to false, and no record of who revoked it or when. Write your own incident note.
- **The permission check is not applied everywhere.** We found `proxy:llm` checked on files, batches and feedback, but did not find a permission check on chat completions or embeddings. Permission strings are also not validated against a list. Do not rely on `proxy:llm` alone to keep a key away from model calls.
- **The console creates keys with `proxy:llm` and no expiry.** Set `expires_at` through the API if you want one.
- **No reactivation.** There is no endpoint to turn a revoked key back on.
- **"Last used" is stored but not returned** by the key endpoints.
- **No leak detection.** We found nothing that scans for leaked keys. Rejected attempts with a revoked key fail in the auth step, and we did not find a log of them.

## What to do now

1. Issue keys per application from a service user with a daily budget.
2. Put each key on a team and set `expires_at`.
3. For agents, add an MCP grant or bundle so the key reaches only the tools it needs.
4. Know where you would find a key id before you need it: the overview `by_key` section, or the `api_key_id` column in request logs.
5. Practice the revoke once, and write down who did it.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

Needs Docker, no provider key. Console: http://localhost:5173. The demo keys are printed in the repository on purpose. Never publish real keys that way.

## Sources

- OpenProxyAI docs: [API keys](/api-reference/api-keys), [Authentication](/getting-started/authentication), [Rate limiting and budgets](/core-concepts/rate-limiting-and-budgets), [MCP gateway](/guides/mcp-gateway), [Audit logging](/security/audit-logging), [Row-level security](/security/row-level-security).
- On this blog: [MCP tool descriptions are untrusted input](/blog/mcp-tool-descriptions-are-untrusted-input), [Row-level security by construction](/blog/row-level-security-by-construction).

These statements are based on the OpenProxyAI source code, tests and docs as read on November 13, 2026. The incident is a hypothetical walkthrough, and no command in it was run for this post.
