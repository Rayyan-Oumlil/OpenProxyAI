# OpenProxyAI — Roadmap

> **Shipped inventory:** [features.md](./features.md).  
> Last updated: 2026-03-21

---

## P1 — Complete

Data residency Tier 2 (customer-cluster install, air-gap mode, ops/security docs). See [self-hosted-security.md](./compliance/self-hosted-security.md), [airgap-checklist.md](./compliance/airgap-checklist.md), [soc2-hipaa.md](./compliance/soc2-hipaa.md).

---

## P2 — Complete

Experiment quality scoring, adaptive load balancing, circuit breaker, prompt_id on proxy, session grouping, per-request overrides. See [features.md](./features.md) and [model-routing.md](./guides/model-routing.md).

---

## Production deployment

**Guide:** [architecture/deployment.md](./architecture/deployment.md) and [deploy/gcp](../deploy/gcp) — GCP Cloud Run + Vercel via gcloud CLI, GitHub Actions, and Workload Identity Federation.

---

## Future backlog (P3)

| Item | Notes |
|------|-------|
| MCP gateway | Model Context Protocol gateway for tool-augmented LLM flows |
| Voice endpoint | Speech-to-text / text-to-speech proxy |
| WASM plugins | Extensibility via WebAssembly modules |
| Vault / external secrets | Integrate HashiCorp Vault or similar for key injection |
| Eval scores API | Standalone eval API (beyond experiment request scores) |

---

