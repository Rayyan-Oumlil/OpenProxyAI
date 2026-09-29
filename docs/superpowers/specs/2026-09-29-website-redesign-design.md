# OpenProxyAI Website Redesign — "Mission Control"

- **Date:** 2026-09-29
- **Status:** Draft — awaiting review
- **Scope:** `web-app/` (openproxyai.com). Docs site (`docs-site/`) is out of scope except for nav links.

---

## 1. Goal

openproxyai.com is the **north star for the product**: it presents OpenProxyAI as the product it is becoming, and the repo is built up to match it. It is also the page recruiters land on from the "[Live Demo]" link on Rayyan's CV, so it must be impressive *and* hold up to scrutiny.

### Success criteria

1. A technical visitor understands what the product does within 10 seconds of landing, from the hero alone.
2. The site has a distinctive, coherent visual identity (one system, not a stack of template sections).
3. Nothing on the site can be exposed as fabricated in an interview (see §3).
4. Every page ships as prerendered HTML; link previews and no-JS visitors see real content.
5. Performance budget met on every page: LCP < 2s, JS < 200KB gzip, Lighthouse ≥ 95 (all four categories).
6. Every capability shown on the site that is not yet in the repo maps to a named backlog item (§8).

### Non-goals

- Deploying the backend or any live sandbox.
- Building the backlog features (§8) — each gets its own spec.
- Rewriting CV bullets — done as §8 features land.
- Redesigning the admin console or docs site.

---

## 2. Positioning

> **The control plane for enterprise AI — every model call and every agent action, governed and audited.**

Three pillars, used consistently across nav, home, and page structure:

| Pillar | Meaning |
|---|---|
| **Models** | Routing, failover, caching, budgets, residency for LLM traffic |
| **Agents** | Governance of agent → tool traffic (MCP gateway, per-agent identity, tool policies) |
| **Trust** | Guardrails, tenant isolation, tamper-evident audit, compliance templates |

FinOps is presented as its own page but framed as a cross-cutting capability, not a fourth pillar.

---

## 3. Honesty rules (hard constraints)

| Allowed | Forbidden |
|---|---|
| Describing capabilities not yet built (they become backlog, §8) | Testimonials, customer quotes, customer logos, "trusted by" |
| Ambitious positioning | Numbers presented as measured that were not measured |
| Simulated traffic, **labeled `SIMULATED`** | Fake status indicators ("operational"), SLAs, fake version strings |
| Real repo numbers (tests, migrations, etc.) | Invented scale numbers ("1,600+ models", "Tn tokens/day") |

Specific removals from the current site: `TestimonialsSection`, "99.99% SLA" (`PricingSection`), "Status: operational" (`FooterSection`), "v2.4.1" / "LIVE" badges, "1,600+ models", "under four milliseconds" measured-P50 claim.

Real numbers shown on `/engineering` are generated at build time from the repo (§6.5), never hand-typed.

---

## 4. Visual direction — "Mission Control"

The site looks like the thing it sells: a control plane. Calm, precise, technical — Linear × Vercel × air-traffic-control, not neon hacker terminal.

### Design tokens (CSS variables, dark-first)

| Token | Role | Direction |
|---|---|---|
| `--bg` | Page | near-black navy (e.g. `#0A0E14`) |
| `--surface` / `--surface-2` | Panels | 1–2 steps lighter navy |
| `--line` | Grid, edges | low-contrast blue-grey |
| `--ink` / `--ink-dim` | Text | off-white / muted |
| `--signal` | The one accent: blocks, alerts, focus | warm amber |
| `--ok` | Allowed / cache hit | desaturated teal |
| `--danger` | 446 / 402 outcomes | restrained red, used sparingly |

Exact hex values are finalized during implementation with a contrast check (WCAG AA minimum for all text).

### Typography

- Sans for headlines and body (one variable family, e.g. Inter Tight / Geist).
- Mono only for data: traces, codes, headers, code samples.
- Type scale is fixed in tokens; no ad-hoc sizes.

### Motion principles

- Motion explains; it never decorates. Every animation shows a real mechanism (routing, blocking, caching, hashing).
- Content is visible without JS and without animation. Animation is progressive enhancement.
- `prefers-reduced-motion`: Map renders static; scroll journeys become stacked static panels.

---

## 5. Information architecture

Nav: `Models · Agents · Trust · FinOps · Engineering · Docs ↗ · Pricing` + primary CTA `View on GitHub` + secondary `Read the docs`.

(The current "Book demo" / "Start trial" CTAs are removed — there is no demo or trial to book.)

### 5.1 Home `/`

