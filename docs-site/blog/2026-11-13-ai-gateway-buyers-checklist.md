---
slug: ai-gateway-buyers-checklist
title: "An AI gateway buyer's checklist: twelve questions, and how to test the answers"
tags: [architecture, security]
description: Every AI gateway claims policy, audit and cost control. Twelve questions that separate the claims from the behavior, each with a test you can run in an afternoon, and how OpenProxyAI answers them.
---

Every AI gateway page lists the same words: policy, guardrails, audit, cost control, multi-provider. The words are cheap. What matters is what the gateway does at 3 a.m. when a key is revoked, a provider is down, or a prompt contains something it should not. Here are twelve questions to ask, a test for each, and how OpenProxyAI answers.

{/* truncate */}

A note on method. A gateway is a control point: everything passes through it, so a mistake is paid for by every application behind it. Ask for demonstrations, not documents. If a vendor cannot show you the behavior in a trial environment, treat it as unproven.

## 1. Where does my data go, and who can read it?

**Test:** Send a prompt with a made-up customer name. Search the vendor's logs, storage and traces for it. Ask where it can appear.

**Ours:** OpenProxyAI is self-hosted, so the gateway runs in your environment and prompts do not pass through us. By default it keeps request metadata only: model, tokens, cost, status and the policy decision. Keeping redacted samples of prompts and answers (payload capture) is opt-in and stays off until you turn it on.

## 2. What happens when no approved route is available?

**Test:** In staging, disable the only key for a model that handles sensitive data, then send a request that names a different model as a fallback.

**Ours:** The request is refused with HTTP 446 and a plain reason, and no provider is called. A caller-supplied fallback does not rescue it. The output is published in [When every authorized provider is down](/blog/when-every-authorized-provider-is-down).

## 3. Does a refusal tell the user something useful, and nothing dangerous?

**Test:** Trigger a block and read the whole response. Does it say what to do? Does it name the keyword, the pattern or the rule? That last part helps whoever is trying to get around it.

**Ours:** A blocked request carries one plain sentence meant for the end user. It names the model the caller asked for and the data class of the request, never the keyword, pattern or setting behind it. See [Refusals should explain themselves](/blog/refusals-should-explain-themselves).

## 4. Where do provider keys live, and what does the console show?

**Test:** Create a key, then look at every place it could appear: the API response, the console, the logs, the database.

**Ours:** Keys are stored encrypted, and the console lists a prefix only. A key can instead point at a secret in HashiCorp Vault or AWS Secrets Manager, in which case the gateway holds no stored copy. See [Provider keys from Vault](/guides/secrets-from-vault).

## 5. How is one customer or business unit kept from another?

**Test:** Ask for the tenant isolation design, then ask for the test that proves it. Better, try to read another tenant's data with a valid login.

**Ours:** Isolation is enforced inside the database with PostgreSQL row-level security, so a forgotten filter in application code still returns nothing from another organization. Tests run against a real database to prove it. The semantic cache is scoped per organization, and [A semantic cache is shared memory](/blog/semantic-cache-is-shared-memory) explains how to use it well.

![The OpenProxyAI model registry: a table of vetted models, each with its provider key, the most sensitive data class it may receive, regions, risk rating, retention and whether it trains on data.](/img/blog/console-model-registry.png)

## 6. Can I say which models may see which data, and is it enforced?

**Test:** Mark a model as unsuitable for confidential data. Then send a confidential prompt that asks for it, and one that uses every fallback path you can find.

**Ours:** A registry records, per model, the most sensitive class it may receive, its regions, risk rating and retention. With routing set to enforce, a request is served only by a model the registry clears, through the key it was registered with. If none qualifies, it is refused before any provider call.

## 7. What does it add to latency?

**Test:** Measure end to end with the gateway and without, at your real request size, with streaming on. Ask for the percentile, not the average.

**Ours:** The gateway sits in the path as a thin layer next to the provider's own latency, and a cache hit replaces the provider round trip entirely. Measure it with your own traffic, as you would any component.

## 8. How do I control cost, including for models with no price?

**Test:** Set a tiny budget and send traffic. Then call a model your gateway cannot price.

**Ours:** Rate limits and dollar budgets are set per team, and a user can carry a daily and monthly budget of their own. A model without a listed price never costs you an answer: the call completes and the cost is recorded as a flagged estimate, so it counts against budgets.

## 9. What is in the audit trail, and can I get it out?

**Test:** Make a change as an admin, send a blocked request, then try to answer "who did what, when, and what did the system decide" without asking the vendor.

**Ours:** Every request is logged with its policy decision, routing outcome, cost and latency. Admin actions, such as creating a key or changing a policy, go to a separate admin audit log. Exports are available for a date range, suitable for an auditor.

## 10. How does it handle agents and tools?

**Test:** Register a tool server, change one of its tool descriptions after approval, and see whether the agent notices. Then have one tool return text that tells the agent to call another.

**Ours:** The MCP gateway can pin tool definitions by hash and flag or hide a tool that changed, scan descriptions and results for injection, restrict tools per role, team, user or key, and refuse tools with side effects in a session that has seen untrusted output. See [MCP 2026-07-28 removes the session](/blog/mcp-2026-07-28-for-gateway-operators).

## 11. What is the supply-chain story?

**Test:** Ask what you are installing and whether you can inspect it. Ask how you would verify a release before it runs in your environment.

**Ours:** The full source is public on GitHub, so you can read what you install and review it with your own tooling before it touches production. The demo stack runs locally with no provider key, which gives you a safe place to evaluate a release first.

## 12. Can I leave?

**Test:** Ask what it takes to move to another gateway or to no gateway. Is the API standard? Is the data in a format you can read?

**Ours:** The API is OpenAI-compatible, so applications built on the OpenAI client libraries can move on or off the gateway by changing a base URL and their model names. The code is open source under Apache-2.0, and your data lives in a standard database you operate.

## How to use this list

Score each question as shown, partly shown, or only claimed. Weigh the answers by your own risk: a team with regulated data should treat questions 2, 5, 6 and 11 as gates; a team with a large bill may care most about 8. And repeat the tests after every upgrade, because a control that held last quarter is not a control until it is tested again.

## Try ours against it

The demo runs with Docker, needs no provider key, and lets you run several of these tests yourself: blocked requests, the registry, key handling, the cache headers and the MCP settings. Console at http://localhost:5173.

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

If it is useful, star the repo or open an issue with the question you would add to the list. Then see [Quickstart](/getting-started/quickstart), [Policies and guardrails](/core-concepts/policies-and-guardrails) and the [Trust center](/security/trust-center).

## Sources

- On this blog: [When every authorized provider is down](/blog/when-every-authorized-provider-is-down), [Refusals should explain themselves](/blog/refusals-should-explain-themselves), [A semantic cache is shared memory](/blog/semantic-cache-is-shared-memory), [MCP 2026-07-28](/blog/mcp-2026-07-28-for-gateway-operators).
- OpenProxyAI docs: [Request pipeline](/core-concepts/request-pipeline), [Provider keys from Vault](/guides/secrets-from-vault), [Audit logging](/security/audit-logging), [Row-level security](/security/row-level-security).

These statements are based on OpenProxyAI's behavior at the post date.
