---
title: Users
description: List people in your organization, change a role or budget, and deactivate an account.
---

# Users

```
GET   /api/v1/users
GET   /api/v1/users/{user_id}
PATCH /api/v1/users/{user_id}
```

Authenticate with a session token. Any member can read; **only admins can change**. You only ever see people in your own organization. To add people, use [invites](/api-reference/teams) or [SCIM](/guides/configuring-scim).

A user looks like this:

```json
{
  "id": "…", "org_id": "…", "email": "dana@example.com", "name": "Dana",
  "role": "developer", "budget_daily_usd": "25.00", "budget_monthly_usd": null,
  "is_active": true, "created_at": "2026-11-02T14:21:07Z"
}
```

## Change a user

`PATCH` takes any of:

| Field | Values |
|---|---|
| `name` | 1 to 255 characters |
| `role` | `admin`, `developer`, `viewer` |
| `budget_daily_usd`, `budget_monthly_usd` | A number of zero or more |
| `is_active` | `false` stops the person signing in |

Two guards protect you from locking yourself out. You cannot remove your own admin access (400), and you cannot demote or deactivate the last active admin of the organization (400). Each change is written to the [admin audit log](/security/audit-logging).
