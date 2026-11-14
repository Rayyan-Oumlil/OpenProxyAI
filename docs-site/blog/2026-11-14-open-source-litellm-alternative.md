---
slug: open-source-litellm-alternative
title: "Looking for an open-source LiteLLM alternative? Eight questions to ask"
tags: [product, architecture]
description: "LiteLLM is a widely used open-source proxy and SDK. If security, finance or compliance now has a say in AI usage, here are eight questions to ask any gateway, and how OpenProxyAI answers each."
---

LiteLLM is a widely used open-source proxy and SDK. It gives developers one OpenAI-style interface across many providers, and for a single team that is often all that is needed. So why do people search for an alternative? Usually because the audience changed. A security lead, a finance partner or an auditor joined the conversation, and the question moved from "can we call many models?" to "who may call which model, with what data, at what cost, and where is the evidence?" This guide gives you eight questions to ask any gateway, including ours.

{/* truncate */}

![Eight boxes listing the questions: policy before the call, budgets and limits, data-class routing, audit and retention, SSO and SCIM, admin console, tool governance, deployment and licence](/img/blog/open-source-litellm-alternative.svg)

## Why teams look beyond a proxy library

A proxy library solves a developer problem: one API, many providers. A gateway for an organization solves a different set of problems.

- **Security** wants rules applied to every prompt, not only in the applications that remembered to add them.
- **Finance** wants spend by team, with limits that stop overspend instead of reporting it afterwards.
- **Compliance** wants a record of who asked what, what the system decided and why, in a form an auditor can read.
- **IT** wants access tied to the identity provider, so leavers lose access the day they leave.

