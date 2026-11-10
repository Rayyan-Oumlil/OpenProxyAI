# Phase 3: the eval loop

Status: started 2026-11-09. Source design: `design-specs.md` §D. This file is the working plan and the status of each slice.

**Goal:** an application can tell the gateway whether an answer was good, the gateway can keep the traffic it is allowed to
keep, score a change against that traffic before shipping it, and pick a winning variant by itself. Everything is opt-in,
org-scoped (row-level security) and written so a failure here never changes an HTTP result for a normal request.

**What exists today:** `POST /api/v1/requests/{id}/scores` needs a JWT user, so an app with an API key cannot send scores;
`request_logs` holds metadata only (no prompt or response text); experiments choose variants by weighted random choice
and never stop; prompt templates are versioned but cannot be promoted.

## Slices
Each slice ships alone, behind its own PR, with tests through the real pipeline or the real database.

| # | Slice | Status |
|---|---|---|
| 1 | `POST /v1/feedback` usable with an API key: idempotent, org-checked, comment redacted of PII | done (PR open) |
| 2 | Opt-in payload capture: sample rate 0 by default, stored only after redaction, expires with audit retention | done (PR open) |
| 3 | Datasets from logged traffic; rows that had PII detected are never imported | todo |
| 4 | Evaluators (exact, regex, LLM judge) and offline eval runs; the judge is metered and policy-checked | todo |
| 5 | Adaptive A/B: variants keyed by `variant_id`, stops with a confidence bound, never below a minimum sample | todo |
| 6 | Promotion gate: a prompt cannot go live without a passing eval run unless an admin overrides (audited) | todo |

Cut from this phase unless asked: the read-only SQL view, `/v1/responses` and `/v1/rerank` (they need a pipeline refactor
and are a separate decision).

## Slice 1 decisions
- **Where a client gets the id:** every response already carries `x-openproxyai-request-id`. Feedback refers to that id.
- **Shape:** `{request_id, score_name = "thumbs", value | thumbs, comment}`. Exactly one of `value` or `thumbs`. Thumbs up is
  `1`, down is `0`, so the mean of a thumbs score is a satisfaction rate (what the adaptive A/B in slice 5 consumes).
- **Idempotent:** one row per `(org, request, score_name)`; sending it again replaces the value.
- **Who may score what:** any key in the same org that has `proxy:llm` may score any request of that org. Not narrowed to the
  same key because keys rotate and feedback often arrives after a rotation. A key in the org can therefore skew scores for the
  org's own traffic; that is accepted for now and written here so it is a decision, not an accident.
- **Comment:** at most 2000 characters, PII-redacted before it is stored (the same detector the policy uses).
- **Not in slice 1:** rate limiting beyond the existing per-key limits. Revisit if feedback is ever exposed to end users directly.
- **Failure mode:** an unknown or other-org request is a 404 with the same body, so a key cannot probe for another org's ids.

## Slice 2 decisions
- **One setting, not two:** `payload_capture_sample_rate` in the policy (0 = off, 1 = every eligible request). The design spec had an enable flag plus a rate; a rate of 0 already means off, so there is one state fewer to get wrong.
- **A ceiling the org cannot raise:** `PAYLOAD_CAPTURE_MAX_DATA_CLASS` (operator env, default `internal`). Stored text is the one place the product keeps what users typed, so an org admin must not be able to start copying `confidential` prompts into a table.
- **Redact first, then cut to size,** so a value split by the cut cannot leave a half-detected fragment.
- **Only role and content are kept.** Tool calls and other extras can carry data the detector never looks at.
- **Expiry follows the plan's `audit_retention_days`;** a job every six hours deletes expired rows, one organization at a time because row-level security is forced.
- **Found while verifying on the real stack:** the purge job returned 0 in a bare process because `PromptTemplate` was never registered in `app/models/__init__.py`. The app process hid it because `main.py` imports everything. Fixed at the root and pinned by a test that imports only `app.models`.
- **Not in this slice:** a console control for the rate (set it through the policy API for now), and reading captured rows (slice 3).
