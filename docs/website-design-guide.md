# OpenProxyAI website — design guide for Claude Design

Use this to design the new marketing site in Claude Design (claude.ai → Design), then hand the canvas link back to Claude Code to build it.

---

## 1. What we learned from the two previous sites

| | Old site (`web-app`, live on openproxyai.com) | Redesign (`web-app-next`, deleted) |
|---|---|---|
| Keep | **Energy**: the live "request stream" table (time · team · model · tokens · latency · policy · status badges) made it feel like a running product | **Honesty**: every claim traced to code; 7 real pages; clean on phones |
| Drop | Invented proof: fake testimonials ("VP of Security", "Trusted by security teams"), "v2.4.1", "under four milliseconds", "1,600+ models", "start trial" / "book demo" for things that don't exist; nav overflowing on phones | Too much text, no images, felt flat |

**Goal for the new site:** the old site's energy + the redesign's honesty + real visuals.

---

## 2. Hard rules (non-negotiable)

1. **No invented proof.** No testimonials, customer logos, user counts, uptime or latency numbers unless you can point at the source. Use a visible placeholder like `[CUSTOMER QUOTE]` instead.
2. **Simulated things say "Simulated".** A live-looking request stream is fine if it's labelled.
3. **Only claim what's built** — the lists in §4. Backlog items are labelled "Next" or left out.
4. **Phone first-class:** 390 px wide, no sideways scroll, nav collapses into a menu.
5. **Accessible:** text contrast ≥ 4.5:1, real buttons/links, animations respect "reduce motion".
6. **CTAs that exist:** "Read the docs", "View on GitHub", "Deploy it". No "Start trial" / "Book demo" unless those flows exist.

---

## 3. Visual direction

Chosen direction: **B · Blueprint** — light, editorial, engineering-drawing feel.
Reference canvas (3 directions): https://claude.ai/artifact/BWixZUMLA69fF7vUsnZ8gL

- **Ground:** warm paper `#f4f1ea`, fine blue grid (24 px minor / 120 px major lines).
- **Ink:** near-black `#1b1b18`; accent blueprint blue `#1d3fd8`.
- **Type:** Instrument Serif (display, italic accents) · Schibsted Grotesk (body) · IBM Plex Mono (labels, code, "FIG. 1" captions).
- **Signature element:** pages as numbered *sheets* ("SHEET 01", "FIG. 2 — …"), with the 7-stage pipeline drawn as a technical figure and a trace dot moving through it.

### Imagery — you asked for more pictures. Best sources, in order:

1. **Real product screenshots, framed as "plates"** (most credible). Screens that exist in `admin-console/`: dashboard (spend, cost by model/team), logs, audit, policy, playground (side-by-side model compare), provider keys, teams, billing. Capture them with seeded demo data.
2. **Technical illustrations in the blueprint style**: exploded view of the gateway, annotated request diagram, cache tiers as a cutaway, the tenant boundary (RLS) as a floor plan.
3. **Animated diagrams**: the request stream (from the old site), the pipeline trace, a policy block (446) turning red.
4. **Stock or AI photos: avoid** people-at-laptops. If you want a photo mood, use abstract textures (paper, cable runs, server racks) — decoration, not proof.

---

## 4. Real content to use

### Positioning
- Headline: **The control plane for enterprise AI** — every model call and every agent action, governed and audited.
- One line: One gateway between your organisation and every model provider and MCP tool server, in your cloud or fully air-gapped.
- Drop-in: OpenAI-compatible — change `base_url`, keep your SDK.
- Providers: OpenAI, Anthropic, Azure OpenAI, Mistral (via LiteLLM).
- Status codes that say why: **402** budget exceeded · **429** rate limit · **446** blocked by policy.

### Request pipeline (in order)
Auth (API key / OIDC SSO) → Rate limit (req/min, tokens/min, $/day) → Policy (PII redaction, injection checks) → Cache (memory → Redis → pgvector semantic) → Provider (key rotation, failover, data residency) → Cache store → Audit log (async, never blocks the reply).

### Built capabilities (safe to claim)

