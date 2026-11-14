---
title: "Glossary: LLM gateway terms"
description: Plain-language definitions of the terms used around LLM gateways, each with how OpenProxyAI handles it and where to read more.
---

# Glossary: LLM gateway terms

This page defines the terms you meet when you put a gateway between your applications and large language model (LLM) providers. Each entry gives a general definition, then one sentence on how OpenProxyAI handles it. Where a term has a status code, header or setting, the name is the one the product uses.

### AI gateway

An AI gateway is a service that sits between applications and AI model providers and applies shared controls to every call: authentication, limits, policy, logging and routing. It is the AI-specific cousin of an API gateway, aware of tokens, prompts and models. OpenProxyAI is a self-hosted AI gateway; see the [introduction](/).

### Air-gapped mode

Air-gapped mode is a deployment setting that stops the gateway from calling any third-party service it does not strictly need. It suits networks with no outbound internet access. In OpenProxyAI, `AIRGAP_MODE=true` turns off optional call-outs and the semantic cache's embedding calls; see [environment flags](/getting-started/environment-flags).

### API key

An API key is a secret string that identifies the caller of an API and is sent with each request. OpenProxyAI keys start with `opai_`, are shown in full once, and carry permissions such as `proxy:llm`; only a prefix and a hash are stored. See [authentication](/getting-started/authentication).

### Audit log

An audit log is a tamper-resistant record of what happened and who did it. OpenProxyAI keeps two append-only records: a request log (one row per request, metadata only by default) and an admin audit log of configuration changes. See [audit logging](/security/audit-logging).

### Batch API

A batch API runs many requests as one asynchronous job, usually at lower priority or cost. OpenProxyAI accepts a JSONL file at `/v1/files` and a job at `/v1/batches`, and runs each line through the same policy, routing, metering and audit path as a live request, with a `max_cost_usd` cap. See [files and batches](/api-reference/batches).

### Budget

A budget is a spending ceiling for a period. OpenProxyAI enforces a daily dollar budget for the organization, a daily budget per user and a monthly budget per team, and answers with HTTP 429 and a `limit_type` when one is reached. See [rate limiting and budgets](/core-concepts/rate-limiting-and-budgets).

### Caching (exact and semantic)

Caching stores a model's answer so a repeated request is served without calling the provider. An exact cache matches identical requests; a semantic cache matches differently worded prompts whose meaning is close, which is approximate by nature. OpenProxyAI has an in-memory and a shared exact tier plus a semantic tier, all off until the operator enables them, and the `x-openproxy-cache` header bypasses them per request. See [caching](/core-concepts/caching).

### Compliance template

A compliance template is a preset of controls aimed at a regulatory framework. In OpenProxyAI, `healthcare_hipaa`, `finance_pci` and `government_fedramp` fill in the guardrail fields of the organization policy; they are configurations, not certifications. See [compliance templates](/security/compliance-templates).

### Data class

A data class is a sensitivity label attached to data that decides where it may go. OpenProxyAI uses `public`, `internal`, `confidential` and `secret`; a request can raise its class with the `x-openproxy-data-class` header but never lower it, and each registered model has a maximum class it may receive. See [policies and guardrails](/core-concepts/policies-and-guardrails).

### Data residency

Data residency is the requirement that data is processed in a particular geographic region. OpenProxyAI gives each organization one region (`us`, `eu` or `ap`), tags provider keys and models with regions, and filters routing and failover to match. See [data residency](/security/data-residency).

### Enforcement mode

Enforcement mode is the switch that decides whether a rule only reports or actually blocks. The OpenProxyAI organization policy has `enforcement_mode` set to `off`, `log_only` (record the hit, let the request through) or `enforce` (refuse it). See [policies and guardrails](/core-concepts/policies-and-guardrails).

### Eval

An eval is a repeatable test that scores a model or prompt against a set of examples. OpenProxyAI lets admins build datasets from captured traffic, score them with exact-match, regular-expression or LLM-judge evaluators, and run them with a cost cap. See [evaluating changes](/admin-console/evaluating-changes).

### Failover

