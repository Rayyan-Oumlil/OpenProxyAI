# OpenProxyAI — Execution Plan (for an AI coding copilot)

Status: drafted 2026-11-01 from a repo review, competitor source reads, Anis's two documents, and research agents.
Audience: an AI coding assistant (e.g. GitHub Copilot agent mode) executing this plan under the owner's supervision.
Companion files: `design-specs.md` (detailed designs for Phases 1-4), `research-brief.md` (market + reference findings).

Evidence labels used below: **[CHECKED]** verified directly in the code by the author; **[AGENT]** reported by a research agent, re-verify before relying on it; **[UNVERIFIED]** secondary sources only.

---

## 0. Read this first (rules for the copilot)

1. Read `ARCHITECTURE_RULES.md` before touching anything. Its architecture rules are binding. Two corrections to it: the real migration head is `u2p3q4r5s6t7` (run `cd backend && alembic heads` to confirm; do not trust the chain listed in ARCHITECTURE_RULES.md), and there are 29 migration files.
2. **Nothing deploys.** Never run or trigger the `Build & Deploy` workflow with `workflow_dispatch`. Never touch GCP/AWS resources. Do not add any workflow that deploys automatically.
3. **One pull request per task ID** (e.g. `P0-4`). Branch name `fix/<task-id>-<slug>`. Small diffs. Each PR must include tests that fail before the change and pass after it.
4. **Definition of done for every task**: tests added; `cd backend && pytest -q` green; `ruff check` clean on the files you changed; no applied migration edited (new migration only); any new table has `ENABLE` + `FORCE ROW LEVEL SECURITY`, an org policy, and app-role grants (copy the pattern in `backend/alembic/versions/u2p3q4r5s6t7_add_mcp_servers.py` and `t1o2p3q4r5s6_app_role_grants_and_append_only_logs.py`); docs updated if behaviour changed.
5. Honour the ARCHITECTURE_RULES.md rules: `set_session_org_id` / `org_scoped_session` before RLS tables; logging is fire-and-forget via background tasks; sidecars (ClickHouse, Langfuse, Prometheus, webhooks, and any new OTel/SIEM exporter) never raise; core services fail hard; new routes must be wired in `main.py`.
6. If a task's premise does not match the code (line numbers drift, a bug is already fixed), stop and report instead of improvising. Line numbers below are approximate; grep for the symbol.
7. Do not start anything gated on an open owner decision (section 2) until the owner records the answer there.
8. Do not copy code from `references/` (competitor repos, gitignored, read-only). Use them for design ideas only. Run `scripts/clone-references.sh` only if it exists on your branch; otherwise ask the owner.

---

## 1. Where the project stands

