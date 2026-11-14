---
title: "Prompts: playground and promotion"
description: Compare models side by side, save and version prompt templates, and require a passing eval run before an edited prompt goes live.
---

# Prompts: playground and promotion

A prompt template is a saved, versioned prompt that application code calls by `prompt_id` instead of embedding the text. This page shows how to compare models in the playground, create and call templates, and, when a template is production code, make every edit prove itself on an evaluation dataset before it replaces the live version.

## The playground

The **Playground** screen in the admin console has two tabs: **Compare** and **Templates**. Admins and developers can use both. Viewers cannot.

### Compare models

Compare sends the same prompt to two to four models in one call and returns, for each, the answer, token counts, cost, and latency. Use it to decide which model to default a use case to before you commit in production.

```bash
curl -X POST https://your-gateway/api/v1/playground/compare \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{
    "models": ["openai/gpt-4o", "anthropic/claude-sonnet-4-5"],
    "messages": [
      {"role": "system", "content": "You are a support agent."},
      {"role": "user", "content": "Summarize our refund policy in two sentences."}
    ],
    "temperature": 0.2,
    "max_tokens": 300
  }'
```

| Field | Notes |
|---|---|
| `models` | 2 to 4 model names in `provider/model` form. An unknown provider fails the whole call with 400 before any model runs |
| `messages` | At least one message with `role` and `content` |
| `temperature`, `max_tokens` | Optional |
| `behavior` | Optional `creativity`, `reasoning_depth`, `max_response_length`, `citations`. The organization's behavior ceiling can lower them. See [Behavior settings](/core-concepts/behavior-settings) |

Each entry in `results` has `model`, `content`, `prompt_tokens`, `completion_tokens`, `cost_usd`, `latency_ms`, and `error`. One model failing does not fail the others; its entry carries the `error`. The `ttft_ms` field exists but is returned as null.

Compare goes through the same controls as real traffic. The organization policy is evaluated first, so a prompt that violates it is refused with a `policy_violation` error and an explanation. Rate limits apply, and a limit returns 429. If data-class routing is on, a model that is not cleared for the prompt's data class is refused for that model only. See [Policies and guardrails](/core-concepts/policies-and-guardrails).

### Prompt templates

A template has a `name`, optional `description`, an optional `system_message`, a required `user_template`, and an optional `variables_schema`. Variables are written `{{name}}` in either message.

```bash
curl -X POST https://your-gateway/api/v1/prompt-templates \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{
    "name": "Customer support reply",
    "system_message": "You are a polite support agent for {{company}}.",
    "user_template": "Hello {{name}}, regarding order {{order_id}}: ...",
    "variables_schema": [
      {"name": "name", "type": "string", "required": true},
      {"name": "company", "type": "string", "default": "Acme"}
    ]
  }'
```

The response includes the template `id`, `version`, `is_active`, and `status` (`draft`, `active` or `retired`). Other endpoints:

| Endpoint | Purpose |
|---|---|
| `GET /api/v1/prompt-templates` | List active and draft templates |
| `GET /api/v1/prompt-templates/{template_id}` | Fetch one |
| `PUT /api/v1/prompt-templates/{template_id}` | Edit (creates a new version, see below) |
| `GET /api/v1/prompt-templates/{template_id}/versions` | All versions of that prompt, newest first |
| `DELETE /api/v1/prompt-templates/{template_id}` | Delete |

In the console, **Playground, Templates** has the same actions, plus a **Promote** button on drafts.

Call a template from your application by sending `prompt_id` and `variables` instead of `messages`. The two are mutually exclusive, and one of them is required. Missing variables become empty strings, so supply every variable the template uses.

```bash
curl https://your-gateway/v1/chat/completions \
  -H "Authorization: Bearer $OPENPROXY_KEY" -H "Content-Type: application/json" \
  -d '{
    "model": "openai/gpt-4o",
    "prompt_id": "TEMPLATE_UUID",
    "variables": {"name": "Sam", "order_id": "A-1042", "company": "Acme"}
  }'
```

### Versions

With no promotion gate, editing a template creates version N+1 and makes it live at once, and the previous version is retired. Every edit makes a new version rather than overwriting, so you can compare behavior across versions through the versions endpoint. Only an active template can be used as a `prompt_id`; any other id returns 404 `prompt_not_found`.

For structured A/B tests of prompts or models against real traffic, use experiments: `POST /api/v1/experiments`, `POST /api/v1/experiments/{experiment_id}/start`, `GET /api/v1/experiments/{experiment_id}/results`. See [Adaptive experiments](/guides/adaptive-experiments).

## Promoting prompts safely

A template that clients call by `prompt_id` is production code, and a one-line edit can quietly make every answer worse. The **promotion gate** makes an edited prompt prove itself on an [evaluation dataset](/api-reference/datasets) before it replaces the live one. It is **off by default**; with it off, edits go live straight away as described above.

### Turn it on

In the console, open **Govern, Policy, Evaluation** and tick **Require a passing eval run before a prompt goes live**. Or use the API:

