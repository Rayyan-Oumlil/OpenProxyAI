---
slug: ai-keys-are-leaking-keep-them-out-of-your-apps
title: "AI service keys leaked 81% more in 2025. Keep provider keys out of your apps"
tags: [security, product]
description: "GitGuardian's State of Secrets Sprawl 2026 counts 1,275,105 leaked AI service secrets in 2025, up 81%. Here is how a gateway keeps provider keys out of apps and makes the keys apps do hold short-lived and revocable."
---

GitGuardian published its State of Secrets Sprawl 2026 report on March 17, 2026. The headline for anyone building with LLMs: secrets tied to AI services reached 1,275,105 in 2025, up 81% from the year before. Eight of the ten fastest-growing kinds of leaked secret were AI related. Every one of those keys started life in someone's app, script or config file. The fix is not a better habit. It is fewer places where a key can live.

{/* truncate */}

![A diagram with three boxes. Your apps hold only application keys that can expire and be revoked. The gateway checks the key on each call and applies policy and budgets. Provider keys sit behind the gateway, encrypted or kept in Vault or AWS secrets.](/img/blog/ai-keys-are-leaking-keep-them-out-of-your-apps.svg)

## What the report found

All figures below come from GitGuardian's own write-up of the report.

| Finding | Figure |
|---|---|
| New hardcoded secrets added to public GitHub commits in 2025 | 28.65 million, up 34% year over year |
| AI service secrets detected | 1,275,105, up 81% year over year |
| Fastest-growing secret types that are AI related | 8 of the top 10 |
| LLM infrastructure (orchestration, RAG, vector storage) vs core model providers | Leaked 5 times faster |
| Leaked DeepSeek API keys cited as an example | 113,000 |
| Secrets found in MCP-related configuration files | 24,008 unique secrets, 2,117 of them valid (8.8%) |
| Credentials confirmed valid in 2022 that were still valid when retested in January 2026 | More than 64% |

The last row matters most. A leaked key is not a one-day problem. Many stay live for years because nobody revokes them.

## What it means for teams shipping AI features

An AI feature touches more secrets than a normal app: a model key, a vector store key, an orchestration key, tool credentials. Each one gets copied into a notebook, a `.env` file, a CI variable and a teammate's laptop. The more copies, the more places to leak, and the harder it is to rotate when one does.

Two design rules shrink the problem:

1. **Apps should not hold provider keys at all.** If the OpenAI or Anthropic key lives in one place, there is one place to protect and one place to rotate.
2. **The key an app does hold should be cheap to lose.** It should be revocable in seconds, able to expire, and limited in what it can spend.

## How OpenProxyAI handles it

OpenProxyAI is an open-source, self-hosted gateway. Your apps call one OpenAI-compatible endpoint with an application key. The provider keys stay inside the gateway.

**Provider keys are held in one place.**
- A provider key is stored encrypted and is never returned by the API. The key list shows a short prefix only.
- If your security team wants no copy in the gateway at all, a provider key can point at a secret in HashiCorp Vault or AWS Secrets Manager instead. The gateway reads it when a request needs it and keeps no stored copy. Rotate it in Vault or AWS, and the gateway picks up the new value without a restart.
- Each organization can reach only its own folder of secrets. If a secret cannot be read, the gateway refuses to serve through that key. It never quietly falls back to a different credential.
- The key value appears in no response, log line or audit entry.

**Application keys are made to be lost.**
- An application key is shown in full once, at creation. The gateway stores only a hash and a prefix, so there is no database of usable keys to steal.
- Keys can carry an expiry date. Expired keys are refused.
- Every request is checked against the current state of the key. Revoke a key and the next call gets a 401.
- A key can be tied to a team, so its usage counts against that team's budget and limits.

**Spend is capped before you notice.** Budgets apply per user, per team and per organization, and requests over a limit are refused with a 429. A leaked key can spend up to what its owner has left, not more. Give each application its own service user with a modest daily budget, and the worst case is a number you chose in advance.

**Tools are covered too.** The report found secrets sitting in MCP configuration files. When agents reach tools through the OpenProxyAI MCP gateway, the agent holds an application key, and tool credentials stay on the gateway side. Grants decide which tools each key can use. See the [MCP gateway guide](/guides/mcp-gateway).

## A worked scenario

A team ships a support assistant. Before: the model key is in the app's environment, in a CI variable and in two developers' notebooks. After:

| Step | What changes |
|---|---|
| 1 | The provider key moves into Vault. The gateway holds a pointer, not a copy. |
| 2 | The assistant gets its own service user with a small daily budget and its own application key, set to expire. |
| 3 | The assistant calls the gateway. The provider key is nowhere in its code or config. |
| 4 | A developer pastes the application key into a public gist. Someone revokes it from the console. The next call with it returns 401. |
| 5 | The team issues a new key, deploys it, and moves on. The provider key never changed, because it never leaked. |

## What to do now

1. List where each model, vector store and tool key lives today. Count the copies.
2. Move provider keys behind a gateway so apps hold application keys only.
3. Store provider keys in Vault or AWS Secrets Manager if you want no stored copy in the gateway.
4. Give every app its own service user, a daily budget and a key expiry.
5. Put each key on a team so spend and limits are visible per team.
6. Practice a revoke once, so it is routine when it counts.

## Good to know

A gateway protects the keys that go through it. It does not clean up keys already sitting in old repositories. Rotate those at the provider, then replace them with application keys. Budgets are set per user, team and organization, so create one service user per app if you want a per-app ceiling.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

Needs Docker, no provider key. Console at http://localhost:5173. If it helps, star the repo or open an issue with what you would like to see next.

## Sources

- GitGuardian, [The State of Secrets Sprawl 2026](https://blog.gitguardian.com/the-state-of-secrets-sprawl-2026/) (17 Mar 2026). Source of every figure in the table above.
- OpenProxyAI docs: [Provider keys from Vault](/guides/secrets-from-vault), [API keys](/api-reference/api-keys), [Provider keys API](/api-reference/provider-keys), [Authentication](/getting-started/authentication), [Rate limiting and budgets](/core-concepts/rate-limiting-and-budgets), [MCP gateway](/guides/mcp-gateway).

These statements are based on the sources above and on OpenProxyAI's behavior at the post date. OpenProxyAI ships controls and templates, not certifications.
