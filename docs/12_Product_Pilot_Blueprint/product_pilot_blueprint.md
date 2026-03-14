# Product Pilot Blueprint - OpenProxyAI

## Purpose

This document is the single execution anchor for moving OpenProxyAI from "working gateway" to "paid security product".

It defines:
- the exact ICP and buyer problem
- the 14-day pilot flow
- measurable success criteria
- conversion criteria from pilot to paid
- product boundaries for this phase

---

## 1) ICP Lock

### Primary ICP (Phase 1)

- Industry: finance, healthcare, government-adjacent B2B
- Company size: 200-3,000 employees
- Team maturity: already using LLM APIs, but no centralized governance
- Deployment preference: self-hosted in customer-controlled environment

### Buyer and Champion

- Economic buyer: CISO / Head of Security / Compliance lead
- Technical champion: staff engineer / platform engineer / ML platform owner

### Core Buyer Trigger

"We cannot keep scaling AI usage without centralized auditability, spend control, and policy enforcement."

---

## 2) Product Boundary (Pilot Scope)

### In Scope

- Unified LLM gateway (OpenAI-compatible proxy)
- API key auth and org/user governance
- Request logging and searchable request history
- Spend tracking (org + user)
- Rate limits and budget controls
- Basic policy hooks (PII + keyword + model allowlist)
- Admin console for operations and evidence review

### Out of Scope (Current Pilot)

- Full enterprise SSO and SCIM
- Advanced compliance automation packs
- Deep RAG orchestration and document pipelines
- Kubernetes-first deployment templates

---

## 3) 14-Day Pilot Flow

### Day 0-1: Setup

- Deploy OpenProxyAI in customer environment (Docker Compose)
- Connect one provider (Anthropic or OpenAI)
- Create org admin and API keys
- Route first real application traffic

### Day 2-5: Baseline Governance

- Enable cost limits by org/user
- Enable first policy hook pack
- Verify logs and analytics visibility
- Export first audit sample

### Day 6-10: Controlled Production Use

- Expand to one real internal workflow
- Track blocked events vs allowed events
- Track daily spend and usage by team/user

### Day 11-14: Decision Window

- Review pilot scorecard
- Decide paid plan (Starter or Growth)
- Define rollout plan to additional teams

---

## 4) Pilot Success Metrics

### Must-Hit Metrics

- 100% of pilot AI requests routed through gateway
- 100% of requests written to immutable audit logs
- Daily and cumulative cost visible by org/user
- At least one policy event captured and explainable
- Exportable evidence package delivered in < 1 day

### Operational Quality Metrics

- Gateway median added latency <= 40 ms
- Error rate attributable to gateway <= 1%
- No unknown spend events (every call attributed)

---

## 5) Conversion Criteria (Pilot -> Paid)

Customer converts when all are true:

- Security owner confirms audit visibility is materially improved
- Engineering owner confirms no integration blockers remain
- Finance/ops confirms spend controls are usable
- Team agrees OpenProxyAI replaced direct unmanaged LLM calls for pilot workload

Target decision SLA: 14 days from production pilot start.

---

## 6) Evidence Outputs Required

For each pilot, produce:

- Request audit export (CSV/JSON, date-bounded)
- Spend report by user/model/provider
- Policy event report (blocked or flagged requests)
- Incident trace sample (request id -> full timeline)

These outputs are mandatory because they directly map to CISO and compliance review needs.

---

## 7) Product Messaging Guardrail

Do not claim features that are not productized.

Allowed positioning now:

- "Zero Trust gateway foundation for enterprise AI"
- "Centralized logging, cost control, and policy enforcement workflow"

Avoid until implemented and validated:

- "Fully automated SOC 2/HIPAA compliance"
- "Enterprise-grade SSO suite" without production support

---

## 8) 30/60/90 Conception Plan

### 0-30 Days

- Complete pilot-grade policy hooks and evidence export
- Tighten admin workflows for logs, spend, and governance
- Run 3-5 design-partner discovery calls

### 31-60 Days

- Execute 1-2 live pilots with explicit scorecards
- Remove top friction points from onboarding and daily ops
- Publish one reference deployment + pilot case summary

### 61-90 Days

- Convert first pilots to paid
- Lock Phase 2 roadmap based on proven buyer demand
- Standardize rollout playbook for repeatable onboarding

---

## 9) Ownership and Cadence

Weekly operating cadence:

- Monday: product + pilot metrics review
- Wednesday: customer feedback synthesis and prioritization
- Friday: shipping review + evidence quality review

Single owner: solo founder until first two paid pilots are complete.

---

## 10) Exit Criteria for This Blueprint

This blueprint is complete when:

- two paid customers are onboarded from pilot process
- pilot scorecard is repeatable without custom implementation
- docs and product status stay aligned each sprint
