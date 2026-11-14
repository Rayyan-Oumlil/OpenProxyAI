---
title: Admin Console Overview
description: Manage your organization, teams, policies, and billing from one dashboard.
---

# Admin Console Overview

The admin console is where you manage everything that isn't a raw API call: teams and members, policies, provider keys, billing, and the audit log.

## Signing in

Sign in with your email/password (created at registration) or through your org's connected [SSO](/guides/sso-and-scim) provider, if configured.

## What you'll find

- **Teams** — create teams, invite members, assign budgets ([Managing Teams](/admin-console/managing-your-organization))
- **Policies** — configure guardrails and apply compliance templates ([Managing Policies](/admin-console/managing-your-organization))
- **Provider keys** — register and rotate upstream provider credentials
- **Analytics** — spend, cache hit rate, and policy activity dashboards
- **Playground** — compare models side-by-side and manage prompt templates ([Prompt Playground](/guides/prompts))
- **Conversations** — saved chats with tags, search and project spaces ([Conversations](/guides/conversations))
- **MCP servers** — register tool servers and approve their tools ([MCP gateway](/guides/mcp-gateway))
- **Batch jobs** — follow and cancel batches your applications started ([Batch jobs](/admin-console/batch-jobs))
- **Billing** — plan, usage, and invoices ([Billing](/admin-console/managing-your-organization))
- **Audit log** — every request and policy decision, queryable and exportable ([Audit Logging](/security/audit-logging))

This is a session-authenticated web app, separate from the API-key-authenticated proxy your applications call — see [Authentication](/getting-started/authentication) for how the two relate.
