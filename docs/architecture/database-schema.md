# OpenProxyAI Database Schema

OpenProxyAI uses PostgreSQL as the single source of truth for all persistent data. This document describes every table, its purpose, key columns, and relationships.

All tables use UUID primary keys generated server-side (`gen_random_uuid()`). Timestamps are in UTC.

## Table: organizations

**Purpose:** Tenant (organization) boundary for multi-tenancy. All other tables reference this.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | UUID | PK, DEFAULT gen_random_uuid() | Unique org identifier |
| name | VARCHAR(255) | NOT NULL | Display name (e.g., "Acme Corp") |
| slug | VARCHAR(100) | UNIQUE, NOT NULL | URL-safe identifier (e.g., "acme-corp") |
| plan | VARCHAR(50) | NOT NULL, DEFAULT 'free' | Feature tier: free, starter, growth, enterprise |
| settings | JSONB | NOT NULL, DEFAULT '{}' | Org-wide config (policy, SSO, webhooks, etc.) |
| budget_monthly_usd | NUMERIC(10,2) | Nullable | Monthly spend limit (optional) |
| is_active | BOOLEAN | NOT NULL, DEFAULT true | Soft delete flag |
| data_region | VARCHAR(50) | Nullable, DEFAULT 'us' | Data residency: us, eu, etc. |
| created_at | TIMESTAMP | NOT NULL, DEFAULT now() | Immutable creation timestamp |
| updated_at | TIMESTAMP | NOT NULL, DEFAULT now() | Updated on any write |

**Notes:**
- The `settings` JSONB column stores org-wide config: `{"policy": {...}, "webhooks": {...}, "sso": {...}}`
- Policy config is loaded into `PolicyConfig` dataclass at request time and cached in Redis
- Changing an org's plan via `settings` affects feature flags checked at request time

## Table: users

**Purpose:** Team members within an organization with role-based access control.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | UUID | PK, DEFAULT gen_random_uuid() | Unique user identifier |
| org_id | UUID | FK → organizations, NOT NULL, CASCADE | Org membership |
| email | VARCHAR(255) | UNIQUE, NOT NULL | Login identifier, verified at signup |
| name | VARCHAR(255) | Nullable | Display name |
| password_hash | VARCHAR(255) | NOT NULL | bcrypt hash of password |
| role | VARCHAR(50) | NOT NULL, DEFAULT 'developer', CHECK IN ('admin', 'developer', 'viewer') | RBAC role |
| budget_daily_usd | NUMERIC(10,2) | Nullable | Per-user daily spend cap (optional) |
| budget_monthly_usd | NUMERIC(10,2) | Nullable | Per-user monthly spend cap (optional) |
| is_active | BOOLEAN | NOT NULL, DEFAULT true | Soft delete / deactivation flag |
| last_login_at | TIMESTAMP | Nullable | Last successful auth timestamp |
| sso_sub | VARCHAR(500) | Nullable | OIDC subject claim (UUID or email from provider) |
| sso_connection_id | UUID | FK → sso_connections, Nullable, SET NULL | OIDC config this user signed up with |
| created_at | TIMESTAMP | NOT NULL, DEFAULT now() | Immutable |
| updated_at | TIMESTAMP | NOT NULL, DEFAULT now() | Updated on any write |

**Role Permissions:**
- `admin`: Full control (create users, manage keys, update policies, view analytics)
- `developer`: Can create API keys, view own usage, call LLM proxy
- `viewer`: Read-only access to dashboards, cannot create keys

**Budget Behavior:**
- If `budget_daily_usd` is set, user cannot exceed it per day
- If not set, defaults to org's `DEFAULT_BUDGET_DAILY_USD` (env var)
- Rate limiter checks both user and org budgets; uses the minimum

## Table: api_keys

