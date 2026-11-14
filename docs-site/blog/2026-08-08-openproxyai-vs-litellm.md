---
slug: openproxyai-vs-litellm
title: "OpenProxyAI vs. LiteLLM: a library or a governed gateway"
tags: [product, architecture]
description: "LiteLLM and OpenProxyAI are both self-hosted and OpenAI-compatible. They differ in what ships by default: policy checks, compliance templates, an admin console and an audit trail."
---

LiteLLM comes up in almost every conversation about self-hosted LLM gateways, and for good reason. It is a widely used open-source proxy and Python SDK with one OpenAI-compatible interface across 100+ providers. The question this post answers is what you get when the approval chain for AI usage includes a security or compliance team.

{/* truncate */}

## What LiteLLM is

LiteLLM is an open-source proxy and Python SDK that gives you a single OpenAI-compatible interface across 100+ providers, with routing, spend tracking and caching. You self-host it and configure it with a `proxy_config.yaml`. It has an Admin UI for keys, budgets and spend, and an open-source guardrail framework that includes custom guardrails and Presidio PII masking. If all you need is one API, many providers and budget tracking, it is a reasonable place to stop.

## What OpenProxyAI adds by default

OpenProxyAI is built for teams where security, finance and platform each have a say. These capabilities are part of the default product:

- **Policy enforcement as a core stage.** Every request is checked against an organization policy: a model allowlist, blocked keywords, personal data detection and prompt-injection detection, plus optional response guardrails. Start in log-only mode, then enforce. See [Policies and guardrails](/core-concepts/policies-and-guardrails).
- **Compliance starting points.** Healthcare, Finance and Government policy templates you apply and then adjust. They are configurations, not certifications. See [Compliance templates](/security/compliance-templates).
- **A full admin console.** Teams, budgets, policies, model registry, MCP servers and the audit log, as the default way to operate the gateway.
- **Data-class routing.** Say which models may see which data, and let the gateway enforce it.
- **An audit trail built to be handed over.** Append-only request logs with retention by plan, and exports. See [Audit logging](/security/audit-logging).
- **SSO and SCIM** for identity-provider based access, and an MCP gateway with per-user tool grants.

For comparison, LiteLLM documents several related features (tag-based budgets, spend reports, team-based logging, SSO beyond 5 users, SCIM, audit logs, secret detection and per-key guardrails) under its Enterprise license. Check [LiteLLM's enterprise docs](https://docs.litellm.ai/docs/enterprise) for the current split.

## How to choose

| If your situation is | Look at |
|---|---|
| A single team that needs multi-provider routing and cost tracking | LiteLLM's simplicity is a real advantage |
| A security, compliance or finance team in the approval chain | OpenProxyAI: policy checks, templates, audit trail and the console are already there |
| You want to run your gateway in your own network under Apache-2.0 | Both run self-hosted; OpenProxyAI is Apache-2.0 |

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

Needs Docker and no provider key. The console is at http://localhost:5173. Star the repo or open an issue if something is missing for your case.

## Sources

- [LiteLLM enterprise features](https://docs.litellm.ai/docs/enterprise), for the open-source versus Enterprise split.
- [Policies and guardrails](/core-concepts/policies-and-guardrails), [Compliance templates](/security/compliance-templates), [Audit logging](/security/audit-logging).

These statements are based on LiteLLM's public documentation and on OpenProxyAI's behavior at the post date.
