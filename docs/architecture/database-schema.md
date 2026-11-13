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
| plan | VARCHAR(50) | NOT NULL, DEFAULT 'community' | Feature tier: community, team, business, enterprise, metered |
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
| region | VARCHAR(10) | NOT NULL, DEFAULT 'us', CHECK IN ('us', 'eu', 'ap', 'global') | Data residency region for this key |
| model_patterns | JSON | Nullable | Array of fnmatch patterns (e.g., ["gpt-4*", "gpt-3.5*"]) |
| created_at | TIMESTAMP | NOT NULL, DEFAULT now() | Immutable |

**Region Filtering:**

When an org has `data_region = 'eu'`, only provider keys with `region = 'eu'` or `region = 'global'` are eligible for routing. This ensures EU orgs never route through US-only keys.

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

**Purpose:** Append-only audit trail of every LLM request (the application role can insert, and only set `archived_at`). Heavy write workload, optimized for analytics queries.

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
- `446` — Blocked by policy
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
- Plans differ in retention: community=7 days, team=30, business=90, enterprise=365 (metered=90)
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

## Table: semantic_cache_entries

**Purpose:** L3 semantic cache — stores embeddings of past requests for cosine-similarity matching. Requires pgvector extension.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | UUID | PK, DEFAULT gen_random_uuid() | Unique cache entry identifier |
| org_id | UUID | FK → organizations, NOT NULL, CASCADE | Org boundary for cache isolation |
| model | VARCHAR(100) | NOT NULL | Model that produced the cached response |
| messages_hash | VARCHAR(64) | NOT NULL | SHA-256 of the original messages (dedup key) |
| embedding | VECTOR(1536) | NOT NULL | Embedding of concatenated message content |
| response_json | JSONB | NOT NULL | Full cached LLM response |
| token_count | INTEGER | NOT NULL, DEFAULT 0 | Tokens saved on cache hit |
| expires_at | TIMESTAMP | NOT NULL | TTL-based expiration |
| created_at | TIMESTAMP | NOT NULL, DEFAULT now() | Immutable |

**Indexes:**
```sql
INDEX idx_semantic_cache_org_model (org_id, model)
-- ivfflat index on embedding column for approximate nearest neighbor search
```

**Cache Lookup Flow:**
1. Embed the incoming request messages via `text-embedding-3-small`
2. Query for nearest neighbor within same org + model where `expires_at > now()`
3. If cosine similarity >= threshold (default 0.95), return cached response
4. Fire-and-forget task creates its own DB session (not request-scoped) to avoid session lifetime issues

## Table: prompt_templates

**Purpose:** Versioned prompt templates for the playground feature. Supports `{{variable}}` substitution.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | UUID | PK, DEFAULT gen_random_uuid() | Unique template identifier |
| org_id | UUID | FK → organizations, NOT NULL, CASCADE | Org boundary |
| name | VARCHAR(255) | NOT NULL | Template display name |
| description | TEXT | Nullable | Optional description |
| system_message | TEXT | Nullable | System prompt template |
| user_template | TEXT | NOT NULL | User message template with `{{variables}}` |
| variables_schema | JSONB | NOT NULL, DEFAULT '[]' | Array of `{name, type, default}` variable definitions |
| version | INTEGER | NOT NULL, DEFAULT 1 | Auto-incremented on update |
| is_active | BOOLEAN | NOT NULL, DEFAULT true | Soft-delete flag |
| created_by | UUID | FK → users, Nullable, SET NULL | Creator |
| created_at | TIMESTAMP | NOT NULL, DEFAULT now() | Immutable |
| updated_at | TIMESTAMP | NOT NULL, DEFAULT now() | Updated on any write |

**Indexes:**
```sql
INDEX idx_prompt_templates_org_active (org_id, is_active)
```

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

The schema is versioned with Alembic (`backend/alembic/versions/`, 57 revisions). Migrations run at startup (`alembic upgrade head`). The current head is `v7w8x9y0z1a2`, a merge of the spaces and SCIM branches. List the full chain with `alembic history`.

## Tables Added After the Initial Schema

