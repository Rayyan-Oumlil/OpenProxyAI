# Phase 5: the rest of the API surface, telemetry and extensibility

Status: started 2026-11-11, after Phases 0-4 (`phase-3-4-finish.md`). Covers what the original plan (`design-specs.md` §C, §D, `roadmap.md`) left unbuilt. Not in scope, still held for the owner: pricing, Stripe changes, a domain, a hosted demo, GCP.

## The rule that shapes the order
Chat and embeddings each carry their own copy of the same sequence: policy, classification, routing, rate limit, key choice, upstream call with fallback, metering, audit log. Embeddings alone is about 200 lines of it. Five more endpoints copied the same way would mean six copies of the code that decides what may reach a provider. So the first slice moves **embeddings onto a shared pipeline with a small per-endpoint adapter** (its existing tests are the safety net), and every new endpoint after it is an adapter plus its tests. Chat stays as it is: streaming, tools, cache and experiments make it a different shape, and moving it is a separate, riskier job.

An adapter supplies: how to read the text that policy and classification must see (`extract_text`), how to estimate tokens, how to call LiteLLM, how to read usage and cost, whether the answer is cacheable (none of the new ones are), and what must stay out of the audit log.

## Slices
| # | Slice | Notes |
|---|---|---|
| 5.1 | Shared pipeline; embeddings moved onto it | No behaviour change. Existing embedding tests plus a new equivalence suite. |
| 5.2 | `POST /v1/rerank` | Query and documents are text: policy, classification and routing apply to all of it. |
| 5.3 | `POST /v1/images/generations` | Prompt is checked like any text. Never cached. `b64_json` is kept out of logs. |
| 5.4 | `POST /v1/audio/transcriptions` and `/v1/audio/speech` (this is the "voice endpoint") | Audio in is multipart: size cap, content type check. The transcript is checked against policy on the way back, since that is where the text appears. Speech input is checked like any prompt. |
| 5.5 | `POST /v1/responses` | Provider-side state (`previous_response_id`, `store=true`) is blocked by default: it keeps data at the provider and conflicts with residency. A policy flag allows it. |
| 5.6 | Files and batches | `batch_jobs` table, a poll job, every line scanned by policy, budget reserved up front. Largest slice. |
| 5.7 | OpenTelemetry export | **Already built in Phase 1** (`services/telemetry.py`). Found on checking: spans said `chat` for every call, now named for the operation; added the user-facing doc it lacked. |
| 5.8 | SIEM export | **Already built in Phase 1** (CEF/JSON to stdout, file, syslog). Documented. |
| 5.9 | Read-only SQL view | A tightly scoped read path over the org's own logs for analysts. Design below. |
| 5.10 | Secrets from Vault | Provider keys can be fetched from HashiCorp Vault (KV v2) instead of being stored encrypted in Postgres. |
| 5.11 | WASM policy plugins | An org-supplied module can add a verdict to the policy check. Design below; the riskiest slice. |
| 5.12 | Scores API | `/v1/feedback` already covers writing scores with an API key. Adds the missing read side: query scores by request, model, name and time. |

## Designs that need stating up front
**SQL view (5.9).** Not free-form SQL against the database. A fixed set of read-only views (`v_requests`, `v_scores`, `v_spend`) over the org's own rows, queried through a restricted, parsed subset (SELECT only, one statement, allowlisted views and columns, row and time limits, a statement timeout) on a dedicated read-only role that has RLS forced and no access to other tables. Admin only, every query written to the admin audit log. If a safe parser cannot be made small enough to trust, the fallback is saved named queries with parameters rather than arbitrary text.

**WASM plugins (5.11).** A plugin is a pure function from text to a verdict (`allow`, `block` with a reason, or `tag`). Runs under wasmtime with no WASI (no files, no network, no clock), a hard memory limit and an instruction budget ("fuel"), so a bad module can only fail, never reach anything. It runs after the built-in policy and can only add restrictions: it cannot override a block. Uploaded by admins, hashed, versioned, and every change audited. A module that traps, times out or exceeds its limits fails closed for the org's `enforce` mode and is recorded. New dependency (`wasmtime`) to be vetted for supply-chain risk first.

**Vault (5.10).** A provider key row can say "fetch from Vault path X" instead of holding ciphertext. Read through Vault's HTTP API with a token or AppRole from the operator's environment (never stored in the org's data); cached briefly; a failure to reach Vault fails hard for that key (no silent fallback to another key), and the secret value is never logged.

## Working rules
Spec first, tests first, a real-stack smoke script per slice, mutation checks on every rule that guards data, dated docs, one PR per slice with CI green before merge. Anything that sends content to a provider goes through policy, classification, routing and the audit log, with a test that the provider received only what was allowed.