Built (see `docs/features.md`): OpenAI-compatible chat/embeddings/models proxy over LiteLLM; key rotation, fallbacks, circuit breaker; 3-tier cache; policy engine (allowlist, keywords, regex PII, optional Presidio, prompt-injection model, response guardrails); budgets and rate limits; Postgres RLS multi-tenancy (enforced since PR #5); OIDC SSO; 3-role RBAC; audit log; webhooks; Stripe billing; compliance templates; data residency; air-gap mode; MCP gateway; A/B experiments; prompt templates/playground; admin console; marketing site; docs site; Python/TS SDKs.

Test state [AGENT, ran the suite]: 707 passed, 10 skipped (8 RLS tests need `DATABASE_URL`; 2 live-LLM tests need an opt-in flag), coverage 76%, RLS tests pass on a real Postgres. There is **no true end-to-end test** of the request pipeline: `tests/test_proxy.py` overrides dependencies and monkeypatches `acompletion`. CI runs no ruff (588 existing errors), no frontend typecheck/build, no e2e.

Strategy in one paragraph: lead with "free SSO/RBAC/audit + compliance evidence + runtime enforcement", then MCP/agent governance, then classification-aware routing. Prove every feature through a fake-upstream end-to-end test before adding more. Do not chase raw speed against Go/Rust gateways.

---

## 2. Owner decisions (status table — the owner fills this in)

| # | Decision | Recommended default | Status | Blocks |
|---|---|---|---|---|
| D1 | Rename the product? | Yes, after a 30-min check of shortlisted names (GitHub org, domains, USPTO/EUIPO). Agent's pick: Gatewarden, fallback Attestgate. Not trademark-checked. | **NO** (owner, 2026-11-08): keep the name OpenProxyAI; no rename work | Any rename work, SDK package names, public launch |
| D2 | Lead wedge | Compliance evidence + MCP governance first; classification-aware routing third | **AGREED** (owner, 2026-11-08): lead with compliance evidence + MCP governance; classification-aware routing third. The buyer calls may revisit it | Phase 2 start |
| D3 | Licence + pricing | Apache-2.0 core, paid modules in a separate commercial dir; ladder Community free / Team $299 / Business $1,500 / Enterprise from $25k per yr | **AGREED** (owner, 2026-11-08): Apache-2.0 core, paid modules in a separate commercial dir, the pricing ladder above. No spending yet: no domain, no Stripe or pricing changes until the owner says so | Pricing/Stripe constants, LICENSE files |
| D4 | Start Phase 0 | Yes (safe under every answer above) | **DONE** (Phase 0 and Phase 1 are finished and merged) | Everything |
| D5 | Scope agreed with Anis | Build his EIAG spec in stages; park the vision paper (voice, "Slack for AI", family/school packages) | **YES** (owner, 2026-11-08): build the EIAG spec in stages; park the vision paper | Phase 2-4 scope |
| D6 | HTTP status for request-time policy blocks | 446 everywhere (matches ARCHITECTURE_RULES.md and `docs-site/.../errors-and-status-codes.md`); the code currently returns 403 and `docs/architecture/overview.md:79` says 403 [CHECKED] | **446 everywhere** (owner delegated the choice, 2026-11-08; done in P1-32) | Task P0-6 |

Phase 0 tasks other than P0-6 are safe regardless of D1-D3 and D5.

---

## 3. Phase 0 — Trust foundation (about 12 engineer-days). Do first.

Goal: every claimed behaviour is proven through the real pipeline, and the known bugs are gone.

### P0-1 Row-level security on `request_scores` [CHECKED gap]
- Problem: no migration enables RLS on `request_scores`; `routes/experiments.py` results query filters only by `experiment_id`; unique key `(request_id, score_name)` is global.
- Do: new migration (on the current head) that enables+forces RLS with an `org_id` policy, grants to the app role, and replaces the unique constraint with `(org_id, request_id, score_name)`. Ensure writers use an org-scoped session.
- Tests: extend `tests/test_rls_isolation.py` (org A cannot read or upsert org B's scores). Needs `DATABASE_URL`; CI already runs RLS tests with `RLS_TESTS_REQUIRED=1`.
- Accept: isolation test green on real Postgres; existing experiment tests green.

### P0-2 Semantic cache must not call an outside embedding model implicitly [CHECKED]
- Problem: `services/cache_service.py` (two `aembedding(...)` calls near lines 194 and 324) uses the ambient env key and the default `text-embedding-3-small`, with no region, org or air-gap check. Only active when `SEMANTIC_CACHE_ENABLED=true` (default false).
- Do: add settings `SEMANTIC_CACHE_EMBEDDING_API_KEY` / `SEMANTIC_CACHE_EMBEDDING_API_BASE` and pass them explicitly (never rely on ambient env keys). Skip the L3 tier when `AIRGAP_MODE` is on, when the org's `data_region` is not global, or when no explicit embedding config exists. Include the org id in cache keys if not already.
- Tests: with a fake `aembedding`, assert it is not called in those cases and is called with the explicit key/base otherwise.

### P0-3 Env-key fallback must respect data residency [CHECKED partly]
- Problem: in `services/llm_service.py` `_select_provider_keys`, if no DB key matches, it falls back to `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `AZURE_API_KEY` without any region filter. `tests/test_data_residency.py` (near line 146) blanks those env keys to make its own test pass.
- Do: refuse the env fallback for orgs whose `data_region` is set and not global (clear error). Update the residency test to assert the refusal instead of blanking keys.

### P0-4 Tool-calling passthrough [CHECKED schema; effect needs a test]
- Problem: `schemas/chat.py` `Message` has only `role` and a required `content: str | list`. Assistant messages with `tool_calls` and null content fail validation; `tool_call_id` and `name` are dropped.
- Do: `Message` allows extra fields (`ConfigDict(extra="allow")`), `content` optional (`None` allowed), and make sure the serialised messages passed to LiteLLM keep the extras.
- Tests (via the fake upstream from P0-8, or a recorder on `acompletion`): `tools`, `tool_choice`, `parallel_tool_calls`, `response_format` with `json_schema`, an assistant message with `tool_calls` and `content=null`, a `role: tool` message with `tool_call_id`, streamed `tool_calls` deltas. Assert the upstream received exactly what the client sent.

### P0-5 Streaming usage and disconnect cost [CHECKED include_usage gap; disconnect behaviour is AGENT-reported]
- Problem: `stream_options={"include_usage": True}` is never set, so OpenAI-style providers may return no usage on streams (streamed requests may record $0). Cost/audit writes run after `[DONE]` inside the generator, so a client disconnect may skip them.
- Do: set `include_usage` for streams (merge with any client-supplied `stream_options`). Put the cost + audit scheduling in a `try/finally` so partial usage is recorded on `GeneratorExit`/`CancelledError` (estimate tokens with `litellm.token_counter` when the provider sent none). Set `X-OpenProxyAI-Cost-USD` correctly where possible.
- Tests: fake upstream asserts it received `include_usage`; a test that cancels mid-stream still produces a `request_logs` row and a spend increment.

### P0-6 Status code for policy blocks — BLOCKED ON D6
- Problem [CHECKED]: request-time policy blocks return 403 (`llm_service.py` near lines 497, 565, 585, 1219); only response guardrails return 446 (near line 998). Docs disagree (see D6).
- If D6 = 446: change all request-time policy blocks to 446, keep 403 for real authorization failures, update `docs/architecture/overview.md`, `docs/reference/api-reference.md` (playground compare), both SDKs' error handling, and tests; add a CHANGELOG note flagged as breaking for clients that match 403.

### P0-7 No inline awaits of `log_request` [CHECKED, 6 sites]
- Problem: `await log_request(...)` appears inline near lines 572, 611, 1124, 1242, 1265, 1331 of `services/llm_service.py`, against ARCHITECTURE_RULES.md's rule.
- Do: schedule through `BackgroundTasks` (or the existing `_schedule_log` helper) on every path including blocks, 429, 402 and errors. The background task must create its own org-scoped session.
- Tests: assert the response returns before the log write (e.g. a slow fake logger) and that a `request_logs` row is still written for blocked and errored requests.

### P0-8 Fake upstream + end-to-end pipeline tests (the missing layer)
- Create `backend/tests/fakes/fake_openai.py`: a small FastAPI app serving `POST /v1/chat/completions` (JSON and SSE), `/v1/embeddings`, `/v1/models`. Behaviour triggers by model name or header: `fail-429`, `fail-500`, `slow`, `bad-json`, `pii-response`, `mid-stream-error`. A recorder endpoint (`/__calls`) returns every request received. Deterministic hash-based embeddings. A pytest session fixture starts it on a random port; provider keys in tests use `api_base` of the fake with the `openai/` model prefix.
- Create `backend/tests/e2e/test_pipeline_e2e.py` (marker `e2e`; needs Postgres + Redis) covering, through the real app with no dependency overrides: no/bad key → 401; Nth request → 429; blocked keyword → block status per D6; over budget → 402; identical request → cache hit and the fake saw one call; audit row exists with cost; stream completes; `/metrics` increments; fallback from a failing key to a good key; RLS isolation between two orgs through the HTTP API.
- Create `scripts/smoke.sh` that starts Postgres/Redis/fake/uvicorn, runs migrations, seeds an org/key/policy, and runs the same checks with curl for local use.
- Docker may be unavailable in some environments; in CI use the existing `pgvector/pgvector:pg16` service. Note: the `vector` extension cannot be installed in some sandboxes, so mark tests needing pgvector accordingly.

### P0-9 CI hardening
- Add ruff with a committed config. Do **not** reformat the whole repo in one PR: add a baseline (per-file ignores or `--exit-zero` on legacy paths) and enforce ruff on changed files; fix the auto-fixable categories in a separate mechanical PR.
- Add jobs for `admin-console` (`npm ci`, typecheck, build, vitest) and `web-app` (typecheck, build, lint once its 8 errors are fixed).
- Add the e2e job from P0-8 on every PR.
- Pin `litellm` in `backend/requirements.txt` to the minor version currently installed and tested (it is `>=1.50.0` today with no ceiling); add a contract test per LiteLLM function used.
- Do not add any deploy step. The `build`/`migrate`/`deploy` jobs must stay `workflow_dispatch`-only.

### P0-10 Documentation corrections
- `docs/roadmap.md` and `OPENPROXYAI_PRESENTATION.md` section 8 list the MCP gateway as backlog; it is shipped. Update both (use `docs/features.md` as the source of truth).
- `docs/features.md`: header says 612 tests/55 files; measure and update. `ARCHITECTURE_RULES.md`: migration count (29) and head (`u2p3q4r5s6t7`); mention the MCP gateway files.
- `docs/compliance`/compliance templates: the FedRAMP template claims "FedRAMP security headers" but no such logic exists [AGENT]. Remove the claim or implement it; do not leave an unimplemented compliance claim.
- Never repeat in public copy: "high-risk EU AI Act obligations enforceable 2 Aug 2026" (the Digital Omnibus moved them to 2 Dec 2027 / 2 Aug 2028 [AGENT, law-firm sources]); "OWASP LLM Top 10 2026" (cite the 2025 edition); any competitor price; "immutable audit" until verified in code (see `tests/test_audit_immutability.py` and migration `f1a9c3e7d5b2`).

### P0 exit criteria
All of P0-1..P0-10 merged (P0-6 only if D6 decided); e2e suite and RLS tests required in CI; `docs/features.md` matches reality. The owner reviews, then Phase 1 starts.

---

## 4. Phase 1 — The wedge: governance you can demo (4-5 weeks). Design: `design-specs.md` §A and §C.

1. **MCP hardening (first 7 items, about 15.5 days)**: transport/SSRF fixes (resolve once and connect to the validated IP; explicit 3xx rejection; response-size and total-time caps; upstream session DELETE; `Origin` check; generic upstream error text); malicious-MCP test fixture; tool description pinning with hash and drift detection; output and description injection scanning; per-tool grants plus a header that can only narrow; virtual bundles per API key; taint tracking with session binding. Also: enforce `proxy:mcp` permission and rate limits on `/v1/mcp`.
2. **OpenTelemetry + SIEM export (about 6 days)**: `gen_ai.*` spans/metrics; CEF/syslog/JSON events (`AI-DLP-BLOCK`, `AI-POLICY-BLOCK`, `AI-UNAUTHORIZED-MCP`, ...). Sidecar rule: bounded queue, never blocks, never raises.
3. **Admin console (estimate 10-15 days)** — `design-specs.md` §E: responsive drawer nav (the console is unusable under ~1024 px today), shared dark design tokens with the website, `DataTable` with loading/empty/error states, nav groups (Observe, Govern, Connect, Admin), MCP servers/tools page (backend routes already exist at `/api/v1/mcp-servers`), request trace page, provider health page, number formatting, accessibility pass, route-based code splitting, lint + Playwright smoke tests.
4. **Demo**: `docker compose up` yields a seeded demo in under 5 minutes; a recorded 3-minute walkthrough (PII blocked, budget stop, audit row, MCP tool denied).

**Gate after Phase 1: five buyer conversations** (script in `research-brief.md`). Phase 2 scope is decided from what buyers say, together with D2/D5.

## 5. Phases 2-4 (after the gate; details in `design-specs.md`)
- Phase 2 (3-4 weeks) Classification-aware routing: model registry with `api_base`, data classes, authorized-set router with fallback closure, guardrail plugin runner with manifests and bindings, CEL rules, dry-run/shadow mode.
- Phase 3 (3 weeks) Eval loop (feedback endpoint usable with an API key, opt-in payload capture, datasets, evaluators, adaptive A/B with auto-stop, promotion gate) and `/v1/responses` + `/v1/rerank` after a pipeline refactor.
- Phase 4 (2 weeks) Conversation workspace (gateway-owned conversations, per-turn model, audited context packages).
- Later: audio, images, files/batches, MCP spec 2026-07-28 + OAuth resource metadata, approvals, agent registry/kill switch, A2A, realtime, voice, SASE.

Rough total of all designs: about 118 engineer-days with overlap (agent estimates). Do not try to do it all.

## 6. Test policy going forward
No feature merges without a test through the real pipeline against the fake upstream. New table → RLS isolation test. New exporter → test that an exporter failure never changes the HTTP result. New routing/policy rule → property test that restricted data never reaches an unauthorized model (see `design-specs.md` §B).

## 7. Commands
```bash
cd backend && pip install -r requirements.txt pytest pytest-asyncio pytest-cov ruff
cd backend && python -m pytest -q --cov=app               # unit (+ integration if DATABASE_URL set)
cd backend && alembic heads && alembic upgrade head
cd admin-console && npm ci && npm run typecheck && npm run build && npx vitest run
cd web-app && npm ci && npm run build
```