Failover is switching to a backup when the primary provider or key fails or is rate limited. In OpenProxyAI, other authorized provider keys are tried, and a caller can name a backup model with `x-openproxy-fallback-model` and cap attempts with `x-openproxy-retries`; fallbacks stay inside the authorized region and model set. See [provider routing](/core-concepts/provider-routing).

### Guardrail

A guardrail is a check that limits what goes into or comes out of a model. OpenProxyAI's policy has a model allowlist, blocked keywords, PII detection and prompt-injection detection on requests, plus keyword and PII checks on responses. See [policies and guardrails](/core-concepts/policies-and-guardrails).

### Label

A label is a key-value tag attached to a request for later grouping. OpenProxyAI accepts up to 10 labels in the `x-openproxy-labels` header as a JSON object, records them on the request log and lets you filter by them. See [chat completions](/api-reference/chat-completions).

### LLM gateway

An LLM gateway is a gateway specialized for large language model traffic. It exposes one endpoint for many providers and adds authentication, cost control, policy and logging in one place. OpenProxyAI is one; the [request pipeline](/core-concepts/request-pipeline) shows the stages each call passes through.

### LLM proxy

An LLM proxy forwards model requests on behalf of an application, and the term is often used interchangeably with LLM gateway. A bare proxy may only forward and translate, while a gateway also enforces policy and records usage. OpenProxyAI is an OpenAI-compatible proxy that adds those controls; see the [introduction](/).

### MCP

The Model Context Protocol (MCP) is an open protocol that lets AI agents discover and call tools on external servers. OpenProxyAI speaks the MCP Streamable HTTP transport at `/v1/mcp`. See the [MCP gateway guide](/guides/mcp-gateway).

### MCP gateway

An MCP gateway puts many MCP tool servers behind one endpoint and one credential, and applies policy and logging to each tool call. OpenProxyAI namespaces tools as `<server>__<tool>`, checks policy on every call and writes an audit row per call. See the [MCP gateway guide](/guides/mcp-gateway).

### Model registry

A model registry is the approved list of models an organization may use, with limits on each. In OpenProxyAI each entry has regions and a maximum data class, and when routing is set to `enforce` a request can only use a registered model authorized for it. See [data residency](/security/data-residency) and [managing your organization](/admin-console/managing-your-organization).

### OpenAI-compatible API

An OpenAI-compatible API accepts the same request and response shapes as OpenAI's API, so existing SDKs work by changing the base URL. OpenProxyAI serves `/v1/chat/completions`, `/v1/embeddings` and `/v1/models` this way; model names take the form `provider/model`. See [OpenAI SDK and frameworks](/integrations/openai-sdk-and-frameworks).

### Organization policy

The organization policy is the single set of rules applied to all of an organization's traffic. OpenProxyAI has exactly one per organization, with an `enforcement_mode`; there are no named policies to pick per request. See [policies and guardrails](/core-concepts/policies-and-guardrails).

### PII

Personally identifiable information (PII) is data that identifies a person, such as an email address, a national ID number or a card number. OpenProxyAI's built-in detector finds email addresses, US Social Security numbers and checksum-valid card numbers; in `enforce` mode a request containing PII is blocked, not redacted. See [policies and guardrails](/core-concepts/policies-and-guardrails).

### Policy block (446)

A policy block is a refusal caused by a rule rather than by an error or a limit. OpenProxyAI returns HTTP 446 with a reason code and a plain-language explanation, and the same code is used for blocked tool calls. See [errors and status codes](/api-reference/errors-and-status-codes).

### Policy plugin

A policy plugin is a custom check added to the policy engine. OpenProxyAI organizations can upload their own checks and enable or disable them; each change is written to the admin audit log. See [policy plugins](/guides/policy-plugins).

### Prompt injection

Prompt injection is an attack that hides instructions in input so the model follows the attacker instead of the user. OpenProxyAI scores requests with a classifier (or regular expressions when it is not installed) and scans MCP tool descriptions and results; detection reduces the risk but does not remove it. See [policies and guardrails](/core-concepts/policies-and-guardrails).

### Provider key

A provider key is the credential a gateway holds for an upstream model provider such as OpenAI or Anthropic. In OpenProxyAI you can register several per provider with weights and a region tag, and rotate them without touching applications. See [keys](/api-reference/keys).

### Rate limit

