---
title: Frequently asked questions
description: Short, verified answers about what OpenProxyAI is, how it handles security, deployment, providers, cost, compliance and licensing.
---

# Frequently asked questions

Short answers to the questions teams ask most before and after adopting OpenProxyAI. Each answer links to the page with the detail. For definitions of terms, see the [glossary](/resources/glossary).

## Basics

### What is OpenProxyAI?

OpenProxyAI is a self-hosted gateway that sits between your applications and LLM providers. Applications send OpenAI-style requests to it, and it applies authentication, rate limits, budgets, policy, caching and routing before calling a provider, then logs the result. See the [introduction](/).

### What problem does a gateway solve that calling providers directly does not?

Calling providers directly spreads keys, limits and logging across every application. A gateway moves them to one place, so you can see who spends what, block risky requests and swap models without changing code. The [request pipeline](/core-concepts/request-pipeline) shows each stage.

### Do I need to change my application code?

Usually only the base URL and the API key. OpenProxyAI serves OpenAI-compatible endpoints, so existing OpenAI SDKs and frameworks work, and Python and TypeScript SDKs are also available. Model names take the form `provider/model`, for example `openai/gpt-4o`. See [OpenAI SDK and frameworks](/integrations/openai-sdk-and-frameworks).

### How do I try it?

Start the stack, create an API key and send one chat request. The [quickstart](/getting-started/quickstart) walks through it end to end.

### How do I trace one request?

Every response carries an `x-openproxyai-request-id` header. Store it with the answer you showed, send it with feedback, and match it to `request_id` on the log entry. See [audit logging](/security/audit-logging).

## Security and privacy

### Does OpenProxyAI store my prompts and answers?

Not by default. The request log keeps metadata such as model, tokens, cost, status and the policy decision. Prompts and answers are kept only if an admin turns on payload capture, which samples a redacted share of traffic. See [payload capture](/guides/payload-capture).

### Where does my data go?

To the provider you route it to, and nowhere else the gateway controls. OpenProxyAI runs in your own infrastructure against your own Postgres and Redis, so the subprocessors are the ones you choose. Optional services such as analytics sidecars are off by default, and air-gapped mode disables the rest. See the [trust center](/security/trust-center).

### How are organizations kept apart?

Isolation is enforced in the database with PostgreSQL row-level security, not only in application queries. See [row-level security](/security/row-level-security).

### What happens when a request contains personal data?

With the policy in `enforce` mode, a request containing PII is blocked with HTTP 446; it is not rewritten and forwarded. In `log_only` mode the hit is recorded and the request goes through. Responses can be withheld or have PII replaced. See [policies and guardrails](/core-concepts/policies-and-guardrails).

### Does it stop prompt injection?

It reduces the risk but cannot remove it. Requests are scored by a classifier (or regular expressions when the model is not installed), and the MCP gateway scans tool descriptions and results and can stop side-effect tools from running after untrusted output. If the classifier is unavailable the request is allowed. See [policies and guardrails](/core-concepts/policies-and-guardrails) and the [MCP gateway](/guides/mcp-gateway).

### What if an application key leaks?

Create a new key, switch the application to it and revoke the old one with `DELETE /api/v1/api-keys/{key_id}`. Provider keys never leave the gateway, so they do not need rotating. See [authentication](/getting-started/authentication).

## Deployment

### How do I deploy it?

Run it with Docker Compose on one host or with the Helm chart on Kubernetes. You need the API service, Postgres with the pgvector extension and Redis; ClickHouse and the admin console are optional. See [deployment](/guides/deployment).

### What must I configure before production?

At minimum `DATABASE_URL`, `REDIS_URL` and `SECRET_KEY`. With `APP_ENV=production` the default `SECRET_KEY` is rejected and the process refuses to start. Changing `SECRET_KEY` later affects stored encrypted secrets, so choose it carefully. See [deployment](/guides/deployment) and [environment flags](/getting-started/environment-flags).

### Can it run without internet access?

Yes. `AIRGAP_MODE=true` disables optional third-party call-outs, and you can point provider keys at internal endpoints. See [environment flags](/getting-started/environment-flags).

