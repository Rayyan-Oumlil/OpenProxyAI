---
title: Changelog
description: What's shipped, by phase.
sidebar_position: 100
---

# Changelog

A summary of what's shipped, grouped by build phase. This tracks major capability milestones, not every individual PR.

## Unreleased — November 2026

- **Policy plugins (WebAssembly)** — `/api/v1/policy-plugins` (admins): add your own rule to the policy check as a sandboxed module. No imports (nothing to call), bounded time and memory, a fresh instance per call, text over 256 KB refused rather than cut; a plugin can only add a restriction, never lift one, and one that fails blocks under `enforce`. Runs on chat and every other endpoint. Wasmtime, with signal-free traps and the features a rule does not need switched off.
- **Analytics query** — `POST /api/v1/analytics/query` (admins): filters, group-bys and aggregates over your own request log and scores, from a structured query rather than SQL text, so every column, operator and aggregate is allowlisted and every value is a bound parameter. Read-only transaction, 5-second timeout, every query in the admin audit log, no free-text columns, and always limited to your own organization.
- **Provider keys from Vault** — a provider key can point at a HashiCorp Vault KV v2 secret (`vault_path`) instead of holding a stored copy. Each org may use only its own folder (`VAULT_PATH_PREFIX`), enforced at creation and on every read; https is required, redirects are refused, a failure to read is an error for that key and never a fallback, and the value is never logged or returned.
- **Reading scores** — `GET /api/v1/scores` (admins) and `/summary` (admins and developers, aggregates only).
- **OpenTelemetry and SIEM export documented**, and spans are now named for the operation (`embeddings`, `image_generation`, ...) instead of always `chat`.
- **More endpoints: rerank, images, audio, Responses** — `POST /v1/rerank`, `/v1/images/generations`, `/v1/audio/transcriptions`, `/v1/audio/speech` and `/v1/responses`, all through one shared request pipeline (embeddings moved onto it) so policy, classification, routing, rate limits, metering and audit cannot differ between endpoints. Audio is uninspected input (classified confidential unless your class map says otherwise); uploads are size-checked before the body is read; transcripts and response text, including function-call arguments and verbose segments, go through response guardrails. Responses always sends `store=false`, refuses provider-side state and provider-run tools unless an admin allows them, and rejects unknown fields. A model LiteLLM cannot price is charged a flat fallback instead of nothing. Chat and streaming are unchanged.
- **Conversations** — `/api/v1/conversations` and a Conversations page: keep a thread in the gateway and switch models mid-way. Before each message the gateway decides which earlier messages the chosen model is cleared for (an exchange is sent whole or not at all; an answer takes the class of everything the model saw), holds the rest back and says so, and refuses a message the model is not cleared to read instead of answering blind. Every answer has an append-only record of what was sent, with a SHA-256 of the exact messages. Off by default (`conversations_enabled`). Private or shared with a team; an admin sees titles and sizes, never another user's messages. The playground now runs on the same model runner as eval runs, and drawers opened from a button return focus to it on close.
- **Console for the eval loop** — an Evaluate group (Datasets, Evaluators, Eval runs with live progress), an Evaluation tab on Policy for capture and the promotion gate, adaptive settings and results on Experiments, and a promotion dialog for draft prompts. Also fixed: dialogs opened from a button now return focus to it on close; the Experiments results toggle's visible text matches its accessible name; the policy badge meets AA contrast in the light theme.
- **Prompt promotion gate** — set `prompt_promotion_gate` in the policy and an edited prompt template becomes a draft instead of going live. An admin promotes it with `POST /api/v1/prompt-templates/{id}/promote`, which needs an eval run of that exact prompt that completed, scored enough items, passed at the configured rate and did not hide errors; or an override with a written reason, audited. Off by default. Last slice of the eval loop.
- **Adaptive A/B experiments** — set `mode: adaptive` and a feedback `metric` on an experiment: a job moves traffic toward the better variant as ratings arrive (never below a floor, never before every variant has enough ratings) and stops the test, naming a winner, when one is clearly best. The winner is recorded, never deployed automatically. Experiment results are now keyed by variant, so two variants on the same model no longer collapse into one row. Fifth slice of the eval loop.
- **Evaluators and eval runs** — `/api/v1/evaluators` and `/api/v1/eval-runs` (admins only): score a candidate model on a dataset with exact match, a regex (run with a timeout) or an LLM judge. Judge and candidate calls go through the gateway's own policy, routing and metering, a run has a spending cap, and an item that could not be scored is an error with a reason, never a zero. Fourth slice of the eval loop.
- **Datasets** — `/api/v1/datasets` (admins only): build a named set of prompts from captured traffic, filtered by model, date and feedback score, or add items by hand. Rows with personal data are never imported and hand-written items containing it are refused. Third slice of the eval loop.
- **Payload capture (opt-in)** — set `payload_capture_sample_rate` in the policy to keep a redacted sample of prompts and answers for evaluation. Off at 0 (the default). PII is replaced before storage, requests above the data-class ceiling (default `internal`) are never kept, and rows expire with the plan's audit retention. Second slice of the eval loop.
- **Feedback endpoint** — `POST /v1/feedback` lets an application rate an answer (thumbs or a named score, with an optional comment stripped of PII) using its API key. Stored as a request score and linked to the experiment variant when there is one. First slice of the eval loop; see `docs/plan/phase-3-plan.md`.
- **Breaking: policy blocks return HTTP 446, not 403.** Requests blocked by policy (PII, keywords, model allowlist) now use the same status as response guardrails. 403 now means only a real authorization failure. The Python and TypeScript SDKs raise `PolicyViolationError` on 446 and still accept a 403 from an older gateway. Raw HTTP clients that check for 403 on blocks must check for 446. Existing log rows keep their old status.
- **Custom provider endpoints** — an `openai` provider key can set `api_base` (any OpenAI-compatible server such as vLLM or Ollama's `/v1`) and a `max_data_class`. Every connection goes through a guard: no redirects are followed, the destination is validated per request and the connection is pinned to it, and TLS is verified against the hostname. External endpoints must be https and public; private or plain-http endpoints need the operator setting `ALLOW_INTERNAL_PROVIDER_ENDPOINTS`.
- **Policy preview** — `POST /api/v1/policy/preview` shows what would happen to a request (class, policy verdict, which model would serve it and why others were ruled out) without sending it: no provider call, no audit row, no budget use. Shows what enforcement would do even while routing is off.
- **Classification-aware routing** — set `routing_mode` to `log_only` to see which registry models would be authorized for each request, then `enforce` to make it binding: a model serves a request only if the registry clears it for the request's data class, and only through its registry key. Requests nothing can serve get HTTP 446. `model: "cap:NAME"` routes chat requests by capability. Applies to chat completions and embeddings.
- **PII detection hardened** (blocking, redaction and classification share one detector): text is normalized before it is read, so fullwidth digits, `＠` and zero-width characters no longer hide PII; SSNs with spaces or dots are found; a 13-19 digit number is only a payment card if it passes the Luhn checksum, and an SSN must be a number that could be issued, so order numbers and version strings stop triggering blocks.
- **Data classification** — each request is classified `public` < `internal` < `confidential` < `secret` from the org default, an `x-openproxy-data-class` header (raise only) and detected PII; returned as `X-OpenProxyAI-Data-Class` and recorded on the request trace. Informational for now; routing will use it next.
- **Model registry** — `GET/POST/PATCH/DELETE /api/v1/model-registry` (admins only): per-model data class, regions, risk rating, retention, capabilities, linked provider key. Administration only for now; routing does not use it yet.
- **Admin console** — command palette (Ctrl/Cmd+K) with theme switching, breadcrumbs, spend by API key, shared tables, tabbed policy page, keyboard and axe accessibility audits.
- **Seeded demo** — `docker compose -f docker-compose.demo.yml up`, with prebuilt images published to GHCR and a recorded walkthrough.

## Phase 7 — 2026-03-19

- **Semantic caching** — 3-tier cache (L1 in-memory, L2 Redis, L3 pgvector semantic), per-request override header, dashboard metrics
- **Prompt playground** — side-by-side model comparison (TTFT, latency, tokens, cost), prompt template CRUD with versioning
- **`GET /v1/models`** — OpenAI-compatible model list built from your org's configured provider keys
- **Data residency (Tier 1)** — region field on provider keys, `data_region` on organizations, routing filtered by region
- **Compliance templates** — Healthcare/HIPAA, Finance/PCI, Government/FedRAMP-aligned policy presets with merge semantics

## Phase 3–6

- Observability: Langfuse tracing, Prometheus metrics, ClickHouse analytics dual-write, outbound webhooks
- Security hardening: prompt-injection detection, response guardrails, PII redaction, SSRF protection
- Billing: Stripe checkout, customer portal, webhook handling, plan-based feature gating
- Public deployment: Docker Compose for local dev, Helm chart for Kubernetes, GitHub Actions CI/CD

## Phase 1–2

- Core proxy: auth, rate limiting, policy hooks, provider routing, async audit logging
- Admin console, invite system, plan enforcement
- OIDC/SSO, immutable audit log
- Python and TypeScript SDKs

---

:::info Granular release notes coming soon
This page currently tracks phase-level milestones. A per-version changelog with dates and PR links is planned once release cadence stabilizes.
:::
