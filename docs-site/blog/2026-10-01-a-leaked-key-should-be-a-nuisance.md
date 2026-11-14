---
slug: a-leaked-key-should-be-a-nuisance
image: /img/blog/og/a-leaked-key-should-be-a-nuisance.png
title: "Keys will leak: design so a leaked application key is a nuisance, not a breach"
tags: [security, engineering]
description: How to set up OpenProxyAI so a leaked application key has a small reach, and a ten minute incident walkthrough that ends with the key revoked and the activity reviewed.
---

Application keys end up in public repositories, chat logs and screenshots. That will happen to you at some point, so the useful question is how much damage one leaked key can do and how fast you can stop it. In OpenProxyAI a key is checked on every request, so revoking it works on the next call. What the key could do before that depends on choices you make when you set it up. This post walks through both.

{/* truncate */}

![A timeline of the first ten minutes after a key leaks: the key is public at minute 0, its id is found at minute 2, it is revoked at minute 4, the next call is refused at minute 5, and logs are queried by key id at minute 10. The key keeps working, within its scope, until the revoke.](/img/blog/a-leaked-key-should-be-a-nuisance.svg)

## The problem

An application key lets software call the gateway as a person. A leaked key is a stranger spending your model budget, reading what your policies allow, and possibly calling your tools. Two things set the damage: what the key is allowed to reach, and how long it works after you notice.

## How a key works

- **Shown once.** The full key is returned only at creation. The gateway keeps a hash and a short prefix, so a database copy does not reveal usable keys.
- **Checked every time.** On each request the gateway verifies the key, and refuses it if it is revoked, expired, or its owner is deactivated. Nothing is cached for authorization, so a revoke applies to the very next call.

## What a key can be limited by

| Lever | What it does |
|---|---|
| Permissions | Keys carry permissions such as model access and MCP access |
| Team | A key can belong to a team, so its requests count against that team's limits |
| Expiry | An expiry date is enforced on every request |
| MCP call rate | Each key has its own tool-call rate limit |
| MCP scope | Tool grants can target one API key, and a key attached to a bundle can only use tools through that bundle. See [MCP gateway](/guides/mcp-gateway) |
| Budgets | Per user, per team and per organization |

The practical design: give each application its own service user with a small daily budget, issue its keys from that user, and put the key on a team. The demo stack does a version of this: its intern key belongs to a user with a one cent daily budget. The budget belongs to the user, so every key that user owns shares it.

Read [Rate limiting and budgets](/core-concepts/rate-limiting-and-budgets) for how the limits behave. Whatever those limits are, they are the ceiling for a leaked key.

## An incident, step by step

This is a hypothetical walkthrough: a key lands in a public repository.

**Minutes 0 to 2: find the key's id.** The secret is public, so you know its prefix. The key's owner can list their own keys with the API keys endpoint, which returns the id, name, prefix, permissions, status, expiry and team. An admin who does not own the key can open the analytics overview, which breaks down the busiest keys with their id, name, prefix, requests, tokens and cost.

**Minute 4: revoke.** Send a `DELETE` for the key from the console's API keys page or the API. A `204` means the key is inactive. Only the owner or an admin can do this. Requests already running, including a stream that has started, finish. New requests are refused.

**Minute 5: check.** Send any request with the leaked key. Expect `401`.

**If the whole account is suspect,** deactivate the user. Every key that user owns stops working, and the change is written to the audit log.

**Minute 10 and after: what did it do?** Request logs record which key made each call. Admins can query the logs filtered to that key, grouped by model and status, with spend and first and last timestamps. Check which models were called, whether any calls were blocked by policy, and how much was spent. Tool calls through the MCP gateway are in the audit log as well. See [Audit logging](/security/audit-logging).

Then issue a replacement: create a new key under a different name, deploy it, and revoke the old one.

## What to do now

1. Issue keys per application from a service user with a daily budget.
2. Put each key on a team and set an expiry.
3. For agents, add an MCP grant or bundle so the key reaches only the tools it needs.
4. Know where you would find a key id before you need it: the analytics overview, or the key column in request logs.
5. Practice the revoke once, and write down who did it.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

Needs Docker, no provider key. Console at http://localhost:5173. The demo keys are public on purpose. Never publish real keys that way. Star the repo or open an issue if you have a key-handling scenario you want covered.

## Sources

- OpenProxyAI docs: [API keys](/api-reference/keys), [Authentication](/getting-started/authentication), [Rate limiting and budgets](/core-concepts/rate-limiting-and-budgets), [MCP gateway](/guides/mcp-gateway), [Audit logging](/security/audit-logging), [Row-level security](/security/row-level-security).
- On this blog: [MCP tool descriptions are untrusted input](/blog/mcp-tool-descriptions-are-untrusted-input), [Row-level security by construction](/blog/row-level-security-by-construction).

These statements are based on OpenProxyAI's behavior at the post date.
