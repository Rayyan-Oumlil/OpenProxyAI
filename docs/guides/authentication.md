# Authentication

> **Applies to:** All plans

OpenProxyAI uses API keys to authenticate requests and manage access control. This guide covers key creation, permissions, role-based access control (RBAC), and SSO configuration.

## API Keys Overview

API keys are bearer tokens prefixed with `opai-` that you use to authenticate requests to the OpenProxyAI gateway. Keys are hashed and stored securely in the database — the full key is shown only once when created.

### Key Format

- **Prefix:** `opai-` (public, shown in key list)
- **Full key:** Displayed once at creation (copy and store securely)
- **Hash:** Stored in database for validation

### Key Properties

| Property | Type | Description |
|----------|------|-------------|
| `id` | UUID | Unique identifier |
| `key_prefix` | string | First 8 characters of key (e.g., `opai-abc1…`) |
| `key_hash` | string | SHA256 hash stored in database |
| `name` | string | User-friendly name (optional) |
| `permissions` | array | List of permission strings (default: `["proxy:llm"]`) |
| `is_active` | boolean | Whether key is usable |
| `expires_at` | datetime | Optional expiration time |
| `created_at` | datetime | Creation timestamp |
| `last_used_at` | datetime | Last successful authentication timestamp |

## Creating API Keys

### Via REST API

Create a new API key using `POST /api/v1/api-keys`:

```bash
curl -X POST https://api.openproxy.ai/api/v1/api-keys \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Production Gateway Key",
    "permissions": ["proxy:llm"],
    "expires_at": "2026-12-31T23:59:59Z"
  }'
```

**Request Body:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | string | — | Friendly name for the key (1-100 chars) |
| `permissions` | array | `["proxy:llm"]` | Access permissions for this key |
| `expires_at` | datetime | null | Optional expiration time |

**Response (201 Created):**

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "key": "opai-abc1def2ghi3jkl4mno5pqr6stu7vwx8",
  "name": "Production Gateway Key",
  "key_prefix": "opai-abc1…",
  "permissions": ["proxy:llm"],
  "is_active": true,
  "expires_at": "2026-12-31T23:59:59Z",
  "created_at": "2026-03-17T10:30:00Z",
  "warning": "Store this key securely. It will not be shown again."
}
```

Save the full `key` value immediately. You cannot retrieve it again.

### Via Admin Console

1. Navigate to **Settings > API Keys**
2. Click **Create New Key**
3. Enter a name and optional expiration date
4. Click **Create**
5. Copy the full key from the confirmation dialog and save it securely

## Key Permissions

Each API key carries a `permissions` array that controls what the key can do. Currently, the primary permission is:

| Permission | Description |
|------------|-------------|
| `proxy:llm` | Allows the key to proxy LLM requests (chat, embedding, completion) |

The default permission set is `["proxy:llm"]`. Reserved for future expansion: policy management, analytics access, and key administration.

## Role-Based Access Control (RBAC)

Users in an organization have roles that determine their access to management features. Roles are set at the user level, not at the API key level.

### Role Capabilities

| Role | API Keys | Provider Keys | Policy | Users | Analytics | Webhooks |
|------|----------|---------------|--------|-------|-----------|----------|
| **admin** | Create, list, revoke | Create, rotate, delete | Read, write | Manage, invite | Read | Read, write |
| **developer** | Create, list, revoke | — | Read | Read only | Read | — |
| **viewer** | List only | — | Read | Read only | Read | — |

### Role Descriptions

**Admin**
- Full access to all organization settings
- Can manage users, provider keys, and policies
- Can configure webhooks and view audit logs
- Can create and revoke API keys

**Developer**
- Can create and revoke their own API keys
- Can view organization settings and analytics
- Cannot modify organization policy or manage users
- Cannot manage provider keys or webhooks

**Viewer**
- Read-only access to all features
- Can view API keys, analytics, and logs
- Cannot create, modify, or delete anything
- Ideal for reporting and compliance roles

## Key Expiration

API keys support optional expiration:

```json
{
  "name": "Temporary Staging Key",
  "expires_at": "2026-04-17T23:59:59Z"
}
```

After expiration, the key becomes invalid for authentication. The key record remains in the database (not deleted) for audit purposes.

To list all keys (including expired ones):

```bash
curl -X GET https://api.openproxy.ai/api/v1/api-keys \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