1. **Hero** — full Map (all node types), live simulated flow. Hover/tap a packet → trace tooltip (stages, outcome, headers). Headline = positioning line. `SIMULATED` tag in the Map corner.
2. **Follow one request** — scroll-pinned journey. The camera follows a single request through the 7 pipeline stages (Auth → Rate limit → Policy → Cache → Route → Upstream → Log). Each stage gets one sentence plus the real header/status it produces.
3. **Three pillars** — Models / Agents / Trust cards, each linking to its page, each with a mini-Map thumbnail of that page's scene.
4. **Drop-in** — code tabs (Python / TypeScript / curl) showing the `base_url` swap from the OpenAI SDK.
5. **WITHOUT / WITH** — side-by-side: tangled direct app→provider calls vs. one governed chokepoint.
6. **Deploy anywhere** — Cloud / VPC / air-gapped, reflecting the real `AIRGAP_MODE` and Helm chart.
7. **Open source** — GitHub link + real repo stats (replaces testimonials).

### 5.2 `/models`

- Hero scene: gateway → provider nodes. A provider trips its circuit breaker; traffic visibly reweights to healthy keys.
- Sections: routing strategies (`simple_shuffle`, `round_robin`, `lowest_latency`), fallback on 429/5xx, circuit breaker, **3-tier cache waterfall** (L1 TTLCache → L2 Redis → L3 pgvector, with the 0.95 similarity threshold), budgets (402), data residency (EU packet blocked from US-only key).

### 5.3 `/agents` (🔨 backlog-driven)

- Hero scene: agents → gateway → MCP tool servers; one tool call blocked by policy.
- Sections: MCP gateway (one endpoint, many tool servers), per-agent identity, per-agent tool allowlists, guardrails on tool calls, A2A audit.

### 5.4 `/trust`

- Hero scene: **audit chain** — log entries linked by hash; visitor can "tamper" with an entry and watch the chain break from that point.
- **PII redaction demo** — visitor types text; emails, SSNs, card numbers are redacted live using the patterns ported from the backend (§6.4).
- Sections: prompt injection detection (DeBERTa model + regex patterns), RLS tenant isolation (diagram of `app.current_org_id` scoping), compliance templates (HIPAA / PCI / FedRAMP), enforcement modes (off / log_only / enforce).

### 5.5 `/finops`

- Hero scene: spend streams splitting by team into chargeback buckets.
- Sections: org/team/user budgets, 80% threshold alerts, cost anomaly detection (7-day baseline), month-end projection, request labels for chargeback.

### 5.6 `/engineering` — recruiter landing page

Written in Rayyan's voice. Linked from the footer on every page and from the CV.

- Real architecture diagram (derived from the code, not the vision).
- Stack and why (FastAPI async, LiteLLM as a library not a fork, Postgres RLS, Redis, pgvector).
- 4–6 design decisions with tradeoffs (e.g. fire-and-forget logging with own DB sessions; RLS via transaction-scoped `set_config`; hooks-based policy engine; custom status codes 446/402).
- Real numbers (build-time generated, §6.5): test count, test files, migrations, API route modules, services.
- Links: GitHub repo, docs site, specific source files.
- A "What's built vs. what's next" list, driven by the same data as §8.

### 5.7 `/pricing`

Tier cards kept (Free / Starter / Growth / Enterprise) with prices from `PLAN_FEATURES`. No SLA claims. FAQ kept, reviewed for fabricated claims.

### 5.8 Global

- Footer: "Designed & built by Rayyan Oumlil" + GitHub + LinkedIn + `/engineering`.
- Cmd+K palette: kept, re-indexed to the new pages.
- 404 page in the Map style.
- Per-page OG images (static, generated at build or hand-exported).

---

## 6. Technical architecture

### 6.1 Stack

| Layer | Choice |
|---|---|
| Framework | React 19 + React Router v7 **framework mode**, `prerender` all routes to static HTML |
| Styling | Tailwind 3 + CSS-variable tokens |
| Motion | GSAP 3 (ScrollTrigger, MotionPath) |
| Map rendering | SVG |
| Tests | Vitest (unit), Playwright (e2e + visual), Lighthouse CI |
| Hosting | Vercel (static output; remove the SPA catch-all rewrite) |

Unused shadcn/Radix dependencies are removed; only components actually used are kept.

### 6.2 Module layout

```
web-app/src/
  routes/                 # one file per page (home, models, agents, trust, finops, engineering, pricing)
  map/
    scenes/               # data only: nodes, edges, viewport per page
      home.ts models.ts agents.ts trust.ts finops.ts
    sim/
      engine.ts           # deterministic event generator (pure, no DOM)
      rng.ts              # seeded PRNG
      outcomes.ts         # stage outcomes + real status codes/headers
    Map.tsx               # renders a scene, subscribes to engine events, animates packets
    PacketTooltip.tsx
  demos/
    pii/redact.ts         # pure: ported backend regexes
    pii/PiiDemo.tsx
    audit/chain.ts        # pure: SHA-256 hash chain via WebCrypto
    audit/AuditChainDemo.tsx
  sections/               # page sections (small, one purpose each)
  data/
    repo-stats.json       # generated at build (§6.5)
    capabilities.ts       # every capability: page, status (built | backlog), backlog id
  design/tokens.css
```

