---
slug: deploy-in-your-vpc-in-minutes
title: "Run an LLM gateway inside your own network, starting in minutes"
tags: [architecture, product]
description: "Self-hosting a gateway should not need a vendor call. See the demo stack on your laptop, what stays inside your network, and the path from demo to a production deployment."
---

Security teams ask one question about AI tooling before any other: where does our data go? If the answer is "through a vendor's cloud", the review gets long. OpenProxyAI answers differently. It is self-hosted, so the gateway, its database, its cache, its logs and its console all run on infrastructure you control. You can see all of that working on your own machine in a few commands, with no provider key and no sign-up.

{/* truncate */}

![Inside your network: applications, the OpenProxyAI gateway, its console, its database and cache, and the audit log. A single outbound line leaves the network to the model providers you configured.](/img/blog/deploy-in-your-vpc-in-minutes.svg)

## What stays inside your network

When you run OpenProxyAI, these are all yours:

- **The gateway** that receives every model call and applies policy, budgets, caching and routing.
- **The database and cache** it uses, which hold your organization, users, keys, settings and request records.
- **The audit log**, which lives in your database, not in a service we operate.
- **The admin console**, served from your own deployment.
- **Provider keys**, stored encrypted in your database, or read from your own secrets manager so the gateway keeps no copy. See [Provider keys from Vault](/guides/secrets-from-vault).

The one thing that leaves is the outbound call to the model provider you chose, which is the same call your application would have made directly. There is no OpenProxyAI-run service in the path. Because you operate it, you also choose which release to run and when to update. See the [Trust center](/security/trust-center) for how data is handled.

Some optional integrations call out to other services, such as observability tools or hosted spend reports. They are off unless you turn them on, and an air-gapped mode switches off everything that is not needed for the core request path.

## See it in five minutes

The repository ships a demo stack. It starts its own database and cache, a stand-in model server that speaks the OpenAI API, the gateway and the console, then sends a batch of sample requests so the console opens with data.

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

You need Docker. You do not need a provider key, because the stand-in server answers instead of a real model, so nothing is billed. The first run builds images, which takes longer than later runs. When it settles:

| What | Where |
|---|---|
| Admin console | http://localhost:5173 |
| Gateway API | http://localhost:8000 |
| Demo sign-in | Printed in the gateway's startup output |

The sample traffic includes an allowed request, a repeated request answered from the cache, requests refused by policy (a blocked keyword and a personal-data check), and a second key with a tiny daily budget that gets stopped. Click through the request log and each row tells you what happened and why. That is the fastest way to feel the product.

The demo uses public sign-in values and settings meant for a laptop. Never deploy it as is. To start over, take the stack down with its volumes and bring it back up.

## From demo to your network

The demo is the same software you run in production, with demo settings. The path to a real deployment:

1. **Pick a target.** A single host with Docker Compose works for a team or a pilot. The Helm chart in the repository targets Kubernetes, including air-gapped clusters.
2. **Bring your own database and cache**, or use the bundled ones for a pilot. Keep them inside your private network.
3. **Set your own secrets** for the gateway and the database. Use your secrets manager rather than files.
4. **Register your organization and create gateway keys** for each application. See [Quickstart](/getting-started/quickstart).
5. **Add provider keys.** Tag each with its region and the highest data class it may receive.
6. **Apply a policy**, in log-only mode first, then enforce. See [Policies and guardrails](/core-concepts/policies-and-guardrails).
7. **Point one application at the gateway** by changing its base URL, then move the rest.

Data isolation between organizations is enforced in the database itself, which matters if several teams share one deployment. See [Row-level security](/security/row-level-security). For region rules, see [Data residency](/guides/data-residency).

## What to do now

- [ ] Run the demo and open the request log.
- [ ] Decide where the gateway will run and who owns it.
- [ ] Decide where provider keys will live.
- [ ] Choose your first application to move.
- [ ] Share the console with a security reviewer and ask what they would want to see.

## Good to know

Self-hosting means you own the uptime, scaling and patching of the service. That is the price of keeping everything in your network, and a fair trade for teams whose prompts carry regulated data. A hosted option is available on the Team and Business plans for teams who would rather not run it.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

Needs Docker, no provider key. Console at http://localhost:5173. If it works for you, star the repo, and if it does not, open an issue.

## Sources

- Internal: [Quickstart](/getting-started/quickstart), [Trust center](/security/trust-center), [Provider keys from Vault](/guides/secrets-from-vault), [Data residency](/guides/data-residency), [Row-level security](/security/row-level-security), [Environment flags](/getting-started/environment-flags).

These statements are based on OpenProxyAI's behavior at the date of this post.
