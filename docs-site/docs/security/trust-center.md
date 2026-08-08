---
title: Trust Center
description: OpenProxyAI's own security posture — data handling, subprocessors, certification status, and how to report a vulnerability.
---

# Trust Center

This page is about OpenProxyAI's own security posture as a vendor — not the guardrails your requests pass through (see [Policies & Guardrails](/core-concepts/policies-and-guardrails) for that). This is what an auditor or security reviewer actually wants to know before signing off on adding OpenProxyAI to your stack.

## Certification status

**OpenProxyAI does not currently hold SOC 2, ISO 27001, or HIPAA certification.** The [compliance templates](/guides/compliance-templates) (Healthcare, Finance, Government) are pre-built *policy configurations* aligned to those frameworks' requirements — they are a starting point for your own audit, not a substitute for it. If a certification badge appears anywhere implying otherwise, that's a mistake — report it.

## Deployment model and data handling

OpenProxyAI is self-hosted: it runs inside your own VPC, against your own Postgres and Redis. There is no multi-tenant SaaS data plane where your requests pass through infrastructure OpenProxyAI operates on your behalf — the software runs on infrastructure you control, so the relevant subprocessors are the ones *you* choose (your cloud provider, your database host), not a fixed list OpenProxyAI dictates.

For the Starter and Growth plans' hosted option, deployment specifics and the exact subprocessor list are covered during procurement — ask your point of contact.

## How data isolation is enforced

Every organization's data is isolated at the database layer using PostgreSQL row-level security, not only application-level query filters. See [Row-Level Security](/security/row-level-security) for the technical detail.

## Audit logging

Every request, policy decision, and routing outcome is logged immutably — entries are never edited or deleted. See [Audit Logging](/security/audit-logging).

## Secret management

Provider API keys and infrastructure credentials (`DATABASE_URL`, `SECRET_KEY`, etc.) are read from environment variables or your platform's secret manager — never hardcoded, never logged in plaintext.

## Reporting a vulnerability

If you find a security issue, report it before disclosing it publicly. Include enough detail to reproduce it. Responsible disclosure is credited unless you ask otherwise.

:::info Security contact and disclosure timeline coming soon
A dedicated security contact address and formal disclosure SLA are being finalized. Until then, route reports through your normal support contact and flag them as security-sensitive.
:::