**Purpose:** API credentials for programmatic access. Never store plaintext keys in database.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | UUID | PK, DEFAULT gen_random_uuid() | Unique key identifier |
| user_id | UUID | FK → users, NOT NULL, CASCADE | Key owner |
| org_id | UUID | FK → organizations, NOT NULL, CASCADE | Org (denormalized for query efficiency) |
| key_hash | VARCHAR(255) | UNIQUE, NOT NULL, INDEXED | SHA-256 hash of the key (never reveal plaintext) |
| key_prefix | VARCHAR(20) | NOT NULL | First 8 chars for display to user (e.g., "sk_org_a...") |
| name | VARCHAR(100) | Nullable | Optional friendly name (e.g., "production key") |
| permissions | JSONB | NOT NULL, DEFAULT '["proxy:llm"]' | Scopes: proxy:llm, analytics:read, etc. (future-proofing) |
| is_active | BOOLEAN | NOT NULL, DEFAULT true | Revocation flag |
| last_used_at | TIMESTAMP | Nullable | Timestamp of last successful request |
| expires_at | TIMESTAMP | Nullable | Optional expiration (null = never expires) |
| created_at | TIMESTAMP | NOT NULL, DEFAULT now() | Immutable |

**Auth Flow:**
1. Client sends `Authorization: Bearer {key_value}`
2. API endpoint hashes the key and queries by `key_hash`
3. Never decrypt or store the plaintext key

**Permissions Array:**
```json
["proxy:llm", "analytics:read"]
```

Currently only `proxy:llm` is implemented. Additional scopes are reserved for future fine-grained RBAC.

## Table: llm_provider_keys

**Purpose:** Encrypted API keys for LLM providers. Supports multiple keys per provider with weighted routing.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | UUID | PK, DEFAULT gen_random_uuid() | Unique provider key identifier |
| org_id | UUID | FK → organizations, NOT NULL, CASCADE | Org that owns this key |
| provider | VARCHAR(50) | NOT NULL | Provider name: openai, anthropic, azure, etc. |
| key_alias | VARCHAR(100) | NOT NULL | User-friendly alias (e.g., "openai-prod", "openai-staging") |
| api_key_encrypted | TEXT | NOT NULL | AES-256 encrypted provider API key |
| weight | INTEGER | NOT NULL, DEFAULT 1 | Routing weight for probabilistic selection (0 = disabled) |
| is_active | BOOLEAN | NOT NULL, DEFAULT true | Disable without deleting |
| model_patterns | JSON | Nullable | Array of fnmatch patterns (e.g., ["gpt-4*", "gpt-3.5*"]) |
| created_at | TIMESTAMP | NOT NULL, DEFAULT now() | Immutable |

**Weighted Routing Example:**

Org configures:
- OpenAI key A (weight=2, patterns=["gpt-4*"])
- OpenAI key B (weight=1, patterns=["gpt-4*"])
- OpenAI key C (weight=1, patterns=["gpt-3.5*"])

When requesting `gpt-4o`:
1. Filter by provider (openai) + active + weight > 0 → [A, B, C]
2. Filter by model pattern ("gpt-4*") → [A, B]
3. Random choice weighted by [2, 1] → 66% A, 33% B

When requesting `gpt-3.5-turbo`:
1. Filter → [C]
2. Use C (single match)

**Encryption:**
- Keys are encrypted at rest using `Fernet` (symmetric encryption)
- Decryption happens only when needed (in `_select_provider_key`)
- Never logged in plaintext

## Table: request_logs

**Purpose:** Immutable audit trail of every LLM request. Heavy write workload, optimized for analytics queries.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | UUID | PK, DEFAULT gen_random_uuid() | Unique log entry identifier |
| request_id | UUID | NOT NULL | Unique request ID (also in response header) |
| org_id | UUID | FK → organizations, NOT NULL | Org context |
| user_id | UUID | FK → users, NOT NULL | User who made the request |
| api_key_id | UUID | FK → api_keys, Nullable | Which API key was used (null if deleted after log) |
| model | VARCHAR(100) | NOT NULL | Model requested (e.g., "openai/gpt-4o") |
| provider | VARCHAR(50) | NOT NULL | Provider (openai, anthropic, azure, etc.) |
| prompt_tokens | INTEGER | NOT NULL, DEFAULT 0 | Input tokens |
| completion_tokens | INTEGER | NOT NULL, DEFAULT 0 | Output tokens |
| total_tokens | INTEGER | NOT NULL, DEFAULT 0 | Sum for convenience |
| cost_usd | NUMERIC(10,6) | NOT NULL, DEFAULT 0 | Calculated cost from token counts |
| latency_ms | INTEGER | Nullable | Total request duration |
| ttft_ms | INTEGER | Nullable | Time to first token (streaming only) |
| status_code | INTEGER | NOT NULL | HTTP status or internal code (-2=timeout, -3=cancelled, -4=blocked) |
| error_message | TEXT | Nullable | Error details (only if status != 200) |
| request_metadata | JSONB | NOT NULL, DEFAULT '{}' | Policy info, cache status, rate limit data, etc. |
| created_at | TIMESTAMP | NOT NULL, DEFAULT now() | Immutable |
| archived_at | TIMESTAMP | Nullable | Set by `archive_old_logs()` job after retention period |