Generated from the SQLAlchemy models (`backend/app/models/`), so it matches the code. Org-scoped tables use row-level security. Later migrations also add columns to the tables above (provider-key `api_base`, `max_data_class` and secret-store sources, request-log routing and stage metadata, plan names `community`, `team`, `business`, `enterprise`); the models are the reference for those. `admin_audit_logs`, `conversation_context_packages` and the request log are append-only for the application role.

### Teams

#### Table: teams

| Column | Type | Null | Notes |
|---|---|---|---|
| org_id | uuid | no | -> organizations.id (CASCADE) |
| name | varchar(255) | no |  |
| budget_monthly_usd | numeric(10, 2) | yes |  |
| id | uuid | no | primary key; default gen_random_uuid() |
| created_at | timestamp without time zone | no | default now() |
| updated_at | timestamp without time zone | no | default now() |

#### Table: team_members

| Column | Type | Null | Notes |
|---|---|---|---|
| team_id | uuid | no | primary key; -> teams.id (CASCADE) |
| user_id | uuid | no | primary key; -> users.id (CASCADE) |

### Experiments and scoring

#### Table: experiments

| Column | Type | Null | Notes |
|---|---|---|---|
| org_id | uuid | no | -> organizations.id (CASCADE) |
| name | varchar(255) | no |  |
| target_model | varchar(100) | no |  |
| is_active | boolean | no | default true |
| mode | varchar(10) | no | default static |
| metric | varchar(100) | yes |  |
| min_samples_per_variant | integer | no | default 30 |
| delta | numeric(5, 4) | no | default 0.0100 |
| weight_floor | integer | no | default 5 |
| winner_variant_id | uuid | yes | -> experiment_variants.id (SET NULL) |
| stopped_reason | varchar(20) | yes |  |
| adaptive_error | text | yes |  |
| adaptive_updated_at | timestamp without time zone | yes |  |
| id | uuid | no | primary key; default gen_random_uuid() |
| created_at | timestamp without time zone | no | default now() |
| updated_at | timestamp without time zone | no | default now() |

#### Table: experiment_variants

| Column | Type | Null | Notes |
|---|---|---|---|
| experiment_id | uuid | no | -> experiments.id (CASCADE) |
| model | varchar(100) | no |  |
| traffic_weight | integer | no | default 50 |
| id | uuid | no | primary key; default gen_random_uuid() |

#### Table: request_scores

| Column | Type | Null | Notes |
|---|---|---|---|
| request_id | uuid | no |  |
| org_id | uuid | no | -> organizations.id (CASCADE) |
| experiment_id | uuid | yes | -> experiments.id (CASCADE) |
| variant_id | uuid | yes | -> experiment_variants.id (CASCADE) |
| score_name | varchar(100) | no |  |
| value | numeric(10, 4) | no |  |
| source | varchar(20) | no | default console |
| comment | text | yes |  |
| user_id | uuid | yes | -> users.id (SET NULL) |
| created_at | timestamp without time zone | no | default now() |
| id | uuid | no | primary key; default gen_random_uuid() |

#### Table: request_payloads

| Column | Type | Null | Notes |
|---|---|---|---|
| request_id | uuid | no |  |
| org_id | uuid | no | -> organizations.id (CASCADE) |
| messages | jsonb | no |  |
| output | text | no |  |
| redacted | boolean | no | default false |
| created_at | timestamp without time zone | no | default now() |
| expires_at | timestamp with time zone | no |  |
| id | uuid | no | primary key; default gen_random_uuid() |

### Datasets and evaluation

#### Table: datasets

| Column | Type | Null | Notes |
|---|---|---|---|
| org_id | uuid | no | -> organizations.id (CASCADE) |
| name | varchar(100) | no |  |
| description | varchar(500) | yes |  |
| created_by | uuid | yes | -> users.id (SET NULL) |
| created_at | timestamp without time zone | no | default now() |
| id | uuid | no | primary key; default gen_random_uuid() |

#### Table: dataset_items

| Column | Type | Null | Notes |
|---|---|---|---|
| org_id | uuid | no | -> organizations.id (CASCADE) |
| dataset_id | uuid | no | -> datasets.id (CASCADE) |
| request_id | uuid | yes |  |
| messages | jsonb | no |  |
| output | text | yes |  |
| expected | text | yes |  |
| created_at | timestamp without time zone | no | default now() |
| id | uuid | no | primary key; default gen_random_uuid() |

