---
title: Evaluators and eval runs
description: Score a model on a dataset with exact match, a regex or an LLM judge, with a spending cap.
---

# Evaluators and eval runs

An **evaluator** says how an answer is scored. An **eval run** sends every item of a [dataset](/api-reference/datasets) to a candidate model, scores each answer with an evaluator, and reports the average and the pass rate. Use it to compare a prompt or a model before you ship it.

Everything here is **admin only** (an organization admin's JWT) and recorded in the admin audit log. A run spends real money, so it has a cost cap, and at most two runs can be active per organization.

## Evaluators

```
/api/v1/evaluators
```

| Method | Path | |
|---|---|---|
| `POST` | `/api/v1/evaluators` | Create. Body: `{"name": "...", "type": "exact" \| "regex" \| "llm_judge", "config": {...}}`. 422 `invalid_evaluator` says what is wrong; 409 if the name is taken. |
| `GET` | `/api/v1/evaluators` | List. |
| `GET` | `/api/v1/evaluators/{id}` | One evaluator. |
| `DELETE` | `/api/v1/evaluators/{id}` | Delete (204). Finished runs keep a copy of the evaluator they used. |

### `exact`

The answer must equal the item's expected answer. Config: `case_sensitive` (default `false`) and `strip` (default `true`, ignores whitespace at the ends). An item with no expected answer is reported as an **error** on that item, not as a failure.

### `regex`

The answer must match a pattern. Config: `pattern` (required, up to 200 characters), `mode` (`search`, the default, or `fullmatch`), `ignore_case` (default `false`).

Patterns run with a one-second timeout in a worker thread, so a pattern that backtracks catastrophically ends in an error on that item and does not slow the service.

### `llm_judge`

Another model grades the answer against your written criteria. Config:

| Field | |
|---|---|
| `model` | Required, `provider/model`. Must be on your model allowlist if you have one. |
| `criteria` | Required, up to 2000 characters: what a good answer is. |
| `scale` | `1-5` (default) or `pass_fail`. |
| `pass_threshold` | With `1-5`: the lowest score that counts as a pass (1 to 5, default 4). |

The judge is called through the gateway like any other model call: your policy applies to it, routing applies if it is on, and the call is metered and appears in the request logs with `source` set to `eval_judge`. The question, reference answer and answer are passed to the judge as delimited data it is told never to obey, and a closing tag inside an answer cannot end its section early.

If the judge is refused by policy, fails, or replies with something that is not a clean score, that item is an **error**, never a silent zero.

## Eval runs

```
/api/v1/eval-runs
```

| Method | Path | |
|---|---|---|
| `POST` | `/api/v1/eval-runs` | Start a run (202). It executes in the background. |
| `GET` | `/api/v1/eval-runs` | List, newest first. `limit` and `offset`. |
| `GET` | `/api/v1/eval-runs/{id}` | Progress and results. |
| `GET` | `/api/v1/eval-runs/{id}/items` | Per-item results. `outcome` filters: `passed`, `failed` (scored below the bar) or `error` (could not be scored). |
| `POST` | `/api/v1/eval-runs/{id}/cancel` | Stop a run. Items already in flight finish; no new item starts. |

### Starting a run

```json
{
  "dataset_id": "…",
  "evaluator_id": "…",
  "candidate_model": "openai/gpt-4o-mini",
  "system_prompt": "You are a concise support agent.",
  "max_items": 100,
  "max_cost_usd": 1.0
}
```

- `candidate_model` is the model being tested, `provider/model`.
- `system_prompt` is put before each item's messages. Alternatively give `prompt_template_id` and the template's system message is used (an explicit `system_prompt` wins).
- `max_items` (1 to 500, default 100) caps how many dataset items run.
- `max_cost_usd` (0.01 to 50, default 1.00) caps spending on candidate and judge calls together. Once it is reached no new item starts and the run ends as `budget_exceeded`. The few items already in flight finish, so the final cost can pass the cap by about four items' worth.

Refused with: 404 for an unknown dataset, evaluator or template; 422 `empty_dataset`; 422 `model_not_allowed` if the candidate or the judge is not on your allowlist; 409 `too_many_runs` when two runs are already active.

### Reading a run

```json
{
  "id": "…",
  "status": "completed",
  "candidate_model": "openai/gpt-4o-mini",
  "evaluator": {"name": "exact-match", "type": "exact", "config": {"case_sensitive": false, "strip": true}},
  "total_items": 100, "completed_items": 100, "scored_items": 97, "failed_items": 3, "passed_items": 81,
  "mean_score": 0.8350, "pass_rate": 0.8351,
  "cost_usd": 0.18, "max_cost_usd": 1.0
}
```

`status` is `queued`, `running`, `completed`, `failed`, `cancelled` or `budget_exceeded`.

**Average and pass rate are over the items that could be scored.** An item that was refused by policy, that the provider failed on, or that the evaluator could not score is counted in `failed_items` and shown with its reason under `outcome=error`, but left out of both, so a handful of broken items does not drag a good result down. Check `failed_items` before you trust a number.

Scores are 0 to 1 for every evaluator: exact and regex give 0 or 1, and a `1-5` judge score is mapped to `(score - 1) / 4`.

A run left active for more than three hours (for example because the service restarted) is ended as `failed` by a job that runs hourly.

## What a run costs and where it shows

Each candidate call and each judge call is an ordinary logged request, tagged in its metadata with `source` (`eval_run` or `eval_judge`) and `eval_run_id`, so it counts in spend and appears in the request logs.
