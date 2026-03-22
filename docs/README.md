# OpenProxyAI Documentation

OpenProxyAI is an enterprise LLM proxy between your organization and LLM providers (OpenAI, Anthropic, Azure, Mistral, etc.). It includes unified **gateway API keys** and **JWT admin auth**, policy enforcement (PII, keywords, model allowlists), cost and rate limits, **semantic caching** (in-memory + Redis + pgvector), **data residency** routing, **compliance templates** (HIPAA, PCI-DSS, FedRAMP), **teams** (org structure and optional budgets), **model A/B experiments**, **Stripe billing** (including optional metered usage), a **prompt playground** with templates and model compare, and audit logging for SOC 2 / HIPAA / GDPR-style programs.

---

## Getting Started

| Document | Purpose |
|----------|---------|
| [Quickstart](./getting-started/quickstart.md) | Create your first API key and make a request in 5 minutes |
| [SDKs](./guides/sdks.md) | Install and use the Python or TypeScript SDK |

---

## Reference

| Document | Purpose |
|----------|---------|
| [API Reference](./reference/api-reference.md) | All endpoints: proxy (`/v1/chat/completions`), management (keys, orgs, analytics) |
| [Webhook Events](./reference/webhook-events.md) | `cost.alert`, `cost.anomaly`, `policy.violation` event payloads |

---

## Guides

| Document | Purpose |
|----------|---------|
| [Authentication](./guides/authentication.md) | API key creation, RBAC roles, OIDC/SSO setup, key rotation |
| [Policy Configuration](./guides/policy-configuration.md) | Enforcement modes, PII detection, prompt injection, model allowlists |
| [Model Routing](./guides/model-routing.md) | Provider keys, weighted routing, router strategies |
| [Base URL Migration](./guides/base-url-migration.md) | Use OpenAI/Anthropic SDKs with only a `base_url` change |
| [Cost Management](./guides/cost-management.md) | Per-user budgets, anomaly detection, budget alert webhooks |
| [Stripe & billing](./guides/stripe-setup.md) | Products, webhooks, env vars. Quick setup: [stripe-webhook-setup.md](./guides/stripe-webhook-setup.md) |
| [Experiments & teams](./guides/experiments-and-teams.md) | Model A/B tests, team APIs, optional `x-openproxy-team-id` on the proxy |
| [Enterprise Deployment](./guides/enterprise-deployment.md) | Intercept employee AI traffic via PAC file, DNS, firewall, or reverse proxy |
| [Customer-Cluster Install](./guides/customer-cluster-install.md) | Self-host on your own cluster with customer-provided PostgreSQL and Redis (no managed deps) |
| [Operational features](./guides/operational-features.md) | Batched spend, provider health check, circuit breaker, adaptive LB, spend reports, key rotation scheduler |
| [Voice Integration](./guides/voice-integration.md) | PTT hardware, STT engines, mobile apps, and wearables |

---

## Architecture

| Document | Purpose |
|----------|---------|
| [System Overview](./architecture/overview.md) | Request pipeline, async logging, sidecar vs core distinction |
| [Repository layout](./architecture/repo-layout.md) | Monorepo map: `backend/`, `admin-console/`, SDKs, Helm |
| [Architecture Decisions](./architecture/decisions.md) | Why key decisions were made — derived from LiteLLM, Portkey, Helicone, Bifrost |
| [Deployment](./architecture/deployment.md) | Docker Compose and Kubernetes Helm production guide |
| [Database Schema](./architecture/database-schema.md) | All tables, columns, constraints, and migration chain |

---

## Compliance

| Document | Purpose |
|----------|---------|
| [Security Architecture](./compliance/security.md) | Encryption, key rotation, audit log immutability, security headers |
| [SOC 2 & HIPAA Controls](./compliance/soc2-hipaa.md) | Control mapping for CC6, CC7, CC8, CC9, and HIPAA §164.312 |
| [Self-Hosted Security](./compliance/self-hosted-security.md) | Encryption, RLS, key rotation, network isolation for customer cluster |
| [Air-Gap Checklist](./compliance/airgap-checklist.md) | No outbound telemetry, license validation, upgrade path |

### Security review notes (internal / audit trail)

These are **not** runbooks — they record what was reviewed, findings, and remediation status for specific features or migrations.

| Document | Topic |
|----------|--------|
| [Security review report](./security/SECURITY_REVIEW_REPORT.md) | Auth, RLS, OWASP Top 10, audit immutability, self-hosted. RLS details: [database-schema.md](./architecture/database-schema.md#row-level-security-rls) |

---

## What's Shipped

| Document | Purpose |
|----------|---------|
| [Feature Reference](./features.md) | Complete inventory of every shipped capability with details |

---

## Roadmap

| Document | Purpose |
|----------|---------|
| [Roadmap](./roadmap.md) | Go-live status, P1–P3 backlog |
