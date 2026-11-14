---
slug: the-gateway-as-your-ai-golden-path
image: /img/blog/og/the-gateway-as-your-ai-golden-path.png
title: "The gateway as the golden path of your internal AI platform"
tags: [product, engineering]
description: "A golden path is the easy road that is also the safe one. Make the gateway that road for AI: one endpoint, the SDK people already use, a key per team, and policy, limits and cost tracking on from the first call."
---

Platform teams talk about a golden path: the way to ship a service that is so easy that people choose it, and so well paved that safety comes with it. AI work usually has no such path. Each team picks a provider, pastes a key into a config file, and writes its own retry loop. Then a security review arrives and asks where the prompts go. The gateway can be the paved road. A new service points at one endpoint, gets a key tied to its team, and from its first request policy, limits and cost tracking are already on.

{/* truncate */}

![A new service sends requests with the OpenAI SDK and a team key to one gateway endpoint. The gateway applies policy, limits and cost tracking by default, then reaches the approved providers.](/img/blog/the-gateway-as-your-ai-golden-path.svg)

## What a golden path needs

A path only works if leaving it is harder than staying on it. For AI that means four things, in this order of importance:

1. **Nothing new to learn.** If teams need a new client library, they will skip it.
2. **Nothing to ask for.** If a key takes a ticket and a week, they will paste a personal one.
3. **Safe by default.** The checks must run without the team turning them on.
4. **Visible.** Platform and finance must see what happens without asking each team.

OpenProxyAI is built so each of these is true on day one.

## One endpoint, the SDK people already use

The gateway speaks the OpenAI request format. A team that already uses an OpenAI SDK, or a framework built on one, changes the base URL and the key and keeps the rest of its code. There is also a Python SDK and a TypeScript SDK if a team wants the gateway's extras, such as the cost and latency of each call on the response. The [migration post](/blog/migrate-to-a-gateway-in-three-lines) shows the three-line change, and [one endpoint, every provider](/blog/one-endpoint-every-provider) explains why the app never needs to know which provider answered.

This is the first reason the road gets used. Moving onto it is a small diff in a pull request, not a project.

## A key per team, issued without a ticket

Each application gets its own gateway key. Any member can create keys for themselves, and a key can be tied to a team they belong to. From then on, every request with that key counts against that team's limits and budget, with no extra header in the code.

A few properties make this a good default:

- The full key is shown once, at creation. Only a hash is stored.
- A key can carry an expiry date, so a forgotten key stops working on its own.
- A key carries only the permissions it needs. Chat is the default, and tool access through the MCP gateway is a separate permission.
- Revoking a key takes effect on the next request. Deactivating a person stops all of their keys.

Provider credentials stay with the platform. Teams never hold a provider key, so there is nothing for them to leak and nothing for you to chase when someone leaves. See [a leaked key should be a nuisance](/blog/a-leaked-key-should-be-a-nuisance) for the longer argument, and the [API keys reference](/api-reference/keys) for the details.

## Policy, limits and cost: on by default

This is the part that turns a convenience into a platform. Because the checks live in the gateway, a new service inherits them.

| Concern | What the new service gets without doing anything |
|---|---|
| Guardrails | The organization policy runs on every request: model allowlist, blocked keywords, personal data checks and prompt injection checks. Guardrails come from the policy, never from a request header, so a team cannot switch them off by accident. |
| Limits | Organization limits, a daily budget per user and a monthly budget per team. A refused call returns a clear message that names the limit. |
| Cost | Every response reports its cost. Spend rolls up by team, user, key and model. |
| Audit | Every request is logged with its policy decision, routing and cost. |
| Routing | Data class rules and the model registry decide which approved models may see a given request. |

A policy can start in a log-only mode where violations are recorded but nothing is blocked, so you can roll out a rule and watch its hits before enforcing it. The post on [rolling out guardrails without breaking teams](/blog/roll-out-guardrails-without-breaking-teams) covers that rollout. Compliance templates give you a starting policy, and they are configuration presets, not certifications.

## Self-service, with the platform team in control

The golden path should not need the platform team for routine work. It should still let the platform team change the rules for everyone at once.

| Who | What they do alone |
|---|---|
| Developer | Create and revoke their own keys, pick a model, tag requests with labels, read their team's spend. |
| Platform admin | Create teams and budgets, edit policy, register providers and models, review the audit log. |

Policy changes take effect within about a minute and apply to every team, with no redeploy. That is the real payoff. When a new rule or a new approved model arrives, it reaches every service by editing one place.

For people, single sign-on and SCIM provisioning bring accounts in and remove them when someone leaves. See the [SSO and SCIM guide](/guides/sso-and-scim).

## A worked scenario

A team builds a support-reply helper.

1. A platform admin creates a team in the console and gives it a monthly budget.
2. A developer creates a key tied to that team, sets an expiry, and stores it in the service's secret store.
3. The service changes its base URL to the gateway and sends a label with its name, for example `{"app": "reply-helper"}`.
4. The first request returns with its cost on the response. The same request appears in the audit log with its policy decision.
5. In week two a reviewer asks where customer text can go. The answer is a page of the model registry and a data class rule, not an email thread.

At no point did the team write a retry loop, handle a provider key, or build a cost report.

## What to do now

- [ ] Pick one internal template (a starter repo or a docs page) and make "base URL plus team key" the first step in it.
- [ ] Create a team and a budget for every group that already uses AI.
- [ ] Move provider keys into the gateway and remove them from application config.
- [ ] Start the policy in log-only mode, review hits for a week, then enforce.
- [ ] Add a short label convention, such as `app` and `env`, to the template.
- [ ] Link new-hire onboarding to the key and team steps.

## Good to know

A golden path is a default, not a fence. The gateway can only protect traffic that passes through it, so the paved road works best when it is also the only road to the providers. Ask your network team to allow provider traffic only from the gateway, and the easy path becomes the only one.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

Needs Docker, no provider key. Console at http://localhost:5173. If it helps, star the repo, and if your platform needs something the path does not cover yet, open an issue.

## Sources

- [Quickstart](/getting-started/quickstart) and [OpenAI SDK and frameworks](/integrations/openai-sdk-and-frameworks): the base URL change and the optional headers.
- [API keys and provider keys](/api-reference/keys): show-once keys, expiry, permissions, team tie-in.
- [Policies and guardrails](/core-concepts/policies-and-guardrails) and [Request pipeline](/core-concepts/request-pipeline): what runs on every request.
- [Rate limiting and budgets](/core-concepts/rate-limiting-and-budgets): limits and how a refusal reads.
- [Python SDK](/integrations/python-sdk) and [TypeScript SDK](/integrations/typescript-sdk).
- On this blog: [why every company needs an LLM gateway](/blog/why-every-company-needs-an-llm-gateway), [know who spends what on AI](/blog/know-who-spends-what-on-ai).

These statements are based on the sources above and on OpenProxyAI's behavior as of 2026-10-15.
