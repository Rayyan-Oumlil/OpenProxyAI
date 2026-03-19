# Reference Architecture Analysis

> Architecture and feature patterns from competitor projects studied during planning.
> Used to inform the [roadmap](./roadmap.md).

---

## Competitor Stack Summary

| Project | Stack | Notable patterns |
|---|---|---|
| **LiteLLM** | Python, FastAPI, DualCache (mem+Redis), Prisma | Proxy hooks (CustomLogger), DBSpendUpdateWriter (batch spend 60s), router strategies (lowest_latency, simple_shuffle), many proxy endpoints (/v1/messages, /v1/images, /v1/batches, etc.), Redis/GCS/S3/Qdrant semantic cache |
| **Portkey Gateway** | TypeScript, Hono, Workers/Node | tryTargetsRecursively fallback, HookSpan/HooksManager (before/after, Guardrail vs Mutator), plugin registry (aporia, patronus, etc.), config from headers, circuit breaker |
| **Bifrost** | Go, 11 µs overhead | Semantic cache, MCP gateway, adaptive load balancing, Vault, plugins (governance, logging, semanticcache), NPX zero-config, Web UI |
| **Helicone** | NextJS, Worker, Express, Supabase, ClickHouse | Sessions (agent trace grouping), Scores API for evals, Playground, prompt versioning, real-time webhooks, Datasets + RAGAS |
| **Envoy AI Gateway** | Go, Kubernetes Gateway API | AIGatewayRoute CRD, routing by x-ai-eg-model header, LLMRequestCosts in metadata, external processor (WASM-capable) |

---

## Competitive Landscape (March 2026)

**Market bifurcation:**
1. **Performance/Developer-focused** (Helicone, LiteLLM, Envoy) — speed, open-source, DX
2. **Enterprise/Compliance-focused** (Portkey, Kong, Azure) — governance, audit trails, regulatory
3. **Niche specialists** (Braintrust, LangSmith, Martian) — observability + evals, semantic routing

**Key threat:** Cloud providers (Azure, AWS) bundling LLM gateway features for free. Mitigation: stay multi-cloud and provider-agnostic.

**OpenProxyAI positioning:** "Compliance-First, Cost-Optimized AI Gateway" — between Portkey's feature breadth and Helicone's performance minimalism. Own the vertical compliance templates (healthcare/finance/gov) that no competitor does well.

---

## Top Deal Closers by RFP Frequency

| Feature | % of Enterprise RFPs | OpenProxyAI Status | ACV Impact |
|---|---|---|---|
| Data residency / on-prem | 65% | Roadmap P1 | $100K+ blocker |
| Semantic caching | 58% | Roadmap P0 | $50K+ cost justification |
| Prompt versioning & A/B testing | 42% | Roadmap P0/P2 | $20K+ feature request |
| Vertical compliance templates | 35% | Roadmap P1 | $75K+ for healthcare |
| Canary deployments | 28% | Roadmap P2 | $15K+ feature request |
| MCP / tool governance | 12% | Roadmap P3 | Emerging |
