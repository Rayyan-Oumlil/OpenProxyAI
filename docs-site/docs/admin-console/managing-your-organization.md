---
title: Managing your organization
description: Create teams, invite people, configure the organization policy and compliance templates, and manage your plan from the admin console.
---

# Managing your organization

This page covers the Admin and Govern screens an organization admin uses every week: **Teams**, **Policy**, and **Billing**. Use it to organize people into teams with their own budgets, to turn guardrails on safely, and to change your plan. Every action here is also available through the API, shown beside each task.

All three screens are admin-only for changes. Other roles can see the Policy screen but cannot edit it, and the Teams screen tells non-admins that it is admin only.

## Teams

A team is a named group of people with an optional monthly dollar budget. Teams let you attribute cost by department or project and cap what each one can spend. Each team gets a UUID that you send in the `x-openproxy-team-id` request header, or tie to an API key as its `team_id`. See [Rate limiting and budgets](/core-concepts/rate-limiting-and-budgets) for how the limits are enforced at the rate-limit stage of the [request pipeline](/core-concepts/request-pipeline).

### The Teams screen

The table lists each team's name, monthly budget (a dash means no budget), member count and creation date. Each row has two actions: manage members and delete. Deleting a team asks for confirmation and unassigns its members; their accounts stay in the organization.

### Create a team

1. Open **Admin, Teams** and select **Create Team**.
2. Enter a name (required, up to 255 characters).
3. Optionally enter **Monthly Budget (USD)**. It must be zero or more.
4. Select **Create Team**.

```bash
curl -X POST https://your-gateway/api/v1/teams \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d '{"name": "Engineering", "budget_monthly_usd": 500}'
```

The response includes the team `id`, `name`, `budget_monthly_usd`, `created_at` and `member_count`. To change the name or budget later, send `PATCH /api/v1/teams/{team_id}` with only the fields you want to change. A name cannot be set to null.

### Add people to a team

Select the members icon on a team's row. The dialog has three parts.

| Part | What it does |
|---|---|
| Current members | Lists each member with a **Remove** button. Removing someone from a team does not delete their organization account, which is useful when they change teams internally. |
| Add existing user | A dropdown of organization users who are not yet on this team. Picking one adds them immediately. |
| Invite someone new | Creates an invite for an email address and a role (Developer, Viewer or Admin). |

Adding a member through the API is `POST /api/v1/teams/{team_id}/members/{user_id}` (it returns 400 if the user is already a member). Removal is `DELETE` on the same path.

### Invite a new person

1. In the members dialog, enter the email address and choose a role. Developer is the default.
2. Select **Send Invite**.
3. Copy the **invite link** shown below the form and send it to the person yourself.

This is subtle: the gateway creates the invite and shows you the link, but it does not send the email. Share the link through your own channel. The invite is valid for 7 days and appears under **Pending invites** with its role and expiry date, where you can **Revoke** it.

The invited person opens the link, sets a name and password, and gets an account in your organization with the role you chose. An invite does not carry a team, so afterwards add them to a team with **Add existing user**.

```bash
curl -X POST https://your-gateway/api/v1/invites/ \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d '{"email": "colleague@company.com", "role": "developer"}'
```

The response contains `invite_url` plus the invite's `id`, `email`, `role` and `expires_at`. List pending invites with `GET /api/v1/invites/` and revoke one with `DELETE /api/v1/invites/{invite_id}`. Accepting an invite is `POST /api/v1/auth/accept-invite` with `token`, `name` and a password of at least 8 characters.

### What a team budget and team limits do

- **Team budget.** The monthly dollar budget you set on the team. When the team's spend for the calendar month reaches it, requests tagged with that team get HTTP 429 with the limit type `team_budget_monthly_usd` until the month resets. The organization budget is checked independently; both must pass.
- **Team request and token rates.** A per-minute ceiling on requests and tokens for every team, set in the organization policy as `per_team_limits`. There is no console field for it; use the API:

```bash
curl -X PATCH https://your-gateway/api/v1/organizations/current/policy \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d '{"per_team_limits": {"rpm": 60, "tpm": 50000}}'
```

When a team exceeds these, the 429 carries `team_requests_per_minute` or `team_tokens_per_minute`.

## Policy

The Policy screen is a form over the organization's single policy, the same configuration served at `/api/v1/organizations/current/policy`. For what each guardrail does inside a request, see [Policies and guardrails](/core-concepts/policies-and-guardrails). There is one policy per organization, not named policies.

### How saving works

Edit any tab, then use the bar at the bottom: it reads **You have unsaved changes** or **All changes saved**. **Discard** resets the form to what is stored; **Save policy** sends only the fields you changed as a partial update. Changes take effect within 60 seconds, because policies are cached.

### The tabs

| Tab | Settings |
|---|---|
| Enforcement | Enforcement mode, model allowlist, blocked keywords |
| Data protection | PII detection and the entity types to look for, prompt injection detection, response guardrails and response PII redaction |
| Data and routing | Default data class, data class overrides per detected kind, routing mode (off, log only, enforce), highest allowed model risk rating, quality-based model preference, provider-held response state, and a routing preview |
| Behavior | Default and ceiling values for creativity, reasoning depth, response length and citations. See [Behavior settings](/core-concepts/behavior-settings) |
| Evaluation | Sampled payload capture, the prompt promotion gate and conversations. See [Prompts](/guides/prompts), [Payload capture](/guides/payload-capture) and [Conversations](/guides/conversations) |
| Rate limits | Per-model requests-per-minute (RPM) and tokens-per-minute (TPM) overrides |
| Templates | One-click compliance templates |