**Indexes:**
```sql
INDEX idx_request_logs_org_created (org_id, created_at DESC)
INDEX idx_request_logs_user_created (user_id, created_at DESC)
INDEX idx_request_logs_model (model, created_at DESC)
```

**Status Code Meanings:**
- `200` — Success (OK)
- `402` — Budget exceeded
- `403` — Policy violation
- `429` — Rate limited
- `502/503/504` — Provider error
- `-2` — Timeout (internal)
- `-3` — Cancelled (internal)
- `-4` — Blocked by policy (internal)

**request_metadata Examples:**

Policy violation:
```json
{
  "policy": {
    "allowed": false,
    "action": "block",
    "reason_code": "pii_detected",
    "triggered_rules": ["pii_detection"],
    "detail": "Potential PII detected: ssn"
  }
}
```

Rate limit:
```json
{
  "policy": {
    "allowed": true,
    "action": "log_only"
  },
  "rate_limit": {
    "rpm": 100,
    "tpm": 100000
  }
}
```

Cache hit:
```json
{
  "cache": "hit"
}
```

**Retention and Archival:**
- Plans differ in retention: free=30 days, starter=90 days, growth/enterprise=365 days
- `archive_old_logs()` runs hourly, sets `archived_at` timestamp on expired logs
- Archived logs stay in PostgreSQL but are excluded from analytics queries (WHERE archived_at IS NULL)
- In Phase 3, logs migrate to ClickHouse for long-term storage

## Table: user_invites

**Purpose:** Pending and accepted team member invitations. Uses token-based verification.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | UUID | PK, DEFAULT gen_random_uuid() | Unique invite identifier |
| org_id | UUID | FK → organizations, NOT NULL, CASCADE | Org inviting the user |
| email | VARCHAR(255) | NOT NULL | Email address to invite |
| role | VARCHAR(50) | NOT NULL, DEFAULT 'developer', CHECK IN ('admin', 'developer', 'viewer') | Role assignment upon acceptance |
| token_hash | VARCHAR(255) | UNIQUE, NOT NULL | SHA-256 hash of random token (never store plaintext) |
| invited_by | UUID | FK → users, Nullable, SET NULL | Which admin sent the invite |
| expires_at | TIMESTAMP | NOT NULL | 7 days from creation (hard expiration) |
| accepted_at | TIMESTAMP | Nullable | Timestamp when invite was accepted (null = pending) |
| created_at | TIMESTAMP | NOT NULL, DEFAULT now() | Immutable |

**Indexes:**
```sql
INDEX idx_user_invites_org_pending (org_id, accepted_at, expires_at)
```

**Workflow:**
1. Admin calls `POST /api/v1/invites` with email
2. Backend generates random token, hashes it, stores `token_hash` in DB
3. Email sent to recipient with secret link: `https://app.openproxy.ai/accept?token={plaintext_token}`
4. Recipient clicks link, sends `POST /api/v1/auth/accept-invite` with token
5. Backend hashes received token, queries by `token_hash`, checks expiry
6. If valid, creates User and sets `accepted_at`

**Security:**
- Tokens are 32-character random strings (256 bits of entropy)
- Only hashes are persisted; plaintext is never stored
- Tokens expire after 7 days
- One-time use (invites cannot be reused)

## Table: sso_connections

