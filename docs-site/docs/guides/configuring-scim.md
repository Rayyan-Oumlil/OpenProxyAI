---
title: Configuring SCIM provisioning
description: Let Okta or Microsoft Entra ID create, update and deactivate OpenProxyAI users automatically.
---

# Configuring SCIM provisioning

SCIM 2.0 lets your identity provider (Okta, Microsoft Entra ID, or anything that speaks SCIM) manage users for you: a new hire appears in OpenProxyAI, a leaver is deactivated, without anyone touching the admin console. It is available on plans that include SSO.

What it does and does not do:

| | |
|---|---|
| Creates users | Yes. New users are **viewers**. |
| Updates name, email, `active` | Yes (PATCH and PUT). |
| Deactivates users | Yes. `DELETE` and `active: false` both deactivate; the user's request history stays. |
| Sets roles | **Never.** Roles are set in the admin console. A request that carries `roles` is refused, so provisioning can never grant admin. |
| Groups | Not supported. Manage teams in OpenProxyAI. |
| Bulk, sort, ETags, password changes | Not supported (advertised as such in `ServiceProviderConfig`). |

SCIM manages **only the users it created**. Users who already exist (admins, people who signed up or were invited) are invisible to it: it cannot read, change or deactivate them, and creating a user with an existing email returns `409`. This is deliberate: SSO matches people by email, so letting an identity provider change an existing user's email would let it take over their account. Once someone has been promoted past viewer in the console, SCIM can still deactivate them (offboarding) but can no longer change their email or re-enable them (`403`).

Deactivation takes effect on the next request: sessions and API keys of an inactive user are refused by the same check the rest of the product already makes.

## 1. Create a token

In the admin console, open **Organization settings → User provisioning (SCIM)** and choose **Create token**. The token is shown once; copy it now. Only a hash is stored. Or through the API (admin only):

```
POST /api/v1/scim/token
```

The response contains `token` (shown once) and `scim_base_url`. A SCIM token only works on `/scim/v2`; it is not an API key and opens nothing else.

There is one live token per organization. **Rotate** replaces it and the old one stops working immediately, so update your identity provider straight away. **Revoke** (`DELETE /api/v1/scim/token`) stops provisioning until you create a new one.

## 2. Point your identity provider at it

| Setting | Value |
|---|---|
| SCIM base URL | `https://<your-gateway>/scim/v2` |
| Authentication | HTTP header, bearer token: `Authorization: Bearer scim_...` |
| Unique identifier | `userName` (the user's email) |
| Supported actions | Create, update, deactivate users. Leave **Push groups** off. |

Okta: add a SCIM 2.0 app, choose "HTTP Header" authentication, and enable Create Users, Update User Attributes and Deactivate Users. Entra ID: Enterprise application → Provisioning → Automatic, paste the base URL as Tenant URL and the token as Secret Token, then use Test Connection.

## How users map

| SCIM | OpenProxyAI |
|---|---|
| `userName` | Email, lower-cased. This is the one email; `emails` is accepted but `userName` wins. |
| `name`, `displayName` | The user's display name (`givenName` and `familyName` are joined). |
| `externalId` | Your identity provider's id for the user. Unique within your organization. |
| `active` | Active or deactivated. |

An email is unique across all of OpenProxyAI, so creating a user whose email already exists (in your organization or another) returns `409` with `scimType: uniqueness`. Users created by SCIM have no password and sign in through SSO.

## Filtering and paging

`GET /scim/v2/Users?filter=userName eq "ada@example.com"` finds one user (also `externalId eq` and `id eq`). Other filters return `400` with `scimType: invalidFilter`; they are refused rather than guessed. `startIndex` is 1-based; `count` is capped at 200.

## Safeguards

- Every change is written to the admin audit log (`user.scim_created`, `user.scim_updated`, `user.scim_deactivated`, `user.scim_reactivated`), with the token's prefix as the actor. Creating, rotating and revoking the token are logged too. The token itself is never logged.
- Changing the email of a SCIM-created user unlinks their SSO identity and revokes their API keys.
- Creating or re-enabling a user counts against the plan's user limit; when it is full the request returns `403` with `scimType: tooMany`. Deactivating is never blocked.
- The last active admin of an organization cannot be deactivated through SCIM.
- A PUT that omits `active` leaves it unchanged, so a replace never re-enables someone your identity provider deactivated.
- Requests are limited per organization (600 per minute), and repeated failed token attempts from one address are throttled.
- Errors use the SCIM error format (`urn:ietf:params:scim:api:messages:2.0:Error`).