#### Table: evaluators

| Column | Type | Null | Notes |
|---|---|---|---|
| org_id | uuid | no | -> organizations.id (CASCADE) |
| name | varchar(100) | no |  |
| type | varchar(20) | no |  |
| config | jsonb | no |  |
| created_by | uuid | yes | -> users.id (SET NULL) |
| created_at | timestamp without time zone | no | default now() |
| id | uuid | no | primary key; default gen_random_uuid() |

#### Table: eval_runs

| Column | Type | Null | Notes |
|---|---|---|---|
| org_id | uuid | no | -> organizations.id (CASCADE) |
| dataset_id | uuid | yes | -> datasets.id (SET NULL) |
| evaluator_id | uuid | yes | -> evaluators.id (SET NULL) |
| evaluator_snapshot | jsonb | no |  |
| prompt_template_id | uuid | yes | -> prompt_templates.id (SET NULL) |
| prompt_fingerprint | varchar(64) | yes |  |
| candidate_model | varchar(100) | no |  |
| system_prompt | text | yes |  |
| status | varchar(20) | no | default queued |
| total_items | integer | no | default 0 |
| completed_items | integer | no | default 0 |
| failed_items | integer | no | default 0 |
| passed_items | integer | no | default 0 |
| score_sum | numeric(14, 4) | no | default 0 |
| cost_usd | numeric(12, 6) | no | default 0 |
| max_cost_usd | numeric(12, 6) | no |  |
| error | text | yes |  |
| created_by | uuid | yes | -> users.id (SET NULL) |
| created_at | timestamp without time zone | no | default now() |
| started_at | timestamp without time zone | yes |  |
| finished_at | timestamp without time zone | yes |  |
| id | uuid | no | primary key; default gen_random_uuid() |

#### Table: eval_run_items

| Column | Type | Null | Notes |
|---|---|---|---|
| org_id | uuid | no | -> organizations.id (CASCADE) |
| run_id | uuid | no | -> eval_runs.id (CASCADE) |
| dataset_item_id | uuid | yes | -> dataset_items.id (SET NULL) |
| output | text | yes |  |
| score | numeric(6, 4) | yes |  |
| passed | boolean | yes |  |
| reason | text | yes |  |
| error | text | yes |  |
| cost_usd | numeric(12, 6) | no | default 0 |
| latency_ms | integer | yes |  |
| created_at | timestamp without time zone | no | default now() |
| id | uuid | no | primary key; default gen_random_uuid() |

### Governance

#### Table: model_registry

| Column | Type | Null | Notes |
|---|---|---|---|
| org_id | uuid | no | -> llm_provider_keys.org_id (SET NULL (provider_key_id)); -> organizations.id (CASCADE) |
| model_id | varchar(200) | no |  |
| provider | varchar(50) | no |  |
| provider_key_id | uuid | yes | -> llm_provider_keys.id (SET NULL (provider_key_id)) |
| max_data_class | varchar(20) | no | default internal |
| regions | json | no |  |
| risk_rating | varchar(10) | no | default medium |
| retention_days | integer | yes |  |
| trains_on_data | boolean | no | default false |
| capabilities | json | no |  |
| cost_tier | varchar(10) | yes |  |
| owner | varchar(200) | yes |  |
| enabled | boolean | no | default true |
| created_at | timestamp without time zone | no | default now() |
| updated_at | timestamp without time zone | no | default now() |
| id | uuid | no | primary key; default gen_random_uuid() |

Check `ck_model_registry_risk`: `risk_rating IN ('low', 'medium', 'high')`

Check `ck_model_registry_cost_tier`: `cost_tier IS NULL OR cost_tier IN ('low', 'medium', 'high')`

Check `ck_model_registry_data_class`: `max_data_class IN ('public', 'internal', 'confidential', 'secret')`

Check `ck_model_registry_retention`: `retention_days IS NULL OR retention_days >= 0`

#### Table: policy_plugins

| Column | Type | Null | Notes |
|---|---|---|---|
| org_id | uuid | no | -> organizations.id (CASCADE) |
| name | varchar(60) | no |  |
| module | bytea | no |  |
| sha256 | varchar(64) | no |  |
| size_bytes | integer | no |  |
| enabled | boolean | no | default true |
| created_by | uuid | yes | -> users.id (SET NULL) |
| created_at | timestamp without time zone | no | default now() |
| id | uuid | no | primary key; default gen_random_uuid() |