**Purpose:** OIDC configuration for team SSO (one per org).

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | UUID | PK, DEFAULT gen_random_uuid() | Unique SSO config identifier |
| org_id | UUID | FK → organizations, NOT NULL, CASCADE | Org that owns this config (one per org) |
| provider_name | VARCHAR(100) | NOT NULL | Display name (e.g., "Auth0", "Okta", "Azure AD") |
| issuer_url | VARCHAR(500) | NOT NULL | OIDC issuer URL (e.g., "https://company.auth0.com") |
| client_id | VARCHAR(255) | NOT NULL | OIDC client ID from provider |
| client_secret_encrypted | TEXT | NOT NULL | AES-256 encrypted client secret |
| domain_hint | VARCHAR(255) | Nullable | Optional hint to provider (e.g., "example.com") |
| is_active | BOOLEAN | NOT NULL, DEFAULT true | Enable/disable without deleting |
| created_at | TIMESTAMP | NOT NULL, DEFAULT now() | Immutable |
| updated_at | TIMESTAMP | NOT NULL, DEFAULT now() | Updated on config change |

**OIDC Flow:**
1. User visits OpenProxyAI admin console
2. Console redirects to `/api/v1/sso/authorize?org_id={org_id}`
3. Backend retrieves SSO config, redirects to provider with PKCE code challenge
4. User authenticates at provider, provider redirects back to `/api/v1/sso/callback` with code
5. Backend exchanges code for ID token
6. Backend extracts `sub` claim (user ID from provider)
7. If user with `sso_sub = sub` exists, log in; otherwise, create new user (JIT provisioning)

