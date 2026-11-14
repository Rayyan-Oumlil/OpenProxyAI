---
title: Organizations, teams and users
description: Manage your organization settings, policy, webhooks, teams, invites and users through the management API.
---

# Organizations, teams and users

These endpoints manage the people and structure around your gateway: the organization (your tenant), the teams that budgets and keys are scoped to, the invites that bring new people in, and the users themselves. Use them to automate onboarding, assign budgets, and keep the access list clean. For the same tasks in the UI, see [Managing your organization](/admin-console/managing-your-organization).

## How access works

Every endpoint here is a management endpoint. Authenticate with a session token (the bearer token from `POST /api/v1/auth/login`), not with a proxy API key. See [Authentication](/getting-started/authentication).

```bash
export TOKEN="<session token>"
curl https://api.openproxy.ai/api/v1/organizations/current \
  -H "Authorization: Bearer $TOKEN"
```

- You only ever see data from your own organization. An id from another organization answers `404`.
- There are three roles: `admin`, `developer`, `viewer`. Reads on users and the organization are open to every member; teams, invites and every write need `admin` (otherwise `403`).
- Every change is recorded in the [admin audit log](/security/audit-logging).

## Organization

### Read and update

```
GET   /api/v1/organizations/current
PATCH /api/v1/organizations/current
```

The `GET` returns your plan, data region, monthly budget, settings and billing status:

| Field | Meaning |
|---|---|
| `id`, `name`, `slug` | Identity of the organization |
| `plan` | `community`, `team`, `business`, `enterprise` or `metered` |
| `budget_monthly_usd` | Organization-wide monthly budget, or `null` |
| `data_region` | `us`, `eu`, `ap` or `null` (see [Data residency](/security/data-residency)) |
| `settings` | Free-form settings object. Webhook secrets are never included |
| `is_active` | Whether the organization is active |
| `stripe_subscription_status` | Billing state when a subscription exists |
| `included_tokens_monthly` | Included token quota, set for usage-metered plans |

`PATCH` (admin) takes any of `name` (1 to 255 characters), `budget_monthly_usd` (zero or more), `data_region` (`us`, `eu`, `ap`), `settings` and `plan`:

```bash
curl -X PATCH https://api.openproxy.ai/api/v1/organizations/current \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name": "Acme AI Platform", "budget_monthly_usd": "5000.00", "data_region": "eu"}'
```

Rules to know:

- `settings` is merged into the existing object, not replaced. The keys `webhooks` and `policy` are reserved and rejected with `400`; use their own endpoints below.
- A spend-report webhook URL inside `settings` must be `https` and resolve to a public address (`400` otherwise).
- You cannot deactivate the organization here (`400`).
- Plans are managed through billing. If a subscription exists, a plan change answers `409`. Without one, only `community` can be set by hand; any other plan answers `400` because it requires a subscription.

### Policy

```
GET   /api/v1/organizations/current/policy
PATCH /api/v1/organizations/current/policy
GET   /api/v1/organizations/current/policy/templates
POST  /api/v1/organizations/current/policy/apply-template
```

Each organization has one policy with an `enforcement_mode` of `off`, `log_only` or `enforce`. `PATCH` (admin) changes only the fields you send; omitted fields keep their value. Changes take effect within 60 seconds. Two guards apply:

- Switching `routing_mode` to `enforce` answers `409` if no enabled model with an active provider key is registered. Use `log_only` to preview first.
- Turning on PII detection needs a plan that includes it (`402` otherwise).

`apply-template` (admin) takes `{"template": "<name>"}` from the templates list. A template sets the guardrail fields only and keeps your model allowlist, rate limits and other settings. An unknown name answers `400`. Templates are configuration presets, not certifications; see [Compliance templates](/security/compliance-templates) and [Policies and guardrails](/core-concepts/policies-and-guardrails).

### Webhooks

```
GET   /api/v1/organizations/current/webhooks
PATCH /api/v1/organizations/current/webhooks
GET   /api/v1/organizations/current/webhooks/deliveries
POST  /api/v1/organizations/current/webhooks/deliveries/{delivery_id}/retry
```

All admin only. `PATCH` replaces the whole webhook configuration:

```json
{
  "url": "https://hooks.example.com/openproxy",
  "secret": "a-long-random-string",
  "events": ["policy.violation", "budget.alert"],
  "enabled": true
}
```

The URL must be `https` and must not resolve to a private or local address. The only events are `policy.violation` and `budget.alert`. The response returns `url`, `events` and `enabled`; the secret is write-only.

The deliveries list is paginated (`page`, `page_size` up to 100, default 20) and filters with `?status=`. A retry on a delivery that already succeeded answers `409`; if the stored URL is no longer considered safe it answers `400`. See [Webhooks](/guides/webhooks) for payloads and signatures.

## Teams

A team is a group of users with its own monthly budget. Teams attribute spend to a department and scope API keys; see [Rate limiting and budgets](/core-concepts/rate-limiting-and-budgets). All team endpoints are admin only.

