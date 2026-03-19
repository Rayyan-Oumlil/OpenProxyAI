# OpenProxyAI Documentation

OpenProxyAI is an enterprise LLM proxy that sits between your organization and LLM providers (OpenAI, Anthropic, Azure, Mistral, etc.). It provides unified API key management, policy enforcement (PII redaction, keyword blocking, model allowlists), cost control (per-user budgets, departmental chargebacks), semantic caching (3-tier: in-memory + Redis + pgvector), data residency routing, compliance templates (HIPAA, PCI-DSS, FedRAMP), a prompt playground with model comparison, and a complete audit trail for SOC 2, HIPAA, and GDPR compliance.

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
| [Model Routing](./guides/model-routing.md) | Provider keys, weighted routing, fnmatch model patterns |
| [Cost Management](./guides/cost-management.md) | Per-user budgets, anomaly detection, budget alert webhooks |
| [Enterprise Deployment](./guides/enterprise-deployment.md) | Intercept employee AI traffic via PAC file, DNS, firewall, or reverse proxy |
| [Voice Integration](./guides/voice-integration.md) | PTT hardware, STT engines, mobile apps, and wearables |

---

## Architecture

| Document | Purpose |
|----------|---------|
| [System Overview](./architecture/overview.md) | Request pipeline, async logging, sidecar vs core distinction |
| [Architecture Decisions](./architecture/decisions.md) | Why key decisions were made — derived from LiteLLM, Portkey, Helicone, Bifrost |
| [Deployment](./architecture/deployment.md) | Docker Compose and Kubernetes Helm production guide |
| [Database Schema](./architecture/database-schema.md) | All tables, columns, constraints, and migration chain |

---

## Compliance

| Document | Purpose |
|----------|---------|
| [Security Architecture](./compliance/security.md) | Encryption, key rotation, audit log immutability, security headers |
| [SOC 2 & HIPAA Controls](./compliance/soc2-hipaa.md) | Control mapping for CC6, CC7, CC8, CC9, and HIPAA §164.312 |

---

## What's Shipped

| Document | Purpose |
|----------|---------|
| [Feature Reference](./features.md) | Complete inventory of every shipped capability with details |

---

## Roadmap

| Document | Purpose |
|----------|---------|
| [Roadmap](./roadmap.md) | Forward-looking only — prioritized P0–P3 work informed by competitive landscape |
| [Reference Analysis](./reference-analysis.md) | Competitor architecture notes and RFP signal data that informed the roadmap |