### Switch between log only and enforce

The enforcement mode applies to the whole policy, not to individual checks: `off`, `log_only` or `enforce`. In `log_only`, violations are recorded as policy events and no request is blocked. In `enforce`, a violating request is blocked with HTTP 446.

Recommended rollout for any new rule:

1. Turn the rule on while the mode is `log_only`.
2. Watch its hit counts for false positives (see below).
3. Switch to `enforce` once you trust it.

The Data and routing tab follows the same two-step pattern with its own routing mode: Preview (log only) records which registry model would serve each request without refusing anything, and Enforce restricts each request to models cleared for its data class. Enforce needs at least one enabled model with an active provider key in the model registry. See [Provider routing](/core-concepts/provider-routing).

### Review policy activity

Hit counts per rule over a time range come from `GET /api/v1/analytics/policy` (see the [analytics reference](/api-reference/analytics)). A rule with many log-only hits on legitimate traffic is too aggressive; a rule that never fires may not be configured the way you meant.

### Apply a compliance template

Open the **Templates** tab, expand **What it configures** on a card, and select **Apply Template**. Available templates are Healthcare (HIPAA), Finance (PCI-DSS) and Government (FedRAMP); the card of the one in use is marked **Applied**. Templates are not available on the Community plan; those cards show **Requires Team plan**.

```bash
curl -X POST https://your-gateway/api/v1/organizations/current/policy/apply-template \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d '{"template": "healthcare_hipaa"}'
```

A template **replaces** the guardrail fields: enforcement mode, blocked keywords, PII detection and entities, prompt injection detection, and response guardrails. Your model allowlist, rate limits, MCP tool lists and other settings are kept. Review the result afterwards, since the keyword list is now the template's. Templates set guardrails only; they are not certifications. See [Compliance templates](/security/compliance-templates).

### Policy troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Save button is disabled | No unsaved changes, or you are not an admin | Change a field; sign in as an admin |
| A setting change has no effect yet | Policy cache | Wait up to 60 seconds |
| Requests get HTTP 446 after a template | The template set `enforce` mode | Switch to `log_only` and review hits first |
| Template cards show Requires Team plan | Community plan | Upgrade under Billing |

## Billing

The Billing screen, under Admin, shows your **Current plan**, **Subscription status** and a **Manage Billing** button, followed by a card for each plan: Community, Team, Business, Metered and Enterprise. See [pricing](https://openproxy.ai/pricing) for what each tier includes. Only admins can start checkout or open the portal.

### Change your plan

1. Select the upgrade button on the Team, Business or Metered card. The console redirects you to the billing provider's checkout page.
2. Complete payment. You return to the console with a "Payment processing" notice, and the page polls for up to 30 seconds until the plan changes.
3. If it still shows the old plan after that, refresh in a moment; the change arrives through a webhook from the billing provider.

Canceling checkout returns you with "Checkout canceled. No charges were made." Enterprise is arranged with sales, and checkout for it is refused as requiring manual setup.

To update payment details, view invoices or change an existing subscription, select **Manage Billing**. It is disabled until the organization has a billing customer record.

```bash
curl -X POST https://your-gateway/api/v1/billing/checkout \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d '{"plan": "team"}'
# {"checkout_url": "https://..."}

curl -X POST https://your-gateway/api/v1/billing/portal \
  -H "Authorization: Bearer $ADMIN_TOKEN"
# {"portal_url": "https://..."}
```

Supported `plan` values are `team`, `business` and `metered`.

### Metered usage

On the Metered plan, a panel compares tokens used in the last 30 days with your included monthly allowance, with a projected month-end total and estimated overage. Usage syncs to the billing provider on an hourly background schedule. That sync is disabled in [air-gapped deployments](/getting-started/environment-flags) (`AIRGAP_MODE=true`), where billing is handled outside the platform.

The webhook endpoint `POST /api/v1/billing/webhook` receives subscription events from the billing provider. You do not call it, but it is where to look when a plan change has not reached the console.

### Billing troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Upgrade buttons are disabled | You are not an admin, or it is your current plan | Ask an admin |
| Manage Billing is disabled | No billing customer yet | Complete a first checkout |
| Plan unchanged after paying | Webhook not processed yet | Refresh after a minute; check webhook delivery |
| Adding a user returns 402 | The plan's user limit is reached | Upgrade the plan |

## Next steps

- [Rate limiting and budgets](/core-concepts/rate-limiting-and-budgets) for how team and organization limits are applied.
- [Policies and guardrails](/core-concepts/policies-and-guardrails) for what each guardrail checks.
- [Evaluating changes](/admin-console/evaluating-changes) before you move a rule from log only to enforce.
- [Organizations, teams and users API](/api-reference/organizations-teams-users) for the full endpoint reference.