A rate limit caps how many requests or tokens are allowed per unit of time. OpenProxyAI limits requests and tokens per minute for the organization and per team, counts them in fixed windows, and answers 429 with `Retry-After`. See [rate limiting and budgets](/core-concepts/rate-limiting-and-budgets).

### Request ID

A request ID is a unique identifier for one call, used to trace it later. OpenProxyAI returns it in the `x-openproxyai-request-id` response header, and it is the id you send with feedback. See [audit logging](/security/audit-logging).

### Retention

Retention is how long records are kept before they are deleted or archived. In OpenProxyAI the request log window comes from the plan (7, 30, 90 or 365 days), after which rows are archived, and compliance templates record a longer target without changing that window. See [audit logging](/security/audit-logging).

### Row-level security

Row-level security (RLS) is a database feature that restricts which rows a query can see, enforced by the database itself. OpenProxyAI uses PostgreSQL row-level security so one organization's data is isolated below the application layer. See [row-level security](/security/row-level-security).

### SCIM

SCIM (System for Cross-domain Identity Management) is a standard for an identity provider to create, update and deactivate users in other systems automatically. OpenProxyAI supports SCIM 2.0 users; new users are viewers, roles are never set by provisioning, and groups are not supported. See [SSO and SCIM](/guides/sso-and-scim).

### Shadow AI

Shadow AI is the use of AI services by staff outside approved channels, so security and finance cannot see it. Routing all model calls through one governed endpoint gives you the usage record that is otherwise missing; see the [blog post on shadow AI](/blog/shadow-ai-needs-a-governed-front-door).

### Showback

Showback reports spend by team or project without billing it back. OpenProxyAI attributes requests to teams and labels, and the analytics views report cost by model, team, key and user. See [rate limiting and budgets](/core-concepts/rate-limiting-and-budgets).

### SSO

Single sign-on (SSO) lets people sign in through the company's identity provider. OpenProxyAI supports OpenID Connect for the admin console on plans that include SSO; SAML is not supported. See [SSO and SCIM](/guides/sso-and-scim).

### Streaming

Streaming sends a model's answer in pieces as it is generated, usually as server-sent events. OpenProxyAI streams through, does not cache streamed responses, and checks a streamed request's estimated cost up front (HTTP 402 if it exceeds what is left). See [chat completions](/api-reference/chat-completions).

### Team

A team is a group of users whose spend and limits are tracked together. In OpenProxyAI a request counts toward a team when its key is tied to the team or it carries `x-openproxy-team-id`, and a team can have per-minute limits and a monthly budget. See [rate limiting and budgets](/core-concepts/rate-limiting-and-budgets).

### Tool grant

A tool grant is a rule that allows or denies a tool to a role, team, user or key. In OpenProxyAI a matching `deny` always wins, and if any `allow` applies to the caller they may use only tools it matches. See the [MCP gateway guide](/guides/mcp-gateway).

### Tool pinning

Tool pinning stores a fingerprint of each tool's definition so a server cannot change it unnoticed. OpenProxyAI's `pin_mode` is `off`, `warn` (the default) or `enforce`, and changed tools are marked `drifted`. See the [MCP gateway guide](/guides/mcp-gateway).

### Trust rule

A trust rule marks how far a tool's output can be trusted. In OpenProxyAI a tool can be `trusted_output` or a `sink` (a tool with side effects); a sink refuses to run in a session that has seen untrusted results. See the [MCP gateway guide](/guides/mcp-gateway).

### Virtual key

A virtual key is a gateway-issued key that applications use in place of the real provider credentials. OpenProxyAI's `opai_` API keys play this role, so a leaked application key can be revoked without rotating any provider key. See [keys](/api-reference/keys).

### Webhook

A webhook is an HTTP callback sent when an event occurs. OpenProxyAI sends signed `policy.violation` and `budget.alert` events to one HTTPS URL per organization, with a delivery log and retries. See [webhooks](/guides/webhooks).

### Zero data retention

Zero data retention (ZDR) means a provider or service does not keep prompts and answers after processing them. OpenProxyAI does not change what a provider keeps; it stores metadata only by default, and prompts are kept only if an admin turns on payload capture. See [payload capture](/guides/payload-capture).