### 6.3 The Map

- **Scene** (data): `{ nodes: {id, kind: user|agent|gateway|model|tool|store, label, x, y}[], edges: {from, to}[], viewport, flows: FlowSpec[] }`.
- **Engine** (pure): given a scene + seed, emits a stream of `RequestEvent { id, path: nodeId[], stages: StageResult[], outcome: 'ok'|'cache_hit'|'blocked_446'|'budget_402'|'rate_429'|'redacted', headers }`. Same seed → same sequence.
- **Map component**: renders SVG nodes/edges from the scene; animates packets along edges via GSAP MotionPath; pauses when off-screen (IntersectionObserver) and when the tab is hidden.
- Accessibility: SVG has a `<title>`/`<desc>`; a visually hidden text list describes the scene; tooltips reachable by keyboard.

### 6.4 Demos (real logic, client-side)

- **PII redaction:** ports exactly the backend patterns in `backend/app/services/policy_service.py` (`_EMAIL_RE`, `_SSN_RE`, `_CC_RE`). Replacement token matches the backend's `[REDACTED]`. Test cases mirror the backend's PII tests. No other entity types are shown (the backend does not implement them).
- **Audit chain:** `entry.hash = SHA-256(prev_hash || canonical_json(entry))`. Editing an entry recomputes and marks every downstream link invalid. Labeled as a demonstration of the planned tamper-evident audit log (backlog B2).

### 6.5 Build-time repo stats

A Node script (`scripts/repo-stats.mjs`) runs before build and writes `src/data/repo-stats.json`:

- test functions (`def test_` count in `backend/tests`), test files, migration files, route modules, service modules, last commit date.

Numbers on the site come only from this file. If the script fails, the build fails (no stale fallback).

### 6.6 Performance and robustness

- Each route's JS is code-split; GSAP loaded only on routes that animate.
- Fonts self-hosted, subset, `font-display: swap`.
- No scroll-reveal that hides content by default (fixes the current blank-page bug).
- Budgets enforced by Lighthouse CI; a PR that breaks them fails.

---

## 7. Testing

| Layer | What |
|---|---|
| Vitest | Engine: determinism (same seed → same events), every outcome reachable, stage order matches the pipeline. `redact.ts`: backend-mirrored cases. `chain.ts`: valid chain verifies; single edit invalidates exactly downstream links. `capabilities.ts`: every `backlog` item has a backlog id. |
| Playwright | Every route renders headline + body text with JS disabled. No console errors. Visual snapshot of each Map scene (seeded, animation paused). Cmd+K opens and navigates. |
| Lighthouse CI | Budgets from §1 on every route. |
| Content lint | A test fails if forbidden strings appear in `src/` (`testimonial`, `SLA`, `operational`, `trusted by`). |

---

## 8. Capability → backlog map

Capabilities shown on the site that are not in the repo yet. Each becomes its own spec → plan → implementation, and only then a CV bullet.

| ID | Capability | Page | Notes |
|---|---|---|---|
| B1 | MCP gateway — single endpoint fronting multiple MCP servers, per-caller tool filtering | /agents | Already in `docs/roadmap.md` P3 |
| B2 | Tamper-evident audit log — hash-chained `request_logs` with verification endpoint | /trust | Extends existing audit immutability migration |
| B3 | Per-agent identity — agent-scoped keys with their own policies and budgets | /agents | Builds on team-scoped API keys |
| B4 | Guardrails on tool calls — policy evaluation on MCP tool arguments/results | /agents | Reuses `policy_service` hooks |
| B5 | A2A audit — log and attribute agent-to-agent calls | /agents | Depends on B1, B3 |
| B6 | Predictive budgets — forecast exhaustion date per team | /finops | Extends month-end projection |

Related hardening items from the 2026-09-28 audit (not website work, but they back up the /trust and /engineering claims): enforce RLS by connecting as a non-superuser role and run RLS tests in CI; fix the two non-hermetic experiment tests; publish or remove the SDK install instructions.

---

## 9. Migration from the current site

- Remove: all 19 existing `sections/*`, `lib/useScrollReveal.ts`, unused shadcn components, `vercel.json` catch-all rewrite.
- Keep and restyle: `CommandPalette`, `Navigation` (rebuilt), Vercel Analytics.
- Existing URLs `/product`, `/security`, `/providers` → permanent redirects to `/models`, `/trust`, `/models`.

## 10. Open questions

None blocking. Final hex values and font choice are decided during implementation under the constraints in §4.