Check `ck_policy_plugins_size`: `size_bytes > 0 AND size_bytes <= 1048576`

#### Table: admin_audit_logs

| Column | Type | Null | Notes |
|---|---|---|---|
| org_id | uuid | no | -> organizations.id (CASCADE) |
| actor_id | uuid | yes | -> users.id (SET NULL) |
| actor_email | varchar(255) | no |  |
| action | varchar(100) | no |  |
| resource_type | varchar(50) | no |  |
| resource_id | varchar(255) | yes |  |
| before | jsonb | yes |  |
| after | jsonb | yes |  |
| ip_address | varchar(45) | yes |  |
| created_at | timestamp with time zone | no | default now() |
| id | uuid | no | primary key; default gen_random_uuid() |

### MCP gateway

#### Table: mcp_servers

| Column | Type | Null | Notes |
|---|---|---|---|
| org_id | uuid | no | -> organizations.id (CASCADE) |
| name | varchar(40) | no |  |
| url | text | no |  |
| auth_header_encrypted | text | yes |  |
| pin_mode | varchar(10) | no | default warn |
| scan_mode | varchar(10) | no | default log |
| is_active | boolean | no | default true |
| created_at | timestamp without time zone | no | default now() |
| id | uuid | no | primary key; default gen_random_uuid() |

#### Table: mcp_tools

| Column | Type | Null | Notes |
|---|---|---|---|
| org_id | uuid | no | -> organizations.id (CASCADE) |
| server_id | uuid | no | -> mcp_servers.id (CASCADE) |
| name | varchar(200) | no |  |
| definition | jsonb | no |  |
| current_hash | varchar(64) | no |  |
| approved_hash | varchar(64) | yes |  |
| approved_snapshot | jsonb | yes |  |
| status | varchar(10) | no | default pending |
| approved_by | uuid | yes | -> users.id (SET NULL) |
| approved_at | timestamp without time zone | yes |  |
| first_seen_at | timestamp without time zone | no | default now() |
| last_seen_at | timestamp without time zone | no | default now() |
| id | uuid | no | primary key; default gen_random_uuid() |

Check `ck_mcp_tools_status`: `status IN ('pending', 'approved', 'drifted', 'blocked')`

#### Table: mcp_tool_versions

| Column | Type | Null | Notes |
|---|---|---|---|
| org_id | uuid | no | -> organizations.id (CASCADE) |
| tool_id | uuid | no | -> mcp_tools.id (CASCADE) |
| hash | varchar(64) | no |  |
| definition | jsonb | no |  |
| seen_at | timestamp without time zone | no | default now() |
| id | uuid | no | primary key; default gen_random_uuid() |

#### Table: mcp_bundles

| Column | Type | Null | Notes |
|---|---|---|---|
| org_id | uuid | no | -> organizations.id (CASCADE) |
| slug | varchar(40) | no |  |
| name | varchar(100) | no |  |
| description | text | yes |  |
| is_active | boolean | no | default true |
| created_at | timestamp without time zone | no | default now() |
| id | uuid | no | primary key; default gen_random_uuid() |

Check `ck_mcp_bundles_slug`: `slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$' AND char_length(slug) <= 40`

#### Table: mcp_bundle_tools

| Column | Type | Null | Notes |
|---|---|---|---|
| org_id | uuid | no | -> organizations.id (CASCADE) |
| bundle_id | uuid | no | -> mcp_bundles.id (CASCADE) |
| tool_pattern | varchar(200) | no |  |
| id | uuid | no | primary key; default gen_random_uuid() |

#### Table: api_key_mcp_bundles

| Column | Type | Null | Notes |
|---|---|---|---|
| api_key_id | uuid | no | primary key; -> api_keys.id (CASCADE) |
| bundle_id | uuid | no | primary key; -> mcp_bundles.id (CASCADE) |
| org_id | uuid | no | -> organizations.id (CASCADE) |
| created_at | timestamp without time zone | no | default now() |

#### Table: tool_grants

