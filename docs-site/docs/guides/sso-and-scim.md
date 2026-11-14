---
title: Single sign-on and SCIM
description: "Connect an OpenID Connect identity provider for console sign-in and let Okta or Microsoft Entra ID provision users through SCIM 2.0."
---

# Single sign-on and SCIM

Single sign-on (SSO) lets your team sign in to the admin console through your own identity provider (IdP) instead of a password. SCIM (System for Cross-domain Identity Management) lets the same IdP create, update and deactivate OpenProxyAI users automatically. Both are available on plans that include SSO (Enterprise) and are set up by an organization admin. SSO uses OpenID Connect (OIDC); SAML is not supported.

All `/api/v1/...` calls below are authenticated as an admin, as described in [Authentication](/getting-started/authentication). The SCIM endpoints under `/scim/v2` use a separate SCIM token.

## Single sign-on (OIDC)

### How the flow works

1. The browser is sent to `GET /api/v1/auth/sso/initiate` with a `connection_id` and a `redirect_uri`. The gateway stores a one-time `state` and `nonce` (valid 10 minutes) and redirects to your IdP's authorization endpoint, requesting the scopes `openid email profile`.
2. After sign-in, the IdP redirects to `/api/v1/auth/sso/callback`. The gateway exchanges the code, verifies the ID token (signature, issuer, audience, nonce) and requires an `email` claim.
3. It then redirects to the console at `/sso-callback?code=...`. That code is single-use and valid for 90 seconds; the console swaps it for a session with `POST /api/v1/auth/sso/exchange-code`, so tokens never appear in a URL.

Two settings must be right for this to work:

| Setting | Meaning |
|---|---|
| `APP_BASE_URL` | Public URL of the API. The only accepted `redirect_uri` is `{APP_BASE_URL}/api/v1/auth/sso/callback`; register exactly that value at your IdP. |
| `FRONTEND_BASE_URL` | Public URL of the console, where the user lands after sign-in. If unset, the first entry in `CORS_ORIGINS` is used. |

### Create a connection

```bash
curl -X POST https://gateway.example.com/api/v1/sso/connections \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "provider_name": "Okta",
    "issuer_url": "https://acme.okta.com",
    "client_id": "0oa1b2c3d4",
    "client_secret": "<client secret>",
    "domain_hint": "acme.com"
  }'
```

The response (`201`) returns `id`, `org_id`, `provider_name`, `issuer_url`, `client_id`, `domain_hint` and `is_active`. The client secret is stored encrypted and never returned. The `id` is the `connection_id` for the sign-in flow.

| Field | Required | Notes |
|---|---|---|
| `provider_name` | Yes | A label for your own reference. |
| `issuer_url` | Yes | Must be an `https` URL that resolves to a public address. Discovery is read from `{issuer_url}/.well-known/openid-configuration`. |
| `client_id`, `client_secret` | Yes | From the OIDC application you create at the IdP. |
| `domain_hint` | No | Stored with the connection. |

Other connection endpoints: `GET /api/v1/sso/connections` lists the organization's connections and `DELETE /api/v1/sso/connections/{connection_id}` removes one (`204`). There is no update call; delete and recreate to change a setting. All three are admin only.

### Who gets in

The gateway matches the IdP's `email` claim to a user in your organization. A user who is not found is created on first sign-in with the **developer** role and no password; an existing user keeps their role. Change roles in the console; see [Managing your organization](/admin-console/managing-your-organization).

## SCIM provisioning

SCIM 2.0 lets your IdP (Okta, Microsoft Entra ID, or anything that speaks SCIM) manage users for you: a new hire appears in OpenProxyAI and a leaver is deactivated without anyone opening the console.

| | |
|---|---|
| Creates users | Yes. New users are **viewers**. |
| Updates name, email, `active` | Yes (PATCH and PUT). |
| Deactivates users | Yes. `DELETE` and `active: false` both deactivate; the user's request history stays. |
| Sets roles | **Never.** A request that carries `roles` is refused (`400`), so provisioning can never grant admin. |
| Groups | Not supported (`404`). Manage teams in OpenProxyAI. |
| Bulk, sort, ETags, password changes | Not supported (advertised as such in `ServiceProviderConfig`). |

### Ownership rules

SCIM manages **only the users it created**. Existing users (admins, people who signed up or were invited) are invisible to it: it cannot read or change them, and creating a user with an existing email returns `409`. This is deliberate: SSO matches people by email, so letting an IdP change an existing user's email would let it take over an account.

One exception keeps offboarding from failing open: `DELETE`, or a PATCH that only sets `active: false`, deactivates **any** user in your organization (the last active admin is still protected). Re-enabling, or deactivating together with other changes, works only on users SCIM created. Once someone has been promoted past viewer, SCIM can no longer re-enable them (`403`). The email (`userName`) of an existing user cannot be changed through SCIM (`403`, `mutability`); change it in the console.

Deactivation takes effect on the next request: sessions and API keys of an inactive user are refused.

### Step 1: create a token

In the admin console open **Organization settings, User provisioning (SCIM)** and choose **Create token**, or call the API as an admin:

