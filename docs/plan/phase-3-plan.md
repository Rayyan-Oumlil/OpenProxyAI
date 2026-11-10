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
| 3 | Datasets from logged traffic; rows that had PII detected are never imported | done (PR open) |
| 4 | Evaluators (exact, regex, LLM judge) and offline eval runs; the judge is metered and policy-checked | done (PR open) |
| 5 | Adaptive A/B: variants keyed by `variant_id`, stops with a confidence bound, never below a minimum sample | done (PR open) |
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

## Slice 3 decisions
- **Admin only, audited.** Datasets hold copies of prompts, so every route needs an admin and writes to the admin audit log (`dataset.created`, `.imported`, `.deleted`).
- **A copy does not expire.** An item outlives the captured payload it came from, because a test set that vanishes after seven days is useless. It goes when an admin deletes it. This is a retention decision and is written in the API docs.
- **PII is refused twice on import:** rows flagged at capture time are skipped, and every row is scanned again, so a better detector later still catches old rows. Items added by hand that contain PII get a 422 rather than being silently rewritten (rewriting an expected answer would change what the test checks).
- **Already-imported rows are excluded before the limit applies,** so a repeated limited import moves on. A mutation test found this was untested: the database's own uniqueness hid it.
- **Capped at 10,000 items per dataset** to bound storage.
- **Tested against real Postgres** (`tests/test_datasets_db.py`, 29 tests) because the feature is SQL: joins, EXISTS filters, uniqueness, row-level security. Six mutations of the import rules are caught. Dropping the app-level org filter is *not* caught, by design: row-level security is the second wall and still holds.
- **Not in this slice:** a console page for datasets, importing by score ranges across several score names, and exporting a dataset.

## Slice 4 decisions
- **Model calls go through one runner** (`app/services/model_runner.py`): policy first, then routing, then the same key selection chat uses, then an audit-log row with tokens and cost tagged `source=eval_run` or `eval_judge`. A refusal is an outcome, not an exception, so one bad item cannot abort a run. **Follow-up debt:** the playground still has its own copy of this sequence (`routes/playground.py`); moving it onto the runner is worth doing but is a refactor of tested, differently shaped code, so it is not part of this slice.
- **A run is background work with a spending cap.** `max_cost_usd` (default $1, max $50) covers candidate and judge calls together; reaching it ends the run `budget_exceeded` and no new item starts (the few in flight finish, so it can overshoot by about four items). At most 2 active runs per org, 500 items per run, 4 items at a time.
- **An item that could not be scored is an error with a reason, never a zero,** and is left out of the mean and pass rate (`scored_items` vs `failed_items`). A judge that refuses, fails or answers badly is the same. Treating errors as zeros would punish a candidate for a broken evaluator.
- **Regex evaluators are the one place an admin's text runs against model output,** so they use the `regex` package with a 1 s timeout in a worker thread. Stdlib `re` cannot be interrupted. A test uses `^(a|aa)+$`, which is genuinely catastrophic in this engine (the usual `(a+)+$` is optimized away and would not prove anything).
- **The judge prompt treats everything as data:** criteria, question, reference and answer sit in delimited sections, closing tags inside them are defused, and the judge is told never to obey them. Judge replies must be a clean whole-number score in range.
- **A run keeps a copy of its evaluator** so deleting or changing the evaluator later does not make an old result unreadable.
- **Cancel is a status change** that each item checks before it starts; a cancel that arrives first is never overwritten by completion.
- **A sweeper** ends runs stuck active for over three hours (the process that held them died).
- **Not done:** rate limiting a run against the org's daily budget (the per-run cap is the guard for now), a console page, and comparing two runs side by side.
- **Tested** with the model calls scripted and everything else real on Postgres (`tests/test_eval_runs_db.py`, 32 tests, plus unit tests for the runner and evaluators). Eight mutations of the run rules are caught. `scripts/smoke_evals.py` runs the whole thing on a real stack, including a deterministic fake judge.

## Slice 5 decisions
- **Method:** each variant's rate (thumbs, or any score in 0 to 1) has a Beta posterior; the chance each is best comes from sampling it (10,000 draws, seeded so a decision can be reproduced). Traffic follows that chance, never below a floor (default 5%). It stops, naming a winner, when one is best with probability at least `1 - delta`.
- **Nothing is decided early:** weights are untouched and no winner is named until every variant has `min_samples_per_variant` ratings (default 30, hard floor 20, enforced in the statistics, in the API and in a database check constraint).
- **The default `delta` is 0.01, not the textbook 0.05, because of a measurement.** The rule is looked at repeatedly as ratings arrive, which inflates false stops. Simulated (a look every 10 ratings, up to 400 per variant, 120 trials): for two *equal* variants, delta 0.05 names a "winner" in 38% to 43% of trials; delta 0.01 in about 13%. For a real 0.7 vs 0.5 gap both pick the better one 119 of 120 times. The docs say this plainly. A false winner between equal variants costs nothing (either is as good), but it is stated, not hidden.
- **A winner is recorded, never deployed.** Stopping ends the split (requests return to the target model) and sets `winner_variant_id`. The model serving production traffic is changed only by a human.
- **A metric that is not a rate is an error, not a guess:** values outside 0 to 1 leave the experiment untouched and set `adaptive_error`, which the results endpoint shows.
- **Results are keyed by variant id, not model name.** Two variants on the same model used to collapse into one row. Rows logged before variants carried ids are matched by model only when that is unambiguous.
- **Variants now have a stable order** (by id). Before, the API listed them in whatever order Postgres returned; the flaky test that exposed this had been comparing list positions.
- **Audit:** weight changes and the winner are written by `system:adaptive-ab` (no human actor).
- **Not done:** a console view, more than a rate as the metric (for example a 1 to 5 score would need normalizing), and a sequential test that corrects for repeated looks properly (the measured default is the pragmatic answer for now).
- **Tested:** 24 unit tests of the statistics including a property test and simulations, and 26 real-Postgres tests of the API, the job and the results. Ten mutations are caught. `scripts/smoke_adaptive.py` runs the real job inside the API container on a real stack.