**Models:** routing strategies (shuffle, round-robin, lowest-latency across weighted keys) · provider fallback on 429/5xx, never on client errors · circuit breaker · adaptive load balancing · three-tier cache (0.95 semantic threshold) · data residency (EU orgs only route through EU/global keys, enforced in SQL).

**Agents:** MCP gateway (one endpoint + one key for every registered tool server) · tool allow/block lists (blocked calls never reach the server) · guardrails on tool *arguments* (keyword + PII) with every call audited.

**Trust:** PII redaction (emails, SSNs, card numbers, prompts and responses, streaming included) · prompt-injection detection (DeBERTa classifier, pattern fallback) · tenant isolation with PostgreSQL row-level security · append-only audit log · compliance templates (HIPAA, PCI-DSS, FedRAMP presets) · per-org OIDC SSO.

**FinOps:** budgets and limits per org/team/user (over budget → 402) · cost anomaly detection vs 7-day baseline · month-end projection · chargeback labels · weekly/monthly spend reports to Slack or email.

### Backlog (label "Next" or leave out)
Per-agent identity · agent-to-agent audit · **tamper-evident hash-chained audit log** · predictive budgets.
> Note: design direction C showed a hash chain — that is *not built yet*.

### Engineering decisions (good "how it's built" content)
LiteLLM as a library, not a proxy · logging never blocks the response · tenant isolation in the database · guardrails as hooks · status codes that say why · a stateless MCP gateway · three cache tiers.

### Pricing (from `backend/app/config.py` PLAN_FEATURES)
| Plan | Price | Users | Audit retention | Highlights |
|---|---|---|---|---|
| Free | $0 | 3 | 7 days | 5 API keys, gateway, budgets and rate limits |
| Starter | $2,500/mo | 50 | 30 days | 50 keys, PII redaction, policy engine |
| Growth | $7,500/mo | 200 | 90 days | 200 keys, team budgets and chargeback |
| Enterprise | Custom | Unlimited | 365 days | OIDC SSO, customer-cluster or air-gapped install |

### Proof you *can* show
Open source (GitHub link) · test count and migration count counted from the repo at build time · CI runs RLS isolation tests on real Postgres · deploy options: Docker Compose, Helm chart, air-gapped mode.

---

## 5. Pages

| Page | Job |
|---|---|
| Home | Offer in one sentence, pipeline figure, live (simulated) request stream, 3 pillars, drop-in code, deploy options, open-source proof |
| Models | Routing, failover, cache, residency |
| Agents | MCP gateway, tool policy, tool guardrails |
| Trust | PII redaction (interactive demo is a nice touch), RLS, audit, SSO, compliance |
| FinOps | Budgets, anomalies, projection, chargeback |
| Engineering | "How I built it": stats, decisions, roadmap |
| Pricing | The 4 plans above |

---

## 6. Prompt to paste into Claude Design

> Design a marketing website for **OpenProxyAI**, an open-source, self-hosted control plane for enterprise AI: one OpenAI-compatible gateway in front of every LLM provider and MCP tool server, with budgets, guardrails, row-level tenant isolation and an append-only audit log.
>
> Style: "Blueprint" — warm paper background (#f4f1ea) with a fine blue engineering grid, near-black ink (#1b1b18), blueprint-blue accent (#1d3fd8). Instrument Serif for display, Schibsted Grotesk for body, IBM Plex Mono for labels. Pages feel like numbered engineering sheets ("SHEET 01", "FIG. 1 — Request pipeline").
>
> I want it visually rich: product screenshots framed as plates, technical illustrations (exploded gateway, cache cutaway, tenant floor plan), and animated diagrams: a 7-stage request pipeline with a moving trace dot, and a labelled "Simulated" live request stream with 200 / 402 / 429 / 446 status badges.
>
> Start with the Home page at 1440 px and 390 px. Use only this content: [paste §4]. Never invent testimonials, logos, customer counts or performance numbers — use [PLACEHOLDER] instead.

---

## 7. Handing it back

When the design is ready, send Claude Code the canvas link and say which artboards are final. Claude Code will rebuild it as a new site folder, wire it to the real data (capabilities, pricing, repo stats), and deploy it to Vercel only — never GCP.