| Column | Type | Null | Notes |
|---|---|---|---|
| org_id | uuid | no | -> organizations.id (CASCADE) |
| subject_type | varchar(10) | no |  |
| subject_id | varchar(64) | no |  |
| tool_pattern | varchar(200) | no |  |
| effect | varchar(5) | no |  |
| created_by | uuid | yes | -> users.id (SET NULL) |
| created_at | timestamp without time zone | no | default now() |
| id | uuid | no | primary key; default gen_random_uuid() |

Check `ck_tool_grants_effect`: `effect IN ('allow', 'deny')`

Check `ck_tool_grants_subject_type`: `subject_type IN ('role', 'team', 'user', 'api_key')`

#### Table: tool_trust_rules

| Column | Type | Null | Notes |
|---|---|---|---|
| org_id | uuid | no | -> organizations.id (CASCADE) |
| tool_pattern | varchar(200) | no |  |
| rule | varchar(20) | no |  |
| created_by | uuid | yes | -> users.id (SET NULL) |
| created_at | timestamp without time zone | no | default now() |
| id | uuid | no | primary key; default gen_random_uuid() |

Check `ck_tool_trust_rules_rule`: `rule IN ('trusted_output', 'sink')`

### Conversations

#### Table: conversations

| Column | Type | Null | Notes |
|---|---|---|---|
| org_id | uuid | no | -> organizations.id (CASCADE) |
| owner_id | uuid | no | -> users.id (CASCADE) |
| team_id | uuid | yes | -> teams.id (SET NULL) |
| title | varchar(200) | no |  |
| system_prompt | text | yes |  |
| visibility | varchar(10) | no | default private |
| tags | jsonb | no | default [] |
| space_id | uuid | yes | -> spaces.id (SET NULL) |
| created_at | timestamp without time zone | no | default now() |
| updated_at | timestamp without time zone | no | default now() |
| id | uuid | no | primary key; default gen_random_uuid() |

Check `ck_conversations_visibility`: `visibility IN ('private', 'team', 'org')`

#### Table: conversation_turns

| Column | Type | Null | Notes |
|---|---|---|---|
| org_id | uuid | no | -> organizations.id (CASCADE) |
| conversation_id | uuid | no | -> conversations.id (CASCADE) |
| seq | integer | no |  |
| role | varchar(10) | no |  |
| content | text | no |  |
| data_class | varchar(20) | no |  |
| model | varchar(100) | yes |  |
| created_at | timestamp without time zone | no | default now() |
| id | uuid | no | primary key; default gen_random_uuid() |

Check `ck_conversation_turns_role`: `role IN ('user', 'assistant')`

#### Table: conversation_context_packages

| Column | Type | Null | Notes |
|---|---|---|---|
| org_id | uuid | no | -> organizations.id (CASCADE) |
| conversation_id | uuid | no | -> conversations.id (CASCADE) |
| assistant_turn_id | uuid | yes | -> conversation_turns.id (SET NULL) |
| model | varchar(100) | no |  |
| data_class | varchar(20) | no |  |
| routing_mode | varchar(10) | no |  |
| included_turn_ids | jsonb | no |  |
| withheld | jsonb | no |  |
| would_withhold | jsonb | no | default [] |
| estimated_tokens | integer | no |  |
| payload_sha256 | varchar(64) | no |  |
| outcome | varchar(10) | no |  |
| created_at | timestamp without time zone | no | default now() |
| id | uuid | no | primary key; default gen_random_uuid() |

#### Table: spaces

| Column | Type | Null | Notes |
|---|---|---|---|
| org_id | uuid | no | -> organizations.id (CASCADE) |
| owner_id | uuid | no | -> users.id (CASCADE) |
| team_id | uuid | yes | -> teams.id (SET NULL) |
| name | varchar(100) | no |  |
| created_at | timestamp without time zone | no | default now() |
| id | uuid | no | primary key; default gen_random_uuid() |

### Batches

#### Table: batch_files

| Column | Type | Null | Notes |
|---|---|---|---|
| org_id | uuid | no | -> organizations.id (CASCADE) |
| user_id | uuid | no | -> users.id (CASCADE) |
| filename | varchar(255) | no |  |
| purpose | varchar(10) | no |  |
| size_bytes | integer | no |  |
| line_count | integer | no |  |
| content | bytea | no |  |
| created_at | timestamp without time zone | no | default now() |
| expires_at | timestamp without time zone | no |  |
| id | uuid | no | primary key; default gen_random_uuid() |

