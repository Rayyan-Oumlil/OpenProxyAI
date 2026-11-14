---
slug: sso-and-scim-for-ai-access
image: /img/blog/og/sso-and-scim-for-ai-access.png
title: "SSO and SCIM for AI access: onboard and offboard through your IdP"
tags: [security, product]
description: "Give people access to AI models through the identity provider you already run. Sign-in through SSO, automatic accounts and instant offboarding through SCIM, with roles that provisioning can never escalate."
---

Access to AI models spreads quickly: a console login here, an API key there, a shared account that nobody owns. When someone leaves, you find out months later that their key still works. The fix is the one you already use for every other tool: let your identity provider decide who has access. OpenProxyAI supports single sign-on (SSO) for sign-in and SCIM for automatic account creation and deactivation. SCIM is the standard that lets an identity provider create, update and deactivate accounts in other systems.

{/* truncate */}

![Identity provider on the left creating, updating and deactivating users in the gateway, with admins setting roles in the console](/img/blog/sso-and-scim-for-ai-access.svg)

## Sign-in through your identity provider

With SSO, people reach the admin console through your own identity provider using OpenID Connect, not a separate password. The flow is the familiar one: choose "Sign in with SSO", authenticate at your provider, return to the console with a normal session. You can list, update and remove connections through the API. Once SSO is enforced, new members are invited by email and finish sign-in through your provider. SSO is available on the Enterprise plan.

## Accounts that follow your directory

SCIM works with Okta, Microsoft Entra ID or any provider that speaks SCIM 2.0. You create a token in the admin console under organization settings, paste it and the gateway's SCIM address into your provider, and turn on create, update and deactivate. The token is shown once, only a hash is stored, and it works only for provisioning. It cannot call models or open anything else. You can rotate it, which cuts off the old one immediately, or revoke it.

| Event in your directory | What happens in the gateway |
|---|---|
| New hire assigned to the app | An account is created as a viewer. No password, sign-in through SSO |
| Name or email attributes updated | The account's name is updated |
| Person marked inactive or removed | The account is deactivated and history is kept |
| Role needs to change | An admin changes it in the console. Provisioning can never set a role |

That last row is deliberate. A request that tries to carry a role is refused, so a mistake in directory mappings can never create an admin.

## Offboarding that actually stops access

Deactivation takes effect on the next request. A deactivated person's sessions are refused. Their API keys are refused too, because a key belongs to the user who created it and is checked against that user's status. The audit log records each provisioning change with the actor, and the last active admin of an organization cannot be deactivated, so you cannot lock yourself out by accident.

One more safeguard matters for leavers. Deleting a user, or setting them inactive, works on any user in the organization, including people who were not created by SCIM, so offboarding never silently fails.

### A worked scenario

A company with an AI platform team and two product teams uses its identity provider as the source of truth.

1. **Monday.** A new analyst is assigned to the gateway app in the identity provider. Their account appears as a viewer. They sign in with SSO.
2. **Tuesday.** Their manager asks for developer access. An admin changes the role in the console, and the change is recorded in the audit log.
3. **Month three.** They move to another team. An admin removes them from the old team and adds them to the new one. Budgets and keys follow the team.
4. **Month nine.** They leave. HR marks them inactive in the identity provider. Their session ends, their personal keys stop working, and their request history remains for review.

## What to do now

- Connect your identity provider and test sign-in with a small pilot group.
- Create the SCIM token and configure create, update and deactivate. Leave group pushing off.
- Decide who is an admin. Remember that SCIM creates viewers, so promotion is a conscious step.
- Before the first leaver, list production keys that were created by individuals. They stop working when the person is deactivated, so move them to keys created by an owner you will keep.
- Rehearse offboarding with a test account and check that sign-in and keys are refused.
- Review the audit log for provisioning events each quarter.

## Good to know

SCIM manages only the users it created. Existing users, such as admins or people invited earlier, are not visible to it, except for deactivation, and an email address of an existing user cannot be changed through SCIM. Creating a user whose email already exists returns a conflict. Provisioning counts against your plan's user limit. SCIM is available on plans that include SSO, and bulk operations and password changes are not supported.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

Needs Docker and no provider key. The console is at http://localhost:5173. Star the repo or open an issue if your identity provider needs something we should support.

## Sources

- Product docs: [Configuring SSO](/guides/sso-and-scim), [Configuring SCIM](/guides/sso-and-scim), [Authentication](/getting-started/authentication), [Users](/api-reference/organizations-teams-users), [Audit logging](/security/audit-logging).

These statements are based on OpenProxyAI's behavior at the post date.