**User-Provider Mapping:**
- `users.sso_sub` contains the OIDC `sub` claim (provider's unique user identifier)
- `users.sso_connection_id` points back to the SSO config used for signup

## Table: webhook_deliveries

**Purpose:** Track webhook delivery attempts for reliability and debugging.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | UUID | PK, DEFAULT gen_random_uuid() | Unique delivery identifier |
| org_id | UUID | FK → organizations, NOT NULL | Org that owns the webhook |
| webhook_url | TEXT | NOT NULL | HTTPS URL where event was sent |
| event_type | VARCHAR(100) | NOT NULL | Type of event (policy.violation, cost.anomaly, etc.) |
| payload | JSONB | NOT NULL | Event payload sent to webhook |
| status_code | INTEGER | NOT NULL | HTTP status from webhook receiver (0 if failed to connect) |
| error_message | TEXT | Nullable | Error details if delivery failed |
| attempt | INTEGER | NOT NULL | Retry attempt number (1 = first try) |
| scheduled_for | TIMESTAMP | NOT NULL | When this attempt is/was scheduled |
| created_at | TIMESTAMP | NOT NULL, DEFAULT now() | Immutable |

**Retry Logic:**
- Fire-and-forget webhook dispatch in `log_request` (no retries in critical path)
- Optional async retry job (Phase 3) checks failed deliveries and retries up to 3 times

## Materialized View: mv_daily_spend

**Purpose:** Fast aggregation for dashboard queries without hitting raw `request_logs`.

```sql
CREATE MATERIALIZED VIEW mv_daily_spend AS
SELECT
    org_id,
    user_id,
    model,
    provider,
    DATE_TRUNC('day', created_at) AS day,
    SUM(cost_usd) AS total_cost_usd,
    SUM(prompt_tokens) AS total_prompt_tokens,
    SUM(completion_tokens) AS total_completion_tokens,
    COUNT(*) AS total_requests,
    AVG(latency_ms) AS avg_latency_ms
FROM request_logs
WHERE status_code >= 0  -- Exclude failures
GROUP BY org_id, user_id, model, provider, day;

CREATE UNIQUE INDEX mv_daily_spend_key ON mv_daily_spend (org_id, user_id, model, provider, day);
```

**Refresh Schedule:**
- Refreshed every 5 minutes via `AsyncIOScheduler` in `app/main.py`
- Uses `REFRESH MATERIALIZED VIEW CONCURRENTLY` to avoid blocking reads

**Example Queries:**
```sql
-- Org spend for last 30 days
SELECT day, SUM(total_cost_usd) FROM mv_daily_spend
WHERE org_id = 'xxx' AND day >= NOW() - INTERVAL '30 days'
GROUP BY day
ORDER BY day DESC;

-- Top models by cost
SELECT model, SUM(total_cost_usd) as cost
FROM mv_daily_spend
WHERE org_id = 'xxx' AND day >= NOW() - INTERVAL '7 days'
GROUP BY model
ORDER BY cost DESC;

-- Per-user breakdown
SELECT user_id, SUM(total_cost_usd) FROM mv_daily_spend
WHERE org_id = 'xxx' AND day = CURRENT_DATE
GROUP BY user_id;
```

## Migration Chain

The schema is versioned with Alembic. Migrations run automatically at startup (`alembic upgrade head`):

1. **54c0ed90559e** — Initial schema
   - organizations, users, api_keys, llm_provider_keys, request_logs
   - Materialized view mv_daily_spend

2. **c4f9a12e8b7d** — GIN index on request_metadata
   - Allows efficient JSONB queries in future

3. **b3e8d87fd2f1** — Add unique index to mv_daily_spend
   - Enables concurrent refresh

4. **d4e7f12a9c3b** — Add user_invites table
   - Invite system with SHA-256 token hashing

5. **e5f8a23b4c1d** — Add SSO support
   - sso_connections table
   - Add sso_sub and sso_connection_id to users

6. **f1a9c3e7d5b2** — Audit log immutability
   - Add archived_at to request_logs
   - RLS policy for immutability (Phase 3)

7. **a2b3c4d5e6f7** — Add webhook_deliveries table
   - Track webhook delivery attempts

8. **b1c2d3e4f5a6** — Add model_patterns to llm_provider_keys
   - Support model-specific key routing

9. **c3d4e5f6a7b8** — Add data_region to organizations
   - Support multi-region deployments

Run `alembic history` to see current state:

```bash
alembic history
# 54c0ed90559e -> c4f9a12e8b7d
# c4f9a12e8b7d -> b3e8d87fd2f1
# ...
# c3d4e5f6a7b8 (head)
```

To create a new migration after schema changes:

```bash
alembic revision --autogenerate -m "describe_change"
alembic upgrade head
```

## PostgreSQL Extensions

The schema requires one extension (created in the initial migration):

```sql
CREATE EXTENSION IF NOT EXISTS pgcrypto;
```

`pgcrypto` provides `gen_random_uuid()` for UUID generation.

In Phase 3, consider also:
- `uuid-ossp` — Alternative UUID generation
- `pg_trgm` — Text search trigrams for prompt search
- `timescaledb` — Time-series optimizations for request_logs

## Performance Considerations

### Indexes

- `api_keys.key_hash` — UNIQUE, for auth lookups
- `request_logs.idx_request_logs_org_created` — For org analytics
- `request_logs.idx_request_logs_user_created` — For per-user breakdown
- `request_logs.idx_request_logs_model` — For model-specific queries
- `user_invites.idx_user_invites_org_pending` — For pending invites
- `mv_daily_spend` (unique index) — Enables concurrent refresh

### Query Patterns

- **Auth:** `SELECT FROM api_keys WHERE key_hash = $1` — Single-row index lookup, ~1ms
- **Policy load:** `SELECT FROM organizations WHERE id = $1` — Single-row lookup, ~1ms
- **Spend by org:** `SELECT FROM mv_daily_spend WHERE org_id = $1 AND day >= $2` — Materialized view, ~10ms
- **Request history:** `SELECT FROM request_logs WHERE org_id = $1 AND created_at > $2 AND archived_at IS NULL` — Index range scan, ~50-100ms for 1M rows

### Optimization Strategy

- PostgreSQL handles all queries up to ~10M request_logs rows
- At >10M rows, migrate request_logs to ClickHouse (Phase 3) and keep PostgreSQL for operational data only
- Keep only last 30 days in PostgreSQL, archive older to ClickHouse or S3

## Backup and Recovery

### Backup Strategy

- **Type:** Full logical backup via `pg_dump`
- **Frequency:** Daily snapshots
- **Retention:** 30 days
- **Command:** `pg_dump postgresql://user:pass@host/openproxyai > backup.sql`

### Recovery

```bash
# Restore from dump
psql postgresql://user:pass@host/openproxyai < backup.sql

# Or via managed database restore (RDS, Cloud SQL, Azure Database)
```

### WAL Archiving (Optional)

For point-in-time recovery, enable WAL archiving:

```sql
ALTER SYSTEM SET wal_level = replica;
ALTER SYSTEM SET max_wal_senders = 10;
ALTER SYSTEM SET wal_keep_size = '10GB';
```

Then restart PostgreSQL.
