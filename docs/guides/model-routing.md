# Model Routing

> **Applies to:** All plans

Model routing allows you to configure API keys for multiple LLM providers and control which provider keys are used for different models. This guide covers provider key management, weighted selection, and pattern-based routing.

## Provider Keys

A provider key is a credential (API key) for an LLM provider (OpenAI, Anthropic, Azure, etc.) stored encrypted in the database. Multiple provider keys can be configured per organization and per provider, enabling load balancing and failover.

### Key Properties

| Property | Type | Description |
|----------|------|-------------|
| `id` | UUID | Unique identifier |
| `provider` | string | Provider name (e.g., `openai`, `anthropic`, `azure`) |
| `key_alias` | string | Friendly name for this specific key |
| `api_key_encrypted` | string | Encrypted provider API key (stored securely) |
| `weight` | integer | Selection weight for weighted random routing (1-100) |
| `is_active` | boolean | Whether this key is usable |
| `model_patterns` | array[string] | fnmatch patterns for model-specific routing |
| `created_at` | datetime | Creation timestamp |

## Creating a Provider Key

Create a new provider key via `POST /api/v1/provider-keys`:

```bash
curl -X POST https://api.openproxy.ai/api/v1/provider-keys \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "openai",
    "key_alias": "Production Key 1",
    "api_key": "sk-...",
    "weight": 5
  }'
```

**Request Body:**

| Field | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| `provider` | string | Yes | 1-50 chars | Provider identifier (e.g., `openai`, `anthropic`, `azure`) |
| `key_alias` | string | Yes | 1-100 chars | Friendly name for this key |
| `api_key` | string | Yes | 8+ chars | Raw API key (stored encrypted, never returned) |
| `weight` | integer | No | 1-100, default=1 | Selection weight for load balancing |

**Response (201 Created):**

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "provider": "openai",
  "key_alias": "Production Key 1",
  "key_prefix": "sk-abc1…",
  "weight": 5,
  "is_active": true,
  "created_at": "2026-03-17T10:30:00Z"
}
```

Note: The raw API key is encrypted and never returned. The response includes only a masked prefix (`key_prefix`).

## Listing Provider Keys

List all provider keys for the organization:

```bash
curl -X GET https://api.openproxy.ai/api/v1/provider-keys \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Response:**

```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "provider": "openai",
    "key_alias": "Production Key 1",
    "key_prefix": "sk-abc1…",
    "weight": 5,
    "is_active": true,
    "created_at": "2026-03-17T10:30:00Z"
  },
  {
    "id": "660e8400-e29b-41d4-a716-446655440001",
    "provider": "openai",
    "key_alias": "Production Key 2",
    "key_prefix": "sk-def2…",
    "weight": 3,
    "is_active": true,
    "created_at": "2026-03-17T10:35:00Z"
  }
]
```

## Weighted Load Balancing

When multiple provider keys exist for the same provider, requests are distributed using weighted random selection.

**Example:** Two OpenAI keys with weights 5 and 3

```json
[
  {
    "provider": "openai",
    "key_alias": "Key 1",
    "weight": 5
  },
  {
    "provider": "openai",
    "key_alias": "Key 2",
    "weight": 3
  }
]
```

Distribution: Key 1 gets ~62% of requests, Key 2 gets ~38% of requests.

To adjust distribution, update the weight:

```bash
curl -X PATCH https://api.openproxy.ai/api/v1/provider-keys/{key_id} \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "weight": 10
  }'
```

## Model Pattern Routing

Direct specific models to specific provider keys using fnmatch patterns. This is useful when:

- Different models are hosted on different provider accounts
- You want gpt-4 on one key and gpt-3.5-turbo on another
- A provider key has quota limits per model

### Pattern Syntax

Uses standard fnmatch glob syntax:

| Pattern | Matches |
|---------|---------|
| `openai/gpt-4o` | Exact match: `openai/gpt-4o` |
| `openai/gpt-4*` | All gpt-4 variants: `openai/gpt-4o`, `openai/gpt-4-turbo`, etc. |
| `openai/*` | All OpenAI models |
| `*/embedding*` | Embedding models from any provider |
| `*` | All models (default if patterns empty) |

### Configuration

When creating or updating a provider key, include `model_patterns`:

```bash
curl -X POST https://api.openproxy.ai/api/v1/provider-keys \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "openai",
    "key_alias": "GPT-4 Only Key",
    "api_key": "sk-...",
    "weight": 5,
    "model_patterns": ["openai/gpt-4*"]
  }'
```

Currently, `model_patterns` is not exposed in the PATCH request schema but is set during creation. To change patterns, delete and recreate the key.

### Routing Logic

When a request comes in for a model:

1. **Find all active keys** for the provider with weight > 0
2. **Filter by model pattern:**
   - If any keys match the model pattern, use only matching keys
   - If no keys match the pattern, use all keys (fallback)