Check `ck_batch_files_purpose`: `purpose IN ('batch', 'output')`

Check `ck_batch_files_size`: `size_bytes >= 0 AND size_bytes <= 16777216`

#### Table: batch_jobs

| Column | Type | Null | Notes |
|---|---|---|---|
| org_id | uuid | no | -> organizations.id (CASCADE) |
| user_id | uuid | no | -> users.id (CASCADE) |
| input_file_id | uuid | yes | -> batch_files.id (SET NULL) |
| output_file_id | uuid | yes | -> batch_files.id (SET NULL) |
| endpoint | varchar(40) | no |  |
| status | varchar(20) | no | default validating |
| total | integer | no |  |
| completed | integer | no | default 0 |
| failed | integer | no | default 0 |
| cost_usd | numeric(12, 6) | no | default 0 |
| max_cost_usd | numeric(12, 6) | no |  |
| error | text | yes |  |
| metadata | jsonb | no | default {} |
| created_at | timestamp without time zone | no | default now() |
| started_at | timestamp without time zone | yes |  |
| finished_at | timestamp without time zone | yes |  |
| id | uuid | no | primary key; default gen_random_uuid() |

Check `ck_batch_jobs_status`: `status IN ('validating', 'in_progress', 'completed', 'failed', 'cancelled', 'budget_exceeded')`

#### Table: batch_results

| Column | Type | Null | Notes |
|---|---|---|---|
| org_id | uuid | no | -> organizations.id (CASCADE) |
| job_id | uuid | no | -> batch_jobs.id (CASCADE) |
| idx | integer | no |  |
| custom_id | varchar(64) | no |  |
| status_code | integer | no |  |
| body | jsonb | yes |  |
| error | text | yes |  |
| id | uuid | no | primary key; default gen_random_uuid() |

### Identity and billing

#### Table: scim_tokens

| Column | Type | Null | Notes |
|---|---|---|---|
| org_id | uuid | no | -> organizations.id (CASCADE) |
| token_prefix | varchar(16) | no |  |
| token_hash | varchar(64) | no |  |
| created_by | uuid | yes | -> users.id (SET NULL) |
| created_at | timestamp without time zone | no | default now() |
| last_used_at | timestamp without time zone | yes |  |
| revoked_at | timestamp without time zone | yes |  |
| id | uuid | no | primary key; default gen_random_uuid() |

#### Table: stripe_events

| Column | Type | Null | Notes |
|---|---|---|---|
| event_id | varchar(255) | no |  |
| processed_at | timestamp with time zone | no | default now() |
| id | uuid | no | primary key; default gen_random_uuid() |

## Row-Level Security (RLS)

Multi-tenant isolation is enforced via PostgreSQL Row-Level Security on the following tables:

| Table | Policy |
|-------|--------|
| request_logs | `org_id = current_setting('app.current_org_id')::uuid` |
| api_keys | Same |
| llm_provider_keys | Same |
| webhook_deliveries | Same |
| semantic_cache_entries | Same |
| prompt_templates | Same |

**Application behavior:**
- At the start of each authenticated request, the app executes `SET LOCAL app.current_org_id = '{org_id}'` on the DB session.
- `SET LOCAL` is transaction-scoped — it resets automatically at commit/rollback.
- Org ID comes from JWT (`org_id` claim) or API key lookup (`get_api_key_by_hash` SECURITY DEFINER function).
- `FORCE ROW LEVEL SECURITY` ensures even the table owner is subject to policies.
- Superuser (migration role) bypasses RLS.

**Verification:** Run `python -m scripts.verify_rls` to generate CSV evidence for auditors.

Run `alembic history` to see current state:

```bash
alembic history
# 54c0ed90559e -> c4f9a12e8b7d
# c4f9a12e8b7d -> b3e8d87fd2f1
# ...
# e6f7a34b9d0c -> f8a9b0c1d2e3 (head)
```

To create a new migration after schema changes:

```bash
alembic revision --autogenerate -m "describe_change"
alembic upgrade head
```

## PostgreSQL Extensions

The schema requires two extensions:

```sql
CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS vector;      -- pgvector for semantic cache
```

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