Response includes all keys created by the current user in their organization, sorted by creation date (newest first).

## Revoking Keys

Revoke a key to immediately invalidate it:

```bash
curl -X DELETE https://api.openproxy.ai/api/v1/api-keys/{key_id} \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Response:** `204 No Content`

Revoked keys set `is_active = false` and are no longer usable, but the record remains in the database for audit purposes.

## Using API Keys

Once created, pass your API key in the `Authorization` header of proxy requests:

```bash
curl -X POST https://api.openproxy.ai/v1/chat/completions \
  -H "Authorization: Bearer opai-abc1def2ghi3jkl4mno5pqr6stu7vwx8" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "openai/gpt-4o",
    "messages": [
      {
        "role": "user",
        "content": "Hello, world!"
      }
    ]
  }'
```

## SSO / OIDC Configuration

For organizations needing federated authentication, OpenProxyAI supports OpenID Connect (OIDC).

### How OIDC Works

1. **Admin configures OIDC provider:** `PATCH /api/v1/organizations/current`
2. **Users are redirected to identity provider:** Auth-code flow
3. **JIT provisioning:** New users created automatically on first login
4. **Tokens mapped to users:** `sso_sub` field stores the provider's subject claim

### Configuration

Update organization OIDC settings:

```bash
curl -X PATCH https://api.openproxy.ai/api/v1/organizations/current \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "settings": {
      "oidc": {
        "issuer": "https://auth.example.com",
        "client_id": "your-client-id",
        "client_secret": "your-client-secret",
        "scopes": ["openid", "profile", "email"]
      }
    }
  }'
```

**OIDC Fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `issuer` | string | Yes | OIDC provider's base URL |
| `client_id` | string | Yes | OAuth 2.0 client ID |
| `client_secret` | string | Yes | OAuth 2.0 client secret (encrypted at rest) |
| `scopes` | array | No | OIDC scopes to request (default: `["openid", "profile", "email"]`) |

### Auth-Code Flow

1. **Redirect user to:** `https://api.openproxy.ai/auth/oidc/authorize?client_id=...&redirect_uri=...&state=...`
2. **User authenticates** at the configured identity provider
3. **Provider redirects back** with an authorization code
4. **Backend exchanges code** for an ID token (using client secret)
5. **JIT provisioning:** If user doesn't exist, create account with email from ID token
6. **Return access token** to client

### JIT Provisioning

When a new user authenticates via OIDC:

- A new `User` record is created if one doesn't exist for that email
- `sso_sub` is set to the provider's subject claim (unique identifier)
- User is assigned to the organization that configured OIDC
- Default role is `developer` (admins must be promoted manually)
- Password hash is not set (SSO-only user)

## Authentication Errors

### Invalid or Expired Key

```
HTTP 401 Unauthorized

{
  "detail": "Invalid API key"
}
```

- Verify key is active (`is_active = true`)
- Check key hasn't expired
- Confirm key prefix matches `opai-`

### Missing Authorization Header

```
HTTP 401 Unauthorized

{
  "detail": "Missing authentication credentials"
}
```

Include the `Authorization: Bearer <key>` header with all requests.

### Insufficient Permissions

```
HTTP 403 Forbidden

{
  "detail": "Permission denied"
}
```

The key's permissions don't allow this operation. Contact your organization admin to update permissions or create a new key.

## Security Best Practices

1. **Treat keys like passwords** — store securely (use environment variables or secrets manager)
2. **Rotate regularly** — create new keys and revoke old ones quarterly
3. **Use expiration dates** — set short TTLs for temporary keys
4. **Limit scope** — create separate keys for different applications
5. **Monitor usage** — review "Last Used" timestamps and audit logs
6. **Revoke immediately** — if a key is compromised, revoke it right away
7. **Enable SSO** — organizations with OIDC reduce password management burden
