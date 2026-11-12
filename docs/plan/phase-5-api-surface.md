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
| 5.6 (done, #78) | Files and batches | Built as a gateway-run job, not a forwarded provider batch: every line goes through the governed runner, so policy, routing, metering and audit apply per line on any provider. Spending cap, daily-budget and owner checks per line, cancel, janitor, expiring content. |
| 5.7 | OpenTelemetry export | **Already built in Phase 1** (`services/telemetry.py`). Found on checking: spans said `chat` for every call, now named for the operation; added the user-facing doc it lacked. |
| 5.8 | SIEM export | **Already built in Phase 1** (CEF/JSON to stdout, file, syslog). Documented. |
| 5.9 | Read-only query (built as a structured query, not SQL text) | See the decision below. |
| 5.10 | Secrets from Vault | Provider keys can be fetched from HashiCorp Vault (KV v2) instead of being stored encrypted in Postgres. |
| 5.11 | WASM policy plugins | An org-supplied module can add a verdict to the policy check. Design below; the riskiest slice. |
| 5.12 | Scores API | `/v1/feedback` already covers writing scores with an API key. Adds the missing read side: query scores by request, model, name and time. |

## Designs that need stating up front
**SQL view (5.9).** Not free-form SQL against the database. A fixed set of read-only views (`v_requests`, `v_scores`, `v_spend`) over the org's own rows, queried through a restricted, parsed subset (SELECT only, one statement, allowlisted views and columns, row and time limits, a statement timeout) on a dedicated read-only role that has RLS forced and no access to other tables. Admin only, every query written to the admin audit log. If a safe parser cannot be made small enough to trust, the fallback is saved named queries with parameters rather than arbitrary text.

**WASM plugins (5.11).** A plugin is a pure function from text to a verdict (`allow`, `block` with a reason, or `tag`). Runs under wasmtime with no WASI (no files, no network, no clock), a hard memory limit and an instruction budget ("fuel"), so a bad module can only fail, never reach anything. It runs after the built-in policy and can only add restrictions: it cannot override a block. Uploaded by admins, hashed, versioned, and every change audited. A module that traps, times out or exceeds its limits fails closed for the org's `enforce` mode and is recorded. New dependency (`wasmtime`) to be vetted for supply-chain risk first.

**Vault (5.10).** A provider key row can say "fetch from Vault path X" instead of holding ciphertext. Read through Vault's HTTP API with a token or AppRole from the operator's environment (never stored in the org's data); cached briefly; a failure to reach Vault fails hard for that key (no silent fallback to another key), and the secret value is never logged.

## Working rules
Spec first, tests first, a real-stack smoke script per slice, mutation checks on every rule that guards data, dated docs, one PR per slice with CI green before merge. Anything that sends content to a provider goes through policy, classification, routing and the audit log, with a test that the provider received only what was allowed.

## Decisions made while building (2026-11-11)
- **5.11 WASM:** `wasmtime` pinned (50.0.1). Found by test: pytest's `faulthandler` overrode wasmtime's signal handlers and crashed the process on the first trap; traps are now implemented without signals (`signals_based_traps = False`), which is the right setting for any host that has its own handlers. Mutation checks found a too-weak memory-limit test and a cached-policy path that would have lost the org id (and so silently disabled plugins for a minute); both fixed with tests.
- **5.9 is a structured query, not SQL text.** The plan allowed this fallback. Parsing arbitrary SQL safely on a shared database means trusting a parser completely; a structured spec has nothing to parse. Every choice is looked up in an allowlist, every value is bound, free-text columns are not exposed, and it runs read-only with a timeout and an audit entry. Raw SQL can be added later behind a vetted parser if analysts need joins.
- **5.7 and 5.8 already existed** (Phase 1). The work was a bug (every span said `chat`) and the missing documentation.
- **5.10 Vault:** a path is valid only inside the org's own folder (`VAULT_PATH_PREFIX`), checked at creation and on every read, because the gateway holds one Vault credential for all orgs. A test found a trailing-newline hole in the first regex (`$` accepts one); `fullmatch` now.
- **5.2-5.5:** audio is uninspected input (classified confidential unless the class map says otherwise); `/v1/responses` always sends `store=false` and refuses provider state and provider-run tools unless allowed. Seven issues from the automatic security review were fixed along the way (see the PR).

## Status (2026-11-12): complete
Everything in this plan is built and merged (#77, #78). Also finished from the earlier phases' leftovers: conversation retention (idle past the plan's audit retention), personas, org-wide sharing (admin only), the `log_only` preview, streaming (SSE; refused for orgs with response guardrails), and console screens for policy plugins, the analytics query and scores.

Deliberately held for the owner: Stripe/pricing, a domain, the hosted demo and its video, GCP, outreach emails, and the three open upstream PRs' forks.
Also built since (#81, #82, #83): AWS Secrets Manager beside Vault; the once-a-minute `last_used_at` write (authorization is still checked on every request, nothing about who may call is cached); the realtime API (`WS /v1/realtime`, `docs-site/docs/api-reference/realtime.md`).

Chat and the shared pipeline: **not merged into one function, on purpose.** Chat has its own order (experiments, cache, templates, tool taint, streaming, fallback model) and forcing it through `Modality` would make that type carry every one of those. What stops the two drifting is `tests/test_chat_parity.py`, which asks chat the questions `test_modalities_pipeline.py` asks every modality. It found a real bug on its first run: a successful chat call to a model LiteLLM cannot price returned 502 (and a stream's pricing error escaped its close, leaving the spend uncounted). Both now use `cost_tracker_service.price_or_fallback`, the same flat-fee rule as every other endpoint.

Not built, by design: raw SQL (the structured query replaces it).
