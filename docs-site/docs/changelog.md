---
title: Changelog
description: What's shipped, by phase.
sidebar_position: 100
---

# Changelog

A summary of what's shipped, grouped by build phase. This tracks major capability milestones, not every individual PR.

## Phase 7 — 2026-03-19

- **Semantic caching** — 3-tier cache (L1 in-memory, L2 Redis, L3 pgvector semantic), per-request override header, dashboard metrics
- **Prompt playground** — side-by-side model comparison (TTFT, latency, tokens, cost), prompt template CRUD with versioning
- **`GET /v1/models`** — OpenAI-compatible model list built from your org's configured provider keys
- **Data residency (Tier 1)** — region field on provider keys, `data_region` on organizations, routing filtered by region
- **Compliance templates** — Healthcare/HIPAA, Finance/PCI, Government/FedRAMP-aligned policy presets with merge semantics

## Phase 3–6

- Observability: Langfuse tracing, Prometheus metrics, ClickHouse analytics dual-write, outbound webhooks
- Security hardening: prompt-injection detection, response guardrails, PII redaction, SSRF protection
- Billing: Stripe checkout, customer portal, webhook handling, plan-based feature gating
- Public deployment: Docker Compose for local dev, Helm chart for Kubernetes, GitHub Actions CI/CD

## Phase 1–2

- Core proxy: auth, rate limiting, policy hooks, provider routing, async audit logging
- Admin console, invite system, plan enforcement
- OIDC/SSO, immutable audit log
- Python and TypeScript SDKs

---

:::info Granular release notes coming soon
This page currently tracks phase-level milestones. A per-version changelog with dates and PR links is planned once release cadence stabilizes.
:::