```
GET    /api/v1/teams
POST   /api/v1/teams
GET    /api/v1/teams/{team_id}
PATCH  /api/v1/teams/{team_id}
DELETE /api/v1/teams/{team_id}
POST   /api/v1/teams/{team_id}/members/{user_id}
DELETE /api/v1/teams/{team_id}/members/{user_id}
```

### Create and change a team

```bash
curl -X POST https://api.openproxy.ai/api/v1/teams \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name": "Platform Engineering", "budget_monthly_usd": "1500.00"}'
```

```json
{
  "id": "…", "org_id": "…", "name": "Platform Engineering",
  "budget_monthly_usd": "1500.00", "created_at": "2026-11-13T15:02:11Z",
  "member_count": 0
}
```

| Field | Rules |
|---|---|
| `name` | 1 to 255 characters. Cannot be set to `null` on update |
| `budget_monthly_usd` | Zero or more, or `null` for no team budget |

`POST` answers `201`. `PATCH` changes only the fields you send. `DELETE` answers `204`. `GET /teams/{team_id}` adds a `members` list (`id`, `email`, `name`). `GET /teams?membership=me` lists only the teams you belong to.

### Members

Adding a member answers `204`. It answers `404` if the team or user is not in your organization and `400` if the user is already a member. Removing a user who is not a member answers `404`.

## Invites

New people join through an invite, not by being created directly. Invites are admin only.

```
POST   /api/v1/invites/
GET    /api/v1/invites/
DELETE /api/v1/invites/{invite_id}
```

```bash
curl -X POST https://api.openproxy.ai/api/v1/invites/ \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"email": "dana@example.com", "role": "developer"}'
```

`role` is `admin`, `developer` or `viewer` (default `developer`). The `201` response contains the invite and an `invite_url` to send to the person:

```json
{
  "id": "…", "org_id": "…", "email": "dana@example.com", "role": "developer",
  "invited_by": "…", "expires_at": "2026-11-20T15:04:00Z",
  "accepted_at": null, "created_at": "2026-11-13T15:04:00Z",
  "invite_url": "https://…"
}
```

- An invite expires after 7 days. The list returns only invites that are neither accepted nor expired.
- The person opens the link and accepts with a name and a password of at least 8 characters.
- Acceptance fails with `410` if the invite expired, `409` if it was already used or the email already has an account, and `402` if the plan's user limit is reached.
- Revoking removes a pending invite (`204`, or `404` if it does not exist).
- To assign the new user to a team, wait until they accept, then add them with the members endpoint. If you use single sign-on, see [SSO and SCIM](/guides/sso-and-scim) instead.

## Users

```
GET   /api/v1/users
GET   /api/v1/users/{user_id}
PATCH /api/v1/users/{user_id}
```

Any member can read; only admins can change. A user looks like this:

```json
{
  "id": "…", "org_id": "…", "email": "dana@example.com", "name": "Dana",
  "role": "developer", "budget_daily_usd": "25.00", "budget_monthly_usd": null,
  "is_active": true, "created_at": "2026-11-02T14:21:07Z"
}
```

`PATCH` takes any of:

| Field | Values |
|---|---|
| `name` | 1 to 255 characters |
| `role` | `admin`, `developer`, `viewer` |
| `budget_daily_usd`, `budget_monthly_usd` | A number of zero or more |
| `is_active` | `false` stops the person signing in |

```bash
curl -X PATCH https://api.openproxy.ai/api/v1/users/$USER_ID \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"role": "viewer", "budget_daily_usd": "10.00"}'
```

Two guards stop you locking yourself out. You cannot remove your own admin access (`400`), and you cannot demote or deactivate the last active admin of the organization (`400`). Audit entries distinguish `user.role_changed`, `user.deactivated` and `user.updated`.

## Errors

| Status | Cause |
|---|---|
| `400` | Invalid value, reserved settings key, unsafe webhook URL, or a lock-out guard |
| `401` | Missing, expired or revoked session token |
| `402` | The plan's limit (users) or feature (PII detection) is not available |
| `403` | The call needs `admin` |
| `404` | Not found in your organization |
| `409` | Duplicate or conflicting state (billing-managed plan, already a member, already accepted) |
| `422` | Body failed validation |

See [Errors and status codes](/api-reference/errors-and-status-codes) for the shared error format.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `403` on `GET /teams` as a developer | Team endpoints are admin only | Use an admin token |
| `PATCH` organization with `settings.policy` answers `400` | `policy` and `webhooks` are reserved | Use the policy or webhooks endpoints |
| Webhook `PATCH` fails validation | URL is not `https`, or resolves to a private address | Use a public `https` endpoint |
| Cannot deactivate a user | They are the last active admin, or you | Promote another admin first |
| Invite link says expired | 7 days passed | Revoke and send a new invite |

## Next steps

- [API keys and provider keys](/api-reference/keys)
- [Rate limiting and budgets](/core-concepts/rate-limiting-and-budgets)
- [Admin audit log](/security/audit-logging)
- [SSO and SCIM](/guides/sso-and-scim)
