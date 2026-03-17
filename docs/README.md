# OpenProxyAI Documentation

OpenProxyAI is an enterprise LLM proxy / control plane that sits between your organization and LLM providers (OpenAI, Anthropic, Azure, Mistral, etc.). It provides unified API key management, policy enforcement (PII redaction, keyword blocking, model allowlists), cost control (per-user budgets, departmental chargebacks), and complete audit trails for compliance (SOC 2, HIPAA, GDPR).

---

## Getting Started

Start here if you are new to OpenProxyAI.

| Document | Purpose |
|----------|---------|
| [Quickstart](./quickstart.md) | Create your first API key and make a request in 5 minutes |
| [SDKs](./guides/sdks.md) | Install and use the Python or TypeScript SDK |

---

## API Reference

Complete endpoint documentation for the proxy and management APIs.

| Document | Purpose |
|----------|---------|
| [API Reference](./api-reference.md) | Proxy endpoints (`/v1/chat/completions`, `/v1/embeddings`), management endpoints (keys, organizations, analytics) |
| [Webhook Events](./webhook-events.md) | Incoming webhooks for cost alerts, policy violations, and audit events |

---

## Guides

Task-oriented guides for specific features and deployments.

| Document | Purpose |
|----------|---------|
| [Authentication](./guides/authentication.md) | API key creation, rotation, and OIDC/SSO setup |
| [Policy Configuration](./guides/policy-configuration.md) | Keyword blocking, PII detection, model allowlists, and enforcement modes |
| [Model Routing](./guides/model-routing.md) | Multi-provider fallback, weighted load balancing, and per-user model restrictions |
| [Cost Management](./guides/cost-management.md) | Per-user budgets, department chargebacks, cost tracking, and spending alerts |
| [Enterprise Deployment](./guides/enterprise-deployment.md) | Intercept employee AI traffic via PAC file, DNS redirection, firewall rules, or reverse proxy |
| [Voice Integration](./guides/voice-integration.md) | Enable voice input via PTT hardware, STT engines, mobile apps, and wearables |

---

## Architecture

Deep dives into how OpenProxyAI works internally.

| Document | Purpose |
|----------|---------|
| [System Overview](./architecture/overview.md) | High-level architecture, request pipeline, and key components |
| [Architecture Decisions](./architecture/decisions.md) | Why key design choices were made — derived from studying LiteLLM, Portkey, Helicone, Bifrost |
| [Deployment](./architecture/deployment.md) | Docker Compose, Kubernetes Helm, infrastructure requirements |
| [Database Schema](./architecture/database-schema.md) | Detailed schema reference (organizations, API keys, logs, etc.) |

---

## Compliance

Security controls and regulatory compliance details.

| Document | Purpose |
|----------|---------|
| [Security Architecture](./compliance/security.md) | Authentication, encryption, audit logging, rate limiting, PII detection |
| [SOC 2 & HIPAA Controls](./compliance/soc2-hipaa.md) | Mapping to specific control requirements and certification roadmap |

---

## Quick Links

### API Keys
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/api-keys` | POST | Create a new API key |
| `/api/v1/api-keys` | GET | List all API keys for your organization |
| `/api/v1/api-keys/{id}` | PATCH | Update key metadata (name, last_used_at) |
| `/api/v1/api-keys/{id}` | DELETE | Revoke an API key |

All requests require the `Authorization: Bearer opai_xxxxxxxxxxxxxx` header.

### Organization Settings
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/organizations/current` | GET | Get current organization details |
| `/api/v1/organizations/current` | PATCH | Update organization settings (name, plan) |
| `/api/v1/organizations/current/policy` | GET | View current policy rules |
| `/api/v1/organizations/current/policy` | PATCH | Update policy (keyword blocking, PII detection, model allowlists) |

### Proxy Endpoints
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/v1/chat/completions` | POST | Send messages to any LLM provider |
| `/v1/embeddings` | POST | Generate embeddings for text |

Model names are provider-prefixed: `openai/gpt-4o-mini`, `anthropic/claude-opus`, `azure/gpt-4`, etc.

---

## Support

### Questions or Issues?

- Check the [Quickstart](./quickstart.md) or relevant guide
- Review the [API Reference](./api-reference.md)
- Contact your account manager or support@openproxyai.com

### Reporting Security Issues

Please report security vulnerabilities to `security@openproxyai.com` rather than public issue trackers.

---

## What's New?

### Phase 3 (Current)

- Kubernetes Helm chart for enterprise deployment
- Microsoft Presidio PII detection
- Prometheus metrics endpoint
- Webhook events for cost alerts and policy violations
- Enhanced audit logging with immutable archival

### Phase 2 (Completed)

- OIDC/SSO single sign-on
- Python and TypeScript SDKs on PyPI / npm
- Invite system for team member onboarding
- Plan enforcement (Free/Starter/Growth/Enterprise)
- Admin console v2 with charts and policy editor

### Phase 1 (Completed)

- FastAPI proxy engine with LiteLLM integration
- PostgreSQL + Redis backend
- API key management
- Rate limiting (RPM, TPM, daily budget)
- Policy hooks (before/after request)
- Admin console with log viewer
