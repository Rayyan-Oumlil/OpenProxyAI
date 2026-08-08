---
title: Teams
description: Create teams, manage members, and scope budgets and API keys to them.
---

# Teams

Teams are how budgets, default policies, and API keys are scoped below the organization level — see [Rate Limiting & Budgets](/core-concepts/rate-limiting-and-budgets).

```
GET    /api/v1/teams
POST   /api/v1/teams
GET    /api/v1/teams/{team_id}
DELETE /api/v1/teams/{team_id}
```

## Members

```
POST   /api/v1/teams/{team_id}/members/{user_id}
DELETE /api/v1/teams/{team_id}/members/{user_id}
```

## Inviting a new user onto a team

New users are invited at the organization level, then assigned to a team:

```
POST /api/v1/invites/
```

See [Managing Teams](/admin-console/managing-teams) for the admin-console workflow.
