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

**Not yet in product:** Scoping **gateway API keys** to a single team (see [roadmap](../roadmap.md) team follow-ups).

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

**Create/update validation:** If the org policy has a non-empty **`allowed_models`** list, `target_model` and every variant `model` must appear on that list (400 if not), so misconfiguration is caught early.

**Results:** `GET /api/v1/experiments/{id}/results` aggregates from `request_logs` (per variant: requests, latency, cost, tokens, policy violations).

See also: [API reference — Experiments](../reference/api-reference.md#experiments-ab-testing-api).