```bash
curl -X POST https://gateway.example.com/api/v1/scim/token \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

```json
{
  "configured": true,
  "token_prefix": "scim_ab12",
  "created_at": "2026-11-13T14:02:11",
  "last_used_at": null,
  "scim_base_url": "https://gateway.example.com/scim/v2",
  "token": "scim_...",
  "rotated": false
}
```

The `token` is shown once (the response is sent with `Cache-Control: no-store`); only a hash is stored. A SCIM token works only on `/scim/v2`; it is not an API key. There is one live token per organization:

| Call | Effect |
|---|---|
| `GET /api/v1/scim/token` | Status only: `configured`, `token_prefix`, `created_at`, `last_used_at`, `scim_base_url`. |
| `POST /api/v1/scim/token` | Creates the token, or rotates it (`rotated: true`). The old token stops working immediately, so update your IdP straight away. |
| `DELETE /api/v1/scim/token` | Revokes it (`204`; `404` if none). Provisioning stops until you create a new one. |

### Step 2: point your IdP at it

| Setting | Value |
|---|---|
| SCIM base URL | `https://<your-gateway>/scim/v2` |
| Authentication | HTTP header, bearer token: `Authorization: Bearer scim_...` |
| Unique identifier | `userName` (the user's email) |
| Supported actions | Create, update, deactivate users. Leave **Push groups** off. |

Okta: add a SCIM 2.0 app, choose "HTTP Header" authentication, and enable Create Users, Update User Attributes and Deactivate Users. Entra ID: Enterprise application, Provisioning, Automatic; paste the base URL as Tenant URL and the token as Secret Token, then run Test Connection.

### How users map

| SCIM | OpenProxyAI |
|---|---|
| `userName` | Email, lower-cased. `emails` is accepted but `userName` wins. |
| `name`, `displayName` | Display name (`givenName` and `familyName` are joined). |
| `externalId` | Your IdP's id for the user, unique within your organization. |
| `active` | Active or deactivated. |

Users created by SCIM have no password and sign in through SSO. Creating a user whose email exists anywhere in OpenProxyAI returns `409` with `scimType: uniqueness`.

```bash
curl -X POST https://gateway.example.com/scim/v2/Users \
  -H "Authorization: Bearer scim_..." \
  -H "Content-Type: application/scim+json" \
  -d '{
    "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
    "userName": "ada@example.com",
    "externalId": "00u1abcd",
    "name": {"givenName": "Ada", "familyName": "Lovelace"},
    "active": true
  }'
```

The `201` response is a SCIM User with `id`, `userName`, `active`, `emails`, `externalId`, `displayName`, `name.formatted` and `meta` (`created`, `lastModified`, `location`). To deactivate:

```bash
curl -X PATCH https://gateway.example.com/scim/v2/Users/<id> \
  -H "Authorization: Bearer scim_..." \
  -H "Content-Type: application/scim+json" \
  -d '{"schemas":["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
       "Operations":[{"op":"replace","path":"active","value":false}]}'
```

### Filtering and paging

`GET /scim/v2/Users?filter=userName eq "ada@example.com"` finds one user (also `externalId eq` and `id eq`). Any other filter returns `400` with `scimType: invalidFilter`; it is refused rather than guessed. `startIndex` is 1-based; `count` defaults to 100 and is capped at 200. Discovery endpoints `ServiceProviderConfig`, `ResourceTypes` and `Schemas` are available under `/scim/v2`.

### Safeguards

- Every change is written to the admin audit log (`user.scim_created`, `user.scim_updated`, `user.scim_deactivated`, `user.scim_reactivated`) with the token's prefix as actor; creating, rotating and revoking the token are logged too, never the token itself. See [Audit logging](/security/audit-logging).
- Creating or re-enabling a user counts against the plan's user limit; when it is full the request returns `403` with `scimType: tooMany`. Deactivating is never blocked.
- The last active admin cannot be deactivated through SCIM.
- A PUT that omits `active` leaves it unchanged, so a replace never re-enables someone your IdP deactivated.
- Requests are limited to 600 per minute per organization, and repeated failed token attempts from one address are throttled (`429` with `Retry-After`).
- Errors use the SCIM error format (`urn:ietf:params:scim:api:messages:2.0:Error`).

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `403` creating a connection or SCIM token | The plan does not include SSO, or the caller is not an admin. | Use an admin on an Enterprise organization. |
| `400 Invalid redirect_uri` on initiate | `redirect_uri` differs from `{APP_BASE_URL}/api/v1/auth/sso/callback`. | Set `APP_BASE_URL` to the public API URL and register the same callback at the IdP. |
| `400` creating a connection | `issuer_url` is not https or does not resolve to a public address. | Use the IdP's public https issuer. |
| `502 IdP discovery failed` | The gateway cannot reach `{issuer_url}/.well-known/openid-configuration`. | Check the issuer URL and outbound access. |
| `400 Invalid or expired SSO state` or `SSO code` | The sign-in took over 10 minutes, or the one-time code was reused or older than 90 seconds. | Start sign-in again. |
| `400 No email claim` | The IdP's ID token has no `email`. | Release the email claim for the `email` scope. |
| `429` on exchange-code | Too many attempts from one address (default 30 per minute, `SSO_EXCHANGE_RATE_LIMIT_RPM`). | Wait a minute. |
| SCIM `401` | Token missing, wrong, rotated or revoked. | Paste the current token into the IdP. |
| SCIM `403` on a user | The user was not created by SCIM, was promoted past viewer, or the email change was attempted. | Make the change in the console. |
| SCIM `409` | The email already exists. | Let the user sign in through SSO, or remove the duplicate in the console. |

## Next steps

- [Managing your organization](/admin-console/managing-your-organization)
- [Audit logging](/security/audit-logging)
- [Authentication](/getting-started/authentication)
