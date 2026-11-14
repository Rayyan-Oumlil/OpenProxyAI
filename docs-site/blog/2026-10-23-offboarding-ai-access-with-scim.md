---
slug: offboarding-ai-access-with-scim
image: /img/blog/og/offboarding-ai-access-with-scim.png
title: "SSO and SCIM: when someone leaves, their AI access leaves with them"
tags: [security, product]
description: "A leaver's AI keys should not outlive their badge. See exactly what stops when your identity provider marks someone inactive, what stays for the record, and how to plan for service keys."
---

Offboarding checklists cover email, laptops and source control. AI access is often missing: a personal API key in a script, a console login, a batch job someone left running. If those are not tied to your directory, they outlive the person. OpenProxyAI ties them together. When your identity provider marks someone inactive, SCIM carries that change to the gateway, and their access stops on the next request.

{/* truncate */}

![The identity provider marks a person inactive and sends a SCIM update. Console sessions, the person's API keys and their running batches stop on the next call. Request history, audit entries and other people's keys are kept. Advice: move production keys to an owner who will stay.](/img/blog/offboarding-ai-access-with-scim.svg)

## The gap SSO alone leaves

Single sign-on (SSO) controls how people sign in to the console. It does not, by itself, tell the gateway that a person has left. API keys are the long-lived part of AI access, and they are used by scripts and apps, not by a person typing a password. SCIM, the standard that lets an identity provider create, update and deactivate accounts in other systems, closes the gap. Our earlier post on [SSO and SCIM for AI access](/blog/sso-and-scim-for-ai-access) covers setup. This one is about the leaver.

## What stops when a person is deactivated

Deactivation happens in either of two ways: your identity provider sets the user inactive, or it deletes the user. Both deactivate the account in OpenProxyAI. From the next request:

| Access | Result |
|---|---|
| Console sessions | Refused. A refresh of the session is refused too. |
| The person's API keys | Refused with a 401. Every request rechecks that the key's owner is still active. |
| MCP gateway access with those keys | Refused, because it uses the same keys. |
| Live realtime sessions | Closed, with a reason that credentials are no longer valid. |
| Batches the person started | Stop as failed, with a note that the owner is no longer active. |

Nothing here waits for a cache to expire. The gateway does not cache the decision about who may call.

## What stays, on purpose

| Kept | Why it helps |
|---|---|
| Request history and cost attribution | Finance and security can still see what the account did. |
| The admin audit log | Each provisioning change is recorded, with the token's prefix as the actor. |
| Other people's keys and the organization's provider keys | Provider keys belong to the organization, not to a person. |

So offboarding removes access and keeps evidence. If you need to look at what a leaver did in their last week, the logs are there.

## Safeguards that matter at offboarding

- **Offboarding never fails because of ownership.** SCIM normally manages only users it created. The exception is deactivation: a delete, or an update that only sets the user inactive, works on any user in the organization, including people invited by hand.
- **Provisioning cannot grant power.** SCIM creates users as viewers and can never set a role. A mapping mistake in the directory cannot make someone an admin.
- **You cannot lock yourself out.** The last active admin cannot be deactivated through SCIM.
- **A replace cannot undo a deactivation.** An update that omits the active flag leaves it unchanged.
- **Everything is audited.** Created, updated, deactivated and reactivated users each have their own audit entry.

## Plan for service keys before the first leaver

This is the one place offboarding can surprise a team, and it is easy to plan for. A key belongs to the user who created it. If a production application runs on a key created by an engineer, that application stops when the engineer is deactivated. This is the behavior you want for personal keys. For production, create the key under an owner you will keep, such as a dedicated service user, and give it a clear name and expiry. Our post on [a leaked key should be a nuisance](/blog/a-leaked-key-should-be-a-nuisance) covers keeping a single key from becoming an incident.

Do the inventory once, now:

1. List keys created by individuals that serve production.
2. Re-create them under a service owner and deploy the new keys.
3. Revoke the old ones, or let the deactivation do it.

## A leaver, step by step

1. HR marks the person inactive in the identity provider.
2. The directory sends a SCIM update. The gateway deactivates the account and writes an audit entry.
3. The next console call, API call or tool call from that person is refused.
4. A batch they left running stops with a clear reason. Realtime sessions close.
5. Security reviews the person's last month in the request history, and the audit log shows who changed what.

For a contractor you want to cut off before the directory is updated, an admin can also revoke a specific key by hand, or deactivate the user in the console.

## Good to know

- A request already being answered when a key is revoked is not interrupted. The next one is refused.
- SCIM can re-enable only users it created, and only those still at viewer level. Someone promoted to a higher role is re-enabled by an admin in the console.
- SCIM needs a plan that includes SSO, and the token is created and rotated by an admin. Rotating it cuts off the old token at once, so update your identity provider right away.
- Rehearse with a test account before the first real leaver, and check that sign-in, a key and a batch are all refused.

## What to do now

- Turn on SCIM with create, update and deactivate. Leave group push off.
- Inventory production keys created by individuals and move them to a service owner.
- Rehearse a leaver with a test account and read the audit entry.
- Add "AI gateway" to your offboarding checklist as a verification step, not an action.
- Review provisioning events in the audit log each quarter.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

Needs Docker and no provider key. The console is at http://localhost:5173. Star the repo or open an issue if your identity provider needs something we should support.

## Sources

- Product docs: [Single sign-on and SCIM](/guides/sso-and-scim), [API keys](/api-reference/keys), [Users](/api-reference/organizations-teams-users), [Batches](/api-reference/batches), [Audit logging](/security/audit-logging), [Authentication](/getting-started/authentication).
- Related posts: [SSO and SCIM for AI access](/blog/sso-and-scim-for-ai-access), [A leaked key should be a nuisance](/blog/a-leaked-key-should-be-a-nuisance).

These statements are based on OpenProxyAI's behavior at the post date.
