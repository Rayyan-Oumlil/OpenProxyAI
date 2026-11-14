---
slug: make-the-gateway-the-only-door
title: "Make the gateway the only door to your AI providers"
tags: [security, architecture]
description: "A gateway only governs the traffic that goes through it. Here is how to close the side doors with network egress rules, and how OpenProxyAI keeps the front door worth using."
---

A gateway can only enforce policy on requests it sees. If a team can still reach a model provider directly from their service, from a laptop script or from a notebook, then budgets, guardrails and audit logs cover only the traffic that behaves. The fix is not another policy. It is making the gateway the only route that works. This post covers the network rules that do that, the gateway-side controls that make the front door easy to use, and a short way to check that no side door is left.

{/* truncate */}

![Applications reach the gateway, which is the only path allowed out to the model providers. Direct paths from applications to providers are blocked at the network edge.](/img/blog/make-the-gateway-the-only-door.svg)

## The problem: two doors

Most teams start with a gateway as a convenience. Apps are asked to point their SDK at it. Nothing forces them. A developer with a provider key in a notebook, a vendor tool with its own integration, or an old service nobody migrated can all call a provider directly. Those calls skip your policy, your spend limits and your logs.

Two facts make this worse. Provider keys are easy to copy, so one key in a chat message is enough to open a side door. And a missing log line is invisible: you do not see the request that bypassed you. See [AI keys are leaking](/blog/ai-keys-are-leaking-keep-them-out-of-your-apps) for how keys escape, and [shadow AI needs a governed front door](/blog/shadow-ai-needs-a-governed-front-door) for the people side of the problem.

## Step 1: close the network paths

Do this in your own network. The gateway cannot block a connection it never receives.

1. **Deny by default for workloads.** Application subnets and clusters should have no general route to the internet. Allow only what each workload needs.
2. **Allow only the gateway to reach the providers.** Put the gateway in its own network segment or namespace. Its outbound rules list the provider hostnames you actually use and nothing else.
3. **Let applications reach the gateway only.** Apps get a route to the gateway address and to their own dependencies. No route to the provider hostnames.
4. **Filter by name, not just address.** Provider addresses change. Use a firewall or an egress proxy that matches on the destination hostname.
5. **Cover the edges.** Developer laptops on the corporate network, CI runners, build agents and managed notebook platforms need the same rule, or they become the new side door.

A few traps to plan for. Provider SDKs sometimes talk to more than one hostname, so test in a staging environment before you turn on blocking. Some vendor SaaS tools call providers from their own cloud; you cannot filter that with your network, so cover it in contracts and with the vendor questionnaire. And internal model servers (for example, self-hosted open models) can be reached from the gateway too, which keeps those calls governed as well.
## Step 2: make the front door the easy path

Network rules alone create friction, and friction creates shadow IT. The gateway should be the easier choice. OpenProxyAI helps in four ways:

| Need | What the gateway does |
|---|---|
| Keep provider keys out of applications | Provider keys are stored in the gateway, encrypted. Applications hold only a gateway key, which can be limited and revoked on its own. |
| Switch with almost no code | One OpenAI-compatible endpoint. Most apps change a base URL and a key. |
| Decide which models are usable | An organization model allowlist. A request for a model that is not on it is refused with status 446 and a reason code. |
| Stop runaway use | Budgets and rate limits per organization, team and user, with usage visible in the console. |

The key point is the first row. When the only place a provider key exists is the gateway, an application cannot call the provider directly even if the network allows it. Combine that with the network rules and you have two independent locks.

For tool access the same idea holds. The MCP gateway gives agents one endpoint for all tool servers, and the credentials for those servers stay in the gateway. Agents do not carry them. See [MCP grants beat shared tokens](/blog/mcp-grants-beat-shared-tokens).

## Step 3: prove it

Trust, then verify. Three checks:

- **Probe from an application host.** Try to open a connection to a provider hostname. It should fail. Try the gateway. It should succeed.
- **Compare the two logs.** Your egress or firewall logs show destinations. The gateway request log shows requests. If a workload appears in the first and not in the second, you have a bypass to chase.
- **Watch for the unknown.** New applications should show up in the gateway logs by key name and team. A key that nobody can explain is a signal to look at.

## What a leaked key looks like in this design

If a gateway key leaks, the damage is bounded by that key's permissions, team and budget, and an admin can revoke it so the next call is refused. If a provider key leaks, it was only ever in the gateway, so rotate it there without touching any application. Both stories are short. See [a leaked key should be a nuisance](/blog/a-leaked-key-should-be-a-nuisance).

## What to do now

1. List every system that calls a model provider today. Include notebooks, CI and vendor tools.
2. Move each onto a gateway key. Remove provider keys from application configuration.
3. Turn on deny-by-default egress for application networks, starting in staging.
4. Allow outbound access to provider hostnames only from the gateway.
5. Set the model allowlist, budgets and rate limits so the front door is safe and predictable.
6. Add a monthly check that compares egress logs to gateway logs.

## Good to know

Network egress rules are yours to set. OpenProxyAI governs everything that reaches it, and it works best when the network makes it the only route. Plan for a short rollout period where you watch the logs before you start blocking.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

Needs Docker, no provider key. Console at http://localhost:5173. Star the repo or open an issue if you want a network pattern covered.

## Sources

- OpenProxyAI docs: [Policies and guardrails](/core-concepts/policies-and-guardrails), [Authentication](/getting-started/authentication), [API keys and provider keys](/api-reference/keys), [MCP gateway](/guides/mcp-gateway), [Deployment](/guides/deployment), [Audit logging](/security/audit-logging).
- On this blog: [Deploy in your VPC in minutes](/blog/deploy-in-your-vpc-in-minutes), [VPC-first architecture](/blog/vpc-first-architecture), [Why every company needs an LLM gateway](/blog/why-every-company-needs-an-llm-gateway).

These statements are based on OpenProxyAI's behavior at the post date.
