---
title: Changelog
description: What's shipped, by phase.
sidebar_position: 100
---

# Changelog

A summary of what's shipped, grouped by build phase. This tracks major capability milestones, not every individual PR.

## Unreleased — November 2026

- **Behavior settings** — ask for `creativity`, `reasoning_depth`, `max_response_length` and `citations` in provider-neutral words (header `x-openproxy-behavior` or a `behavior` field), and set organization defaults and a ceiling in the policy. The ceiling only lowers (and also lowers a caller's own `temperature`, `max_tokens` and `reasoning_effort`), only parameters a model supports are sent, and the request log records what was applied, ignored or lowered. Applies to chat, conversation turns and the playground. See [Behavior Settings](/core-concepts/behavior-settings).
- **Refusals now explain themselves** — a `446` response carries an `explanation`: one plain sentence for an end user ("openai/gpt-4o is not approved for confidential data in your organization."). It names only the model asked for and the request's own data class, never the keyword, pattern, plugin or registry setting involved. The request trace shows what the caller was told, and the policy preview shows what a caller would be told. Existing fields are unchanged.
- **Conversation tags, search and spaces** — tag a conversation, filter the list by tag, search titles and tags (never message content), and file conversations in spaces (`/api/v1/spaces`), optionally shared with a team. A space is a folder, not a permission: it lists only what you could already read and never widens who can read a conversation. The `private` tag (the console's "Keep private") makes a conversation unshareable.
- **Chat and every other endpoint now share one admission step** (policy, classification, routing, team check, refusals, rate limits), so they cannot drift apart. No behavior change for callers.
- **Fixed: chat to a model the gateway cannot price** returned a 502 after the provider had already answered, and a stream's pricing error could leave the call unaudited. Chat now follows the same rule as every other endpoint: the answer is returned and the call is charged a flat fee, marked as an estimate.
- **Realtime API** — `WS /v1/realtime`: the OpenAI Realtime protocol through the gateway. Text you send is checked by your policy before the provider sees it, each response is checked against your limits and billed from the usage the provider reports, the session ends when its key is revoked or time runs out, and sessions per organization are capped. Organizations that enforce response guardrails cannot use it, because a spoken answer cannot be held back. See [Realtime](/api-reference/realtime).
- **Provider keys from AWS Secrets Manager**, beside Vault: `aws_secret_name` in place of a key, inside your organization's folder only, names not ARNs, operator-held credentials, no fallback to another source.
- **Faster authenticated requests** — "last used" on an API key is written at most once a minute instead of on every request, which removes an UPDATE, a commit and a re-select from almost every call. Nothing about who may call is cached: a revoked key, a deactivated user or an expired key still stops at once.
- **Abandoned and broken streams are priced from their tokens**, never at zero, and audited before the stream closes.
- **Files and batches** — `/v1/files` and `/v1/batches`: upload a JSONL file of chat requests and run it as one job. Each line runs through the same governed path as a live request (policy, classification, routing, metering, audit), a bad line is a result and never fails the job, every job has a spending cap, and stored content expires after 7 days.
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
- **Feedback endpoint** — `POST /v1/feedback` lets an application rate an answer (thumbs or a named score, with an optional comment stripped of PII) using its API key. Stored as a request score and linked to the experiment variant when there is one. First slice of the eval loop.
- **Breaking: policy blocks return HTTP 446, not 403.** Requests blocked by policy (PII, keywords, model allowlist) now use the same status as response guardrails. 403 now means only a real authorization failure. The Python and TypeScript SDKs raise `PolicyViolationError` on 446 and still accept a 403 from an older gateway. Raw HTTP clients that check for 403 on blocks must check for 446. Existing log rows keep their old status.
- **Custom provider endpoints** — an `openai` provider key can set `api_base` (any OpenAI-compatible server such as vLLM or Ollama's `/v1`) and a `max_data_class`. Every connection goes through a guard: no redirects are followed, the destination is validated per request and the connection is pinned to it, and TLS is verified against the hostname. External endpoints must be https and public; private or plain-http endpoints need the operator setting `ALLOW_INTERNAL_PROVIDER_ENDPOINTS`.
- **Policy preview** — `POST /api/v1/policy/preview` shows what would happen to a request (class, policy verdict, which model would serve it and why others were ruled out) without sending it: no provider call, no audit row, no budget use. Shows what enforcement would do even while routing is off.
- **Classification-aware routing** — set `routing_mode` to `log_only` to see which registry models would be authorized for each request, then `enforce` to make it binding: a model serves a request only if the registry clears it for the request's data class, and only through its registry key. Requests nothing can serve get HTTP 446. `model: "cap:NAME"` routes chat requests by capability; the opt-in `routing_quality_signal: "feedback"` lets thumbs feedback choose among the authorized models. Applies to chat completions and embeddings.
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
