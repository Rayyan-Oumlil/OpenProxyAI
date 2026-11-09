---
title: Changelog
description: What's shipped, by phase.
sidebar_position: 100
---

# Changelog

A summary of what's shipped, grouped by build phase. This tracks major capability milestones, not every individual PR.

## Unreleased — November 2026

- **Breaking: policy blocks return HTTP 446, not 403.** Requests blocked by policy (PII, keywords, model allowlist) now use the same status as response guardrails. 403 now means only a real authorization failure. The Python and TypeScript SDKs raise `PolicyViolationError` on 446 and still accept a 403 from an older gateway. Raw HTTP clients that check for 403 on blocks must check for 446. Existing log rows keep their old status.
- **Custom provider endpoints** — an `openai` provider key can set `api_base` (any OpenAI-compatible server such as vLLM or Ollama's `/v1`) and a `max_data_class`. Every connection goes through a guard: no redirects are followed, the destination is validated per request and the connection is pinned to it, and TLS is verified against the hostname. External endpoints must be https and public; private or plain-http endpoints need the operator setting `ALLOW_INTERNAL_PROVIDER_ENDPOINTS`.
- **Policy preview** — `POST /api/v1/policy/preview` shows what would happen to a request (class, policy verdict, which model would serve it and why others were ruled out) without sending it: no provider call, no audit row, no budget use. Shows what enforcement would do even while routing is off.
- **Classification-aware routing** — set `routing_mode` to `log_only` to see which registry models would be authorized for each request, then `enforce` to make it binding: a model serves a request only if the registry clears it for the request's data class, and only through its registry key. Requests nothing can serve get HTTP 446. `model: "cap:NAME"` routes chat requests by capability. Applies to chat completions and embeddings.
- **PII detection hardened** (blocking, redaction and classification share one detector): text is normalized before it is read, so fullwidth digits, `＠` and zero-width characters no longer hide PII; SSNs with spaces or dots are found; a 13-19 digit number is only a payment card if it passes the Luhn checksum, and an SSN must be a number that could be issued, so order numbers and version strings stop triggering blocks.
- **Data classification** — each request is classified `public` < `internal` < `confidential` < `secret` from the org default, an `x-openproxy-data-class` header (raise only) and detected PII; returned as `X-OpenProxyAI-Data-Class` and recorded on the request trace. Informational for now; routing will use it next.
- **Model registry** — `GET/POST/PATCH/DELETE /api/v1/model-registry` (admins only): per-model data class, regions, risk rating, retention, capabilities, linked provider key. Administration only for now; routing does not use it yet.
- **Admin console** — command palette (Ctrl/Cmd+K) with theme switching, breadcrumbs, spend by API key, shared tables, tabbed policy page, keyboard and axe accessibility audits.
- **Seeded demo** — `docker compose -f docker-compose.demo.yml up`, with prebuilt images published to GHCR and a recorded walkthrough.

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