None of this is a criticism of a library. It is a sign that the job has grown. For a side-by-side with one specific project, see [OpenProxyAI vs. LiteLLM](/blog/openproxyai-vs-litellm). For a longer test-driven list, see the [AI gateway buyer's checklist](/blog/ai-gateway-buyers-checklist).

## Eight questions to ask any gateway

### 1. Is policy enforced before the provider call?

A guardrail that runs after the provider has already seen the prompt is a log, not a control. Ask where in the request path the checks run and what happens to a request that fails them. Then try it.

**OpenProxyAI:** every request is checked against your organization's policy before any provider is called: model allowlist, blocked keywords, personal data detection and prompt-injection detection, with optional response guardrails. You can start in log-only mode and switch to enforcing when the log looks right. A blocked request returns HTTP 446 with one plain sentence for the end user. See [Policies and guardrails](/core-concepts/policies-and-guardrails).

### 2. Can I set budgets and rate limits per team?

An organization-wide cap protects the invoice but not the teams from each other. Ask whether limits exist at the team and user level, and whether they are checked before the call is made.

**OpenProxyAI:** rate limits and dollar budgets are set per organization, team and user, and checked up front. Over-limit calls return 429, and a streamed request that would not fit the remaining daily budget returns 402. See [Rate limiting and budgets](/core-concepts/rate-limiting-and-budgets) and [Give every team its own limits](/blog/give-every-team-its-own-limits).

### 3. Can I route by the sensitivity of the data?

Not every model should see every prompt. Ask whether you can say which models may receive which class of data, and whether the gateway enforces it, including when it falls back to another provider.

**OpenProxyAI:** a model registry records, for each model, the most sensitive data class it may receive, its regions and its retention. With routing set to enforce, a request is served only by a model the registry clears. If none qualifies, it is refused before any provider call. See [Provider routing](/core-concepts/provider-routing).

### 4. What is in the audit trail, and how long is it kept?

"We log everything" is not an answer. Ask what a record contains, whether admin changes are logged separately, how retention works and how you get the data out.

**OpenProxyAI:** the request log records the model, tokens, cost, status, policy decision and routing for every request, and prompts and answers are stored only if you turn on payload capture. A separate admin audit log records administrative changes. Retention follows your plan, and exports for a date range are available for an auditor. See [Audit logging](/security/audit-logging).

### 5. Does access follow my identity provider?

Shared keys and manual user lists do not survive a reorganization. Ask about single sign-on for the console and about automated provisioning and deprovisioning.

**OpenProxyAI:** the console supports OpenID Connect sign-in, and Okta or Microsoft Entra ID can provision and deactivate users through SCIM 2.0. These are available on plans that include SSO. See [Single sign-on and SCIM](/guides/sso-and-scim).

### 6. Can non-engineers operate it?

If every change needs a developer and a deploy, the people accountable for the outcome cannot act. Ask what an admin can do without writing code.

**OpenProxyAI:** the admin console covers teams, budgets, policies, the model registry, provider keys, MCP servers and the audit log. See [Admin console overview](/admin-console/overview).

### 7. Can I govern agent tools, not only prompts?

Agents call tools through the Model Context Protocol (MCP). Ask who may call which tool, and what happens if a tool changes after approval.

**OpenProxyAI:** the MCP gateway applies allow and deny grants for a role, team, user or API key, and a client can only ask for less than it was granted. It can also pin tool definitions and flag a tool that changed. See [MCP gateway](/guides/mcp-gateway) and [MCP grants beat shared tokens](/blog/mcp-grants-beat-shared-tokens).

### 8. Where does it run, and under what licence?

A gateway sees every prompt. Ask whether it runs in your network, what you must trust outside it and what the licence lets you do.

**OpenProxyAI:** it is self-hosted and Apache-2.0. You run it with Docker Compose on one host or with the Helm chart on Kubernetes, so prompts stay in your environment. See [Deployment](/guides/deployment) and [Open source under Apache-2.0](/blog/open-source-apache-2-for-a-gateway).

## A quick comparison

The left column is a neutral question to put to any gateway. The right column is what we can show today.

| Ask any gateway | OpenProxyAI |
|---|---|
| Policy before the provider call? | Yes, with log-only mode first and a 446 refusal |
| Limits per team and user? | Yes, checked before the call |
| Data-class routing? | Model registry with enforce mode |
| Audit trail? | Request log and separate admin audit log, with exports |
| SSO and SCIM? | OpenID Connect and SCIM 2.0, on plans with SSO |
| Admin console? | Included |
| Tool governance? | MCP grants per role, team, user or key |
| Licence? | Apache-2.0, self-hosted |

Check the same rows against any other project's current documentation, including which features sit in a paid tier. Test, do not trust a table, ours included.

## Switching in three lines

If your applications already use an OpenAI-style client, moving them behind a gateway is a small change: the base URL, the API key and, if you like, the model name.

```python
client = OpenAI(
    base_url="https://gateway.your-company.com/v1",
    api_key=os.environ["OPENPROXY_KEY"],
)
```

Request and response shapes, streaming and framework integrations stay the same. Move one low-risk service first, then the rest one at a time. The full walkthrough is in [Migrate to a gateway in three lines](/blog/migrate-to-a-gateway-in-three-lines).

## What to do now

- Decide which of the eight are gates for you.
- Ask each candidate to demonstrate questions 1, 3 and 4 in a trial.
- Run policy in log-only mode on one service for a week.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

Needs Docker and no provider key. The console is at http://localhost:5173. Star the repo or open an issue with the ninth question you would add.

## FAQ

### Is OpenProxyAI open source?

Yes. It is released under Apache-2.0, the full source is public on GitHub, and you self-host it.

### Does it work with the OpenAI SDK and frameworks I already use?

Yes. It exposes an OpenAI-compatible endpoint, so clients and frameworks that accept a custom base URL work by changing the URL and key. Python and TypeScript SDKs are also available if you want typed cost and latency data. See [OpenAI SDK and frameworks](/integrations/openai-sdk-and-frameworks).

### Do I have to enforce policy on day one?

No. Policy can run in log-only mode so you see what it would block without blocking anything. Switch to enforcing when the results look right. See [Roll out guardrails without breaking teams](/blog/roll-out-guardrails-without-breaking-teams).

### Do the compliance templates make me compliant?

No. They are starting configurations for healthcare, finance and government use that you apply and adjust. They are not certifications. See [Compliance templates](/security/compliance-templates).

## Sources

- On this blog: [OpenProxyAI vs. LiteLLM](/blog/openproxyai-vs-litellm), [AI gateway buyer's checklist](/blog/ai-gateway-buyers-checklist), [Migrate to a gateway in three lines](/blog/migrate-to-a-gateway-in-three-lines).
- OpenProxyAI docs: [Quickstart](/getting-started/quickstart), [Request pipeline](/core-concepts/request-pipeline), [Policies and guardrails](/core-concepts/policies-and-guardrails), [Audit logging](/security/audit-logging), [Single sign-on and SCIM](/guides/sso-and-scim), [MCP gateway](/guides/mcp-gateway), [Deployment](/guides/deployment).

These statements are based on OpenProxyAI's behavior at the post date.