### Does it support single sign-on and automatic provisioning?

OpenID Connect sign-in for the admin console and SCIM 2.0 user provisioning (Okta, Microsoft Entra ID or any SCIM client) are supported on plans that include SSO. SAML is not supported. See [SSO and SCIM](/guides/sso-and-scim).

## Providers and models

### Which providers are supported?

The introduction lists OpenAI, Anthropic, Azure, Mistral and Google, among others. You add credentials as provider keys, and the model list reflects what your active keys can serve. See [provider routing](/core-concepts/provider-routing) and [keys](/api-reference/keys).

### Can I use local or self-hosted models?

Yes, an `openai`-type provider key can use a custom `api_base`, such as vLLM or Ollama's `/v1`. Pointing at a private or plain-HTTP endpoint needs the operator to set `ALLOW_INTERNAL_PROVIDER_ENDPOINTS=true`. See [environment flags](/getting-started/environment-flags).

### What happens when a provider is down?

If a provider key fails, the router tries other authorized keys, and a request can name a backup model with `x-openproxy-fallback-model`. If nothing authorized is left, the caller gets a clear error rather than an out-of-policy fallback. See [provider routing](/core-concepts/provider-routing).

### Which endpoints beyond chat completions are available?

Embeddings, model listing, rerank, images, audio, Responses, realtime, files and batches are documented. See [other endpoints](/api-reference/other-endpoints) and [realtime](/api-reference/realtime).

### Does streaming work?

Yes. Streaming responses pass through, and a streamed request is checked against the remaining budget before it starts. Streamed responses are not cached. See [chat completions](/api-reference/chat-completions).

## Cost and limits

### How do I cap spend?

Set daily dollar budgets for the organization and for users, and monthly budgets for teams. A request over a limit gets HTTP 429 with a `limit_type`, and a streamed request whose estimate exceeds the remaining budget gets 402. See [rate limiting and budgets](/core-concepts/rate-limiting-and-budgets).

### What are the default limits?

The deployment defaults are 60 requests per minute, 100,000 tokens per minute and 50 dollars per day for the organization, set by the operator in the environment. Team limits come from the policy. See [rate limiting and budgets](/core-concepts/rate-limiting-and-budgets).

### Can I get alerts before a budget runs out?

Yes. When daily spend reaches 80% of the organization budget, a `budget.alert` webhook is sent, at most once per day. See [webhooks](/guides/webhooks).

### Does caching save money?

Where traffic repeats, yes. Exact matches are served from memory or a shared cache, and a semantic tier can match reworded prompts, but it is approximate and off by default. Streaming and tool-using requests are not cached. See [caching](/core-concepts/caching).

## Compliance

### Is OpenProxyAI SOC 2, ISO 27001 or HIPAA certified?

No. The trust center states that OpenProxyAI does not currently hold those certifications. It provides controls and evidence, such as policy enforcement and audit logs, that you can use in your own audit. See the [trust center](/security/trust-center).

### What do the compliance templates do?

They fill in the guardrail fields of your organization policy for healthcare, finance or government settings. They are starting configurations, not certifications, and applying one does not make a deployment compliant. See [compliance templates](/security/compliance-templates).

### How long are logs kept, and can I export them?

The request log window follows the plan: 7 days on Community, 30 on Team, 90 on Business and 365 on Enterprise. Older rows are archived rather than erased and can be listed with `include_archived=true`. Logs can also be streamed to a SIEM. See [audit logging](/security/audit-logging) and [telemetry and SIEM](/guides/telemetry-and-siem).

### Can I keep EU data in the EU?

You set one data region per organization and tag provider keys and models with regions. The gateway then only routes to matching keys and models, including during failover. It cannot verify a tag with the provider, so tag honestly. See [data residency](/security/data-residency).

## Open source and licence

### What licence is it under?

Apache-2.0, as stated in the repository's licence file. See the post on [why the gateway is Apache-2.0](/blog/open-source-apache-2-for-a-gateway).

### How does it compare with other gateways?

The [compare hub](/resources/compare) links every comparison and evaluation guide, including a neutral buyer's checklist.
