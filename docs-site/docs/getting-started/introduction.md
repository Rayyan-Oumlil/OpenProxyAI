---
slug: /
title: Introduction
description: OpenProxyAI is the control plane for enterprise AI — a single gateway in front of every LLM provider, with policy enforcement, audit logging, and cost control.
---

# Introduction

OpenProxyAI is the control plane for enterprise AI — a single gateway that sits between your organization and every LLM provider (OpenAI, Anthropic, Azure, Mistral, Google, and more).

Instead of every team managing its own provider keys, rate limits, and logging, all traffic goes through one proxy that is OpenAI-API-compatible. Point your existing SDK at OpenProxyAI's `base_url` and nothing else in your application code changes.

## What it does

- **One API key** in front of every provider you use — rotate provider keys without touching client code.
- **Policy enforcement** on every request — PII redaction, secrets scanning, topic guarding, prompt-injection detection, and model allowlists, enforced before the call ever leaves your network.
- **Full audit trail** — every request, response, and policy decision is logged and replay-able.
- **Cost attribution** — every request is tagged by team and tracked against a daily budget.
- **A 3-tier cache** — in-memory, Redis, and semantic (embedding-similarity) — that cuts duplicate provider calls.

## How a request flows

Every request passes through the same six-stage pipeline, in order:

1. **Auth** — verify the bearer API key
2. **Rate limit** — requests/min, tokens/min, and dollars/day, enforced together
3. **Policy** — PII redaction, guardrails, allowlists
4. **Cache** — check L1 → L2 → L3 before calling a provider
5. **Route** — weighted selection across your configured provider keys
6. **Log** — written asynchronously; never blocks the response

See [Request Pipeline](/core-concepts/request-pipeline) for the full detail on each stage.

## Where to go next

- **[Quickstart](/getting-started/quickstart)** — install, get a key, send your first request
- **[Authentication](/getting-started/authentication)** — API keys, headers, and permissions
- **[Policies & Guardrails](/core-concepts/policies-and-guardrails)** — configure what gets blocked, redacted, or logged
- **[Provider Routing](/core-concepts/provider-routing)** — add providers, set weights, configure failover
- **[API Reference](/api-reference/overview)** — full endpoint reference
