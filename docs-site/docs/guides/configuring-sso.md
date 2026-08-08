---
title: Configuring SSO
description: Connect an identity provider so your org signs in through your own IdP.
---

# Configuring SSO

Organizations on Growth and Enterprise plans can connect an identity provider (OIDC/SAML) so members sign in to the admin console through your own IdP instead of a password.

## Connect a provider

```
POST /api/v1/auth/sso/initiate
```

This begins the connection flow for your identity provider. Once configured, the connection appears under `/api/v1/sso/connections`.

## The sign-in flow

1. A user visits the admin console sign-in page and selects "Sign in with SSO."
2. They're redirected to your IdP.
3. On success, your IdP redirects back to `/api/v1/auth/sso/callback`, which exchanges the authorization code (`/api/v1/auth/sso/exchange-code`) and issues a normal OpenProxyAI session.

## Managing connections

List, update, or remove a connection via `/api/v1/sso/connections` and `/api/v1/sso/connections/{connection_id}`.

## Inviting members under SSO

Once SSO is enforced for an org, new members are provisioned by inviting them (`/api/v1/invites/`) — they complete sign-in through your IdP rather than setting a password. See [Managing Teams](/admin-console/managing-teams).