3. **Select by weight:** Randomly choose from the candidate set weighted by their weights
4. **Use the key:** Decrypt the selected key's `api_key_encrypted` and forward to LiteLLM

**Example:** Request for `openai/gpt-4o`

Keys available:
- Key A: pattern=`["openai/gpt-4*"]`, weight=5 ← matches
- Key B: pattern=`["openai/gpt-3.5*"]`, weight=3 ← doesn't match
- Key C: pattern=`[]`, weight=2 ← no pattern (catch-all)

Routing: 100% chance to use Key A (only match) instead of falling back to all keys.

## Updating Provider Keys

Update provider key metadata (alias, weight, active status):

```bash
curl -X PATCH https://api.openproxy.ai/api/v1/provider-keys/{key_id} \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "key_alias": "Updated Name",
    "weight": 8,
    "is_active": true
  }'
```

**Request Fields (all optional):**

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `key_alias` | string | 1-100 chars | Friendly name |
| `weight` | integer | 1-100 | Selection weight |
| `is_active` | boolean | — | Whether key is usable |

**Response:** Updated ProviderKeyResponse (same as create response)

Note: You cannot update the raw API key via PATCH. Use key rotation instead.

## Key Rotation

Rotate a provider key to re-encrypt it with a fresh Fernet token (zero-downtime):

```bash
curl -X POST https://api.openproxy.ai/api/v1/provider-keys/{key_id}/rotate \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Response:**

```json
{
  "rotated": true,
  "key_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**What happens:**

1. The plaintext API key is decrypted
2. It's re-encrypted with a fresh Fernet token
3. The new ciphertext replaces the old one in the database
4. The plaintext value itself never changes (same API key with provider)
5. Requests continue seamlessly (zero-downtime)

**When to rotate:**

- Quarterly security rotation (best practice)
- After an encryption key rollover
- For SOC 2 CC9.2 compliance (vendor risk management)
- No need to notify the provider — the key value is unchanged

## Disabling a Provider Key

Prevent a key from being used without deleting it:

```bash
curl -X PATCH https://api.openproxy.ai/api/v1/provider-keys/{key_id} \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "is_active": false
  }'
```

The key record remains in the database (for audit) but is excluded from routing (`is_active` check).

## Deleting a Provider Key

Permanently remove a provider key:

```bash
curl -X DELETE https://api.openproxy.ai/api/v1/provider-keys/{key_id} \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Response:** `204 No Content`

The key is permanently deleted. Audit logs retain the fact that it existed.

## Provider Fallback

If no provider keys are configured for a provider, OpenProxyAI falls back to environment variables:

| Provider | Environment Variable |
|----------|----------------------|
| `openai` | `OPENAI_API_KEY` |
| `anthropic` | `ANTHROPIC_API_KEY` |
| `azure` | `AZURE_API_KEY` |

Fallback is used only if:

1. No `LLMProviderKey` records exist for the provider, OR
2. All existing keys are inactive (`is_active = false`), OR
3. All existing keys have weight 0

Recommendation: For production, always use provider keys (database) instead of relying on environment variable fallback.

## Multi-Provider Routing

Configure keys for multiple providers simultaneously:

```json
[
  {
    "provider": "openai",
    "key_alias": "OpenAI Production",
    "weight": 5,
    "is_active": true
  },
  {
    "provider": "anthropic",
    "key_alias": "Anthropic Production",
    "weight": 5,
    "is_active": true
  },
  {
    "provider": "azure",
    "key_alias": "Azure Internal",
    "weight": 3,
    "is_active": true
  }
]
```

Requests for `openai/gpt-4o` use the OpenAI key, while `anthropic/claude-3-sonnet` uses the Anthropic key, and so on.

## Error Handling

### No Keys Available

```
HTTP 400 Bad Request

{
  "error": "invalid_request_error",
  "detail": "No provider keys available for provider 'openai'"
}
```

Configure at least one active provider key or set the environment variable fallback.

### Invalid Model Format

```
HTTP 400 Bad Request

{
  "error": "invalid_model",
  "detail": "Model not supported"
}
```

Model must be in the format `provider/model-name` (e.g., `openai/gpt-4o`).

## Permissions

Only users with role `admin` can:

- Create provider keys (`POST /api/v1/provider-keys`)
- Update provider keys (`PATCH /api/v1/provider-keys/{key_id}`)
- Rotate provider keys (`POST /api/v1/provider-keys/{key_id}/rotate`)
- Delete provider keys (`DELETE /api/v1/provider-keys/{key_id}`)

Users with role `developer` or `viewer` can only list keys.

Attempting to create/update without admin role returns:

```
HTTP 403 Forbidden

{
  "detail": "Only admins can manage provider keys"
}
```