```bash
curl -X PATCH https://your-gateway/api/v1/organizations/current/policy \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d '{"prompt_promotion_gate": true, "prompt_gate_min_pass_rate": 0.8, "prompt_gate_min_items": 10}'
```

| Setting | Default | Meaning |
|---|---|---|
| `prompt_promotion_gate` | `false` | Turns the gate on. Sending `null` is refused, so the control cannot be switched off silently |
| `prompt_gate_min_pass_rate` | `0.8` | Share of scored items that must pass. Above 0, up to 1 (the console takes whole percents) |
| `prompt_gate_min_items` | `10` | How many items the run must have scored, so a run of two cannot promote a prompt. From 1 to 100,000 |

Policy changes take effect within 60 seconds, like every other policy setting, and that applies to the gate too.

### The workflow

With the gate on:

1. **An edit makes a draft.** `PUT /api/v1/prompt-templates/{id}` on the live template creates version N+1 with status `draft`. The live version keeps serving. A new template also starts as a draft. A draft cannot be a `prompt_id`; a request for one gets `prompt_not_found`.
2. **Test the draft.** Start an [eval run](/api-reference/eval-runs) with `prompt_template_id` set to the draft's id and no `system_prompt` of its own. The run sends your dataset through the draft's system message and records a fingerprint of the draft's content. The console's promote dialog links straight to this.
3. **Promote it.** `POST /api/v1/prompt-templates/{id}/promote` (admins only) makes the draft live and retires the version it replaces.

There can be one draft per prompt at a time. Editing a draft changes it in place; trying to edit the live version while a draft exists returns 409 `draft_exists`, so edit the draft or promote it first. Each promotion is recorded in the admin audit log as `prompt_template.promoted`.

```bash
curl -X POST https://your-gateway/api/v1/prompt-templates/$DRAFT_ID/promote \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" -d '{}'
```

The response has `template_id`, `name`, `version`, `status`, `previous_version`, `run_id` (the run that vouched for it) and `overridden`.

### What counts as a passing run

All of these must hold for one run of this exact prompt:

- It **completed**. A cancelled run, one stopped by its spending cap, or one that failed never counts.
- It **tested this exact prompt.** If you edit the draft after the run, the run no longer counts and you run it again. A run that used its own `system_prompt` instead of the template's does not count either.
- It **scored at least `prompt_gate_min_items` items**.
- Its **pass rate over scored items is at least `prompt_gate_min_pass_rate`**.
- **No more than a tenth of its items could not be scored.** Otherwise a run where most items errored out could pass on the few that worked.

### Check where a draft stands

```bash
curl https://your-gateway/api/v1/prompt-templates/$DRAFT_ID/promotion \
  -H "Authorization: Bearer $TOKEN"
```

Admins and developers can read this. The response lists `gate_enabled`, the `requirements` (`min_pass_rate`, `min_items`), `passes_gate`, the `qualifying_run`, or the closest run in `best_run` plus `reasons` naming exactly what is missing. If promotion is refused you get 409 `promotion_gate_failed` with the same reasons. Promoting something that is not a draft returns 409 `not_a_draft`.

### Override

When you must ship without a passing run, an admin can override:

```json
{"override": true, "reason": "Customer-facing typo fix; the evaluation set is being rebuilt"}
```

The reason is required (at least 10 characters, at most 500), otherwise the call returns 422 `override_needs_reason`. The promotion is recorded in the audit log as `prompt_template.promoted_with_override` with the reason and what was unmet. In the console, the promote dialog shows an **Override** checkbox when the gate is not met. Asking for an override when the gate is already satisfied is not recorded as one.

### Limits to know about

- **The gate tests the system message.** A run's dataset supplies each item's own messages, so what varies between runs is the system prompt. A template with no system message cannot be vouched for by a run and needs an override. A change to only the `user_template` still invalidates earlier runs, because the fingerprint covers both, but re-running tests the same system message.
- **A run is only as good as its dataset and evaluator.** The gate checks that you ran something and it passed, not that the dataset is representative.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Compare returns 400 | A model name has an unknown provider | Use `provider/model` names from your registry |
| Compare returns a policy violation | The prompt breaks the organization policy | Adjust the prompt, or review the policy |
| `prompt_not_found` on a chat call | The template is a draft, retired, or in another organization | Promote the draft, or use the live id |
| Edit returns `draft_exists` | The gate is on and a draft is waiting | Edit or promote the existing draft |
| `promotion_gate_failed` | No qualifying run | Read `reasons`, run an eval of the draft, or override |
| An earlier passing run stopped counting | The draft changed after the run | Re-run the eval |
| Gate change not visible yet | Policy cache | Wait up to 60 seconds |

## Next steps

- [Eval runs](/api-reference/eval-runs) and [datasets](/api-reference/datasets) to build the evidence the gate checks.
- [Evaluating changes](/admin-console/evaluating-changes) for the console workflow.
- [Managing your organization](/admin-console/managing-your-organization) for the policy screen.
