# Experiments & teams

How **model A/B experiments** and **teams** fit together with the gateway and admin console.

---

## Teams

**Purpose:** Group users inside an org for departmental structure and optional **monthly budget** per team (`budget_monthly_usd`).

**Admin console:** **Teams** page — create/edit teams, add or remove members, set budgets.

**API:** Base path `/api/v1/teams` (JWT session from admin login — not the gateway API key). **All team endpoints require the `admin` role.**

| Method | Path | Notes |
|--------|------|--------|
| `GET` | `/api/v1/teams` | List teams + member counts |
| `POST` | `/api/v1/teams` | Create team |
| `GET` | `/api/v1/teams/{id}` | Detail + members |
| `PATCH` | `/api/v1/teams/{id}` | Update |
| `DELETE` | `/api/v1/teams/{id}` | Delete |
| `POST` | `/api/v1/teams/{id}/members/{user_id}` | Add member |
| `DELETE` | `/api/v1/teams/{id}/members/{user_id}` | Remove member |

**Gateway header (optional):** `x-openproxy-team-id: <uuid>` on `POST /v1/chat/completions` (and embeddings) to attach team context for logging/metadata. The team must exist in the org and the **API key’s user** must be a member (see backend validation).

**Team-scoped API keys:** Gateway API keys can optionally be tied to a team. When creating a key in the admin console, admins can select a team; the creating user must be a member. Keys with `team_id` propagate team context to all requests (logging, rate limits, analytics). See [cost-management.md](./cost-management.md) for team budgets and `per_team_limits`.

---

## Experiments (model A/B)

**Purpose:** For a given **target model** string (what clients send in `model`), the gateway can randomly route to **variant** models by traffic weight, log which variant ran, and expose aggregate metrics.

**Admin console:** **Experiments** page — define variants, start/stop, view results.

**API:** `/api/v1/experiments` (JWT). Mutations (create/update/delete/start/stop) are **admin only**. List/get/results are available to authenticated org members.

**Proxy behavior:**

1. Client calls `POST /v1/chat/completions` with `model` equal to the experiment’s **`target_model`**.
2. If an **active** experiment matches, the gateway may replace the model with a **variant** for that request.
3. **Policy** (model allowlist) is evaluated on the **resolved** variant — variants not on the allowlist are blocked like any other model.
4. Request metadata records experiment id / variant for analytics and the **results** endpoint.

Chat completions can use either `messages` (standard) or `prompt_id` + `variables` (saved Playground templates); see [API reference — chat completions](../reference/api-reference.md#post-v1chatcompletions).

**Create/update validation:** If the org policy has a non-empty **`allowed_models`** list, `target_model` and every variant `model` must appear on that list (400 if not), so misconfiguration is caught early.

**Results:** `GET /api/v1/experiments/{id}/results` aggregates from `request_logs` (per variant: requests, latency, cost, tokens, policy violations) and includes **quality scores** when submitted via the Request Scores API or the eval hook.

**Eval hook (LLM-as-judge / external callback):** When an experiment variant completes a request, the gateway can optionally call an eval hook to compute quality scores. Configure via env:

- **`EVAL_HOOK_URL`** — HTTP POST URL. Gateway sends `{prompt, response, request_id}`; hook returns `{scores: [{name, value}]}` or `{score: n}`.
- **`EVAL_LLM_MODEL`** — e.g. `openai/gpt-4o`. Uses LLM-as-judge: prompt+response are sent to the model with a rating instruction; reply is parsed as a 1–5 score (stored as `quality`).

Both run as fire-and-forget background tasks. **Fail-open:** if the hook or LLM fails, the request succeeds and no score is stored. Scores are persisted via the Request Scores API and appear in experiment results.

See also: [API reference — Experiments](../reference/api-reference.md#experiments-ab-testing-api), [Request Scores API](../reference/api-reference.md#request-scores-api).
