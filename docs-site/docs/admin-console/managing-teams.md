---
title: Managing Teams
description: Create teams, invite members by email, and scope budgets and API keys per team.
---

# Managing Teams

## Creating a team

From the console, create a team and give it a name — this becomes the value used in the `x-op-team` header, or the `team_id` an API key can be scoped to. See [Rate Limiting & Budgets](/core-concepts/rate-limiting-and-budgets).

## Inviting members

Invite a teammate by email from the team's member management screen. They receive an invite link; accepting it (`POST /api/v1/auth/accept-invite`) provisions their account and adds them to the team directly — no separate "create account, then request access" step.

## Removing a member

Remove a member from a team without deleting their org account entirely — useful when someone changes teams internally rather than leaving the organization.

## Setting a team's budget

Each team has its own daily dollar budget, requests/min, and tokens/min limits, visible and editable from the team's settings page — the same limits enforced at the rate-limit stage of the [request pipeline](/core-concepts/request-pipeline).
