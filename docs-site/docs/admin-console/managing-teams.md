---
title: Managing Teams
description: Create teams, invite members by email, and scope budgets and API keys per team.
---

# Managing Teams

## Creating a team

From the console, create a team and give it a name — the team gets a UUID, which you send in the `x-openproxy-team-id` header, or tie an API key to as its `team_id`. See [Rate Limiting & Budgets](/core-concepts/rate-limiting-and-budgets).

## Inviting members

Invite a teammate by email from the team's member management screen. They receive an invite link; accepting it (`POST /api/v1/auth/accept-invite`) provisions their account and adds them to the team directly — no separate "create account, then request access" step.

## Removing a member

Remove a member from a team without deleting their org account entirely — useful when someone changes teams internally rather than leaving the organization.

## Setting a team's budget

Each team has its own monthly dollar budget, set from the Teams page. Team request and token rates are counted per team against the ceiling set in the organization policy. Both are enforced at the rate-limit stage of the [request pipeline](/core-concepts/request-pipeline).
