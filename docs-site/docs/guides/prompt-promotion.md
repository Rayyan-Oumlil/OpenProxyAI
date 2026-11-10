---
title: Promoting prompts safely
description: Require a passing eval run before an edited prompt template goes live.
---

# Promoting prompts safely

A prompt template that clients call by `prompt_id` is production code. A one-line edit can quietly make every answer worse. The **promotion gate** makes an edited prompt prove itself on an [evaluation dataset](/api-reference/datasets) before it replaces the live one.

It is **off by default**: with it off, editing a template makes the new version live straight away, as before.

## Turn it on

```bash
curl -X PATCH https://your-gateway/api/v1/organizations/current/policy \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d '{"prompt_promotion_gate": true, "prompt_gate_min_pass_rate": 0.8, "prompt_gate_min_items": 10}'
```

| Setting | Default | |
|---|---|---|
| `prompt_promotion_gate` | `false` | Turn the gate on. Sending `null` is refused: it would otherwise switch the control off silently. |
| `prompt_gate_min_pass_rate` | `0.8` | The share of scored items that must pass. Above 0, up to 1. |
| `prompt_gate_min_items` | `10` | How many items the run must have scored, so a run of two cannot promote a prompt. |

Policy changes take effect within 60 seconds, like every other policy setting.

## How it works

With the gate on:

1. **An edit makes a draft.** `PUT /api/v1/prompt-templates/{id}` on the live template creates version N+1 as a `draft`. The live version keeps serving. A new template also starts as a draft. A draft cannot be used as a `prompt_id`; a request for one gets `prompt_not_found`.
2. **You test the draft.** Start an [eval run](/api-reference/eval-runs) with `prompt_template_id` set to the draft's id, and no `system_prompt` of its own. The run sends your dataset through the draft's system message and records a fingerprint of the draft's content.
3. **You promote it.** `POST /api/v1/prompt-templates/{id}/promote` (admins only) makes the draft live and retires the version it replaces.

There can be one draft per prompt at a time. Editing a draft changes it in place.

## What counts as a passing run

All of these must hold for one run of **this exact prompt**:

- It **completed**. A cancelled run, one stopped by its spending cap, or one that failed never counts.
- It **tested this exact prompt.** If you edit the draft after the run, the run no longer counts and you run it again. A run that used its own `system_prompt` instead of the template's does not count either.
- It **scored at least `prompt_gate_min_items` items**.
- Its **pass rate over scored items is at least `prompt_gate_min_pass_rate`**.
- **No more than a tenth of its items could not be scored.** Otherwise a run where most items errored out could pass on the few that happened to work.

`GET /api/v1/prompt-templates/{id}/promotion` tells you where a draft stands. It lists the requirements, the run that qualifies, or the closest run and exactly what it is missing, so you never have to guess.

If promotion is refused you get `409 promotion_gate_failed` with the same reasons.

## Override

When you have to ship without a passing run, an admin can override:

```json
{"override": true, "reason": "Customer-facing typo fix; the evaluation set is being rebuilt"}
```

The reason is required (at least 10 characters), and the promotion is recorded in the admin audit log as `prompt_template.promoted_with_override` with the reason and what was unmet. Asking for an override when the gate is already satisfied is not recorded as one.

## Limits to know about

- **The gate tests the system message.** A run's dataset supplies each item's own messages, so what varies between runs is the system prompt. A template with no system message cannot be vouched for by a run, so it needs an override. A change to only the `user_template` still invalidates earlier runs (the fingerprint covers both), but re-running tests the same system message.
- **A run is only as good as its dataset and evaluator.** The gate checks that you ran something and it passed, not that the dataset is representative.
- **The 60-second policy cache applies to the gate too.** A change to the gate settings can take up to a minute to be seen.
