---
title: Admin Console Overview
description: Manage your organization, teams, policies, and billing from one dashboard.
---

# Admin Console Overview

The admin console is where you manage everything that isn't a raw API call: teams and members, policies, provider keys, billing, and the audit log.

## Signing in

Sign in with your email/password (created at registration) or through your org's connected [SSO](/guides/configuring-sso) provider, if configured.

## What you'll find

- **Teams** — create teams, invite members, assign budgets ([Managing Teams](/admin-console/managing-teams))
- **Policies** — configure guardrails and apply compliance templates ([Managing Policies](/admin-console/managing-policies))
- **Provider keys** — register and rotate upstream provider credentials
- **Analytics** — spend, cache hit rate, and policy activity dashboards
- **Playground** — compare models side-by-side and manage prompt templates ([Prompt Playground](/guides/prompt-playground))
- **Billing** — plan, usage, and invoices ([Billing](/admin-console/billing))
- **Audit log** — every request and policy decision, queryable and exportable ([Audit Logging](/security/audit-logging))

This is a session-authenticated web app, separate from the API-key-authenticated proxy your applications call — see [Authentication](/getting-started/authentication) for how the two relate.
