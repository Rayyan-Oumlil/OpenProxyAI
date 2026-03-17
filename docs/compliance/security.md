# Security Architecture — OpenProxyAI

Complete guide to security controls implemented in OpenProxyAI, covering authentication, encryption, audit logging, and compliance.

---

## API Key Management

### Key Format

All API keys are prefixed with `opai_` followed by 32 random alphanumeric characters:

```
opai_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p
```

### Key Storage

API keys are never stored in plaintext. The backend stores:

1. **Key prefix** — First 8 characters (for display in logs/UI)
2. **Key hash** — SHA-256 hash of the full plaintext key

The plaintext key is shown only once during creation and never persists to disk.

### Authentication

All API requests require the key in the `Authorization` header:

```bash
Authorization: Bearer opai_xxxxxxxxxxxxxx
```

The gateway validates the key hash against the database on every request. Invalid keys return HTTP 401.

---

## Provider Key Encryption

### Encryption Method

LLM provider keys (OpenAI, Anthropic, Azure, etc.) stored in the database are encrypted using **Fernet (AES-128-CBC + HMAC-SHA256)** from Python's `cryptography` library.

### Key Derivation

The encryption key is derived deterministically from `SECRET_KEY` via **PBKDF2-SHA256** with 100,000 iterations:

```python
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

kdf = PBKDF2HMAC(
    algorithm=hashes.SHA256(),
    length=32,
    salt=b"openproxyai-llm-provider-keys-v1",
    iterations=100_000,
)
encryption_key = kdf.derive(SECRET_KEY.encode())
```

This allows provider keys to be decrypted across service restarts as long as `SECRET_KEY` remains stable.

### Environment Variable

Set `SECRET_KEY` at deployment time:

```bash
export SECRET_KEY="your-stable-secret-key"
```

Changing `SECRET_KEY` invalidates all existing encrypted provider keys.

### Provider Key Rotation

Rotate a provider key without changing the plaintext (for compliance):

```bash
POST /api/v1/provider-keys/{id}/rotate
```

Response:

```json
{
  "rotated": true,
  "key_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**What happens:**

1. Decrypt the stored ciphertext using the current `SECRET_KEY`
2. Re-encrypt the plaintext with a fresh Fernet IV
3. Store the new ciphertext

The plaintext API key is unchanged — only the ciphertext is replaced. This satisfies SOC 2 CC9.2 vendor risk management (key rotation) without requiring changes to upstream LLM providers.

---

## TLS and HTTP Security Headers

### SecurityHeadersMiddleware

Every response includes security headers to prevent common web vulnerabilities:

```
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Strict-Transport-Security: max-age=31536000; includeSubDomains
Content-Security-Policy: default-src 'none'; frame-ancestors 'none'
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: geolocation=(), microphone=(), camera=()
```

**Explanation:**

| Header | Value | Purpose |
|--------|-------|---------|
| `X-Content-Type-Options` | `nosniff` | Prevent MIME-type sniffing attacks |
| `X-Frame-Options` | `DENY` | Block clickjacking (prevent embedding in iframes) |
| `X-XSS-Protection` | `1; mode=block` | Enable XSS filtering in older browsers |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` | Force HTTPS for 1 year; include subdomains |
| `Content-Security-Policy` | `default-src 'none'; frame-ancestors 'none'` | Restrict resource loading; prevent framing |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Send referrer only to same-origin requests |
| `Permissions-Policy` | `geolocation=(), microphone=(), camera=()` | Disable potentially dangerous features |

### TLS Configuration

All connections to the gateway must use HTTPS with TLS 1.2+. Deployment guides (Kubernetes, Docker Compose) include TLS certificate configuration.

---

## Audit Log Immutability

Request logs are immutable and protected by PostgreSQL Row-Level Security (RLS) plus hourly archival:

### Database RLS

Each organization can only view its own logs:

```sql
CREATE POLICY org_isolation ON request_logs
  FOR SELECT
  USING (org_id = current_user_org_id);
```

Even database administrators cannot bypass RLS — only the table owner can disable it.

### Hourly Archival

A scheduled cron job runs every hour and marks old logs as archived:

```python
# From app.main.archive_old_logs()
async def archive_old_logs():
    for org in organizations:
        retention_days = org.plan_features['audit_retention_days']
        cutoff = now() - timedelta(days=retention_days)

        await db.execute(
            UPDATE request_logs
            SET archived_at = now()
            WHERE org_id = org.id
            AND created_at < cutoff
            AND archived_at IS NULL
        )
```

Once a log is archived (marked with `archived_at` timestamp), it is treated as immutable. Archived logs can be exported to a cold storage system (e.g., AWS S3 Glacier) for long-term retention.

### Retention Policies

Different plans have different retention periods:

| Plan | Retention Days |
|------|----------------|
| Free | 7 days |
| Starter | 30 days |
| Growth | 90 days |
| Enterprise | 365 days |

---

## Rate Limiting

Rate limits are enforced in Redis to prevent abuse. Each organization has separate buckets:

### Limit Types

1. **Requests per minute (RPM):** Limit on API calls
2. **Tokens per minute (TPM):** Limit on token consumption
3. **Daily budget (USD):** Limit on spend per calendar day

### Rate Limit Response

When a limit is exceeded, the gateway returns HTTP 429:

```json
{
  "error": "rate_limit_exceeded",
  "detail": "Requests per minute limit exceeded (100 req/min)",
  "limit_type": "requests_per_minute",
  "retry_after": 5
}
```

For daily budget limits, the response includes:

```json
{
  "error": "budget_exceeded",
  "detail": "Daily budget exhausted ($100.00)",
  "limit_type": "daily_budget_usd",
  "retry_after": 86400
}
```

### Headers

Every response includes rate limit information:

```
X-RateLimit-Limit-Rpm: 100
X-RateLimit-Remaining-Rpm: 47
X-RateLimit-Reset: 1710590000
X-OpenProxyAI-Budget-Remaining-Usd: 45.32
```

---

## PII Detection

Personally identifiable information (PII) is detected in-flight using **Microsoft Presidio**. No data is stored; detection happens on request/response content only.

### Detectable Patterns

Presidio can detect:

- Email addresses
- Phone numbers
- Credit card numbers
- Social Security numbers (SSNs)
- Bank account numbers
- Passport numbers
- Driver license numbers

### Configuration

Enable PII detection in the organization policy:

```bash
PATCH /api/v1/organizations/current/policy
```

```json
{
  "pii_detection_enabled": true,
  "pii_patterns": ["email", "ssn", "credit_card"]
}
```

### Behavior

- **Log only mode:** PII is logged but the request is allowed
- **Block mode:** Requests containing PII are rejected with HTTP 403

```json
{
  "error": "policy_violation",
  "code": "pii_detected",
  "detail": "Request blocked: PII detected (email, credit_card)",
  "policy_action": "block"
}
```

---

## OIDC/SSO Authentication

Organizations can connect to an OIDC provider (Auth0, Okta, Azure AD, etc.) for single sign-on.

### Client Secret Encryption

The OIDC provider's client secret is encrypted at rest using the same Fernet key as provider API keys:

```python
sso_connection.client_secret_encrypted = encrypt(client_secret)
await db.commit()
```

Decryption happens only when the secret is needed for token exchange — never logged or exposed.

### JIT Provisioning

When a user logs in via OIDC for the first time, they are automatically provisioned:

1. An account is created in OpenProxyAI
2. They are assigned to the organization
3. A default role is set (usually `viewer`)

Admins can then grant additional permissions in the admin console.

---

## Data Residency

Organizations can specify where their data is stored:

```json
{
  "data_region": "us-east-1"
}
```

This controls:

- Database region (if using managed databases)
- S3 region for archived logs
- Redis region for caching

---

## Error Messages

Error messages never leak sensitive information:

- Database credentials are never revealed
- Stack traces are never exposed to clients
- Request contents are not echoed back to unauthorized parties

Example error response:

```json
{
  "error": "internal_server_error",
  "detail": "An unexpected error occurred"
}
```

Detailed error information is logged on the server side only (with proper access controls).

---

## Compliance Frameworks

### SOC 2 Type II

Controls implemented:

- **CC9.2 Vendor Risk Management:** Provider key rotation without exposure
- **CC6.1 Logical Access Control:** RBAC, OIDC/SSO, API key authentication
- **CC7.2 System Monitoring:** Immutable audit logs with 1-hour archival window
- **CC9.1 Potential for Misuse:** Rate limiting prevents brute force / DOS

### HIPAA

Controls for healthcare organizations:

- **Encryption at rest:** Fernet AES-128-CBC for provider keys
- **Encryption in transit:** TLS 1.2+ for all connections
- **Audit logging:** Immutable logs with retention per data protection rules
- **Access controls:** RBAC + OIDC/SSO
- **Data residency:** Support for US-East deployments

### GDPR

Controls for EU organizations:

- **Data processing agreements (DPA):** Available upon request
- **Data residency:** EU-West region support
- **Right to erasure:** Audit logs can be anonymized
- **Breach notification:** 72-hour SLA for incident response

---

## Secret Rotation

### Best Practices

1. **Rotate API keys:** Create new keys, update applications, delete old keys
2. **Rotate provider keys:** Use the `/rotate` endpoint every 90 days
3. **Rotate SECRET_KEY:** Plan a maintenance window, re-encrypt all provider keys
4. **Rotate OAuth secrets:** Rotate OIDC client secrets every 6 months

### Zero-Downtime Rotation

Provider key rotation uses fresh Fernet IVs without blocking requests:

```bash
POST /api/v1/provider-keys/{id}/rotate
```

No downtime; no client changes required.

---

## Security Checklist

Before deploying to production:

- [ ] `SECRET_KEY` is strong (32+ random characters)
- [ ] `SECRET_KEY` is stored in a secrets manager (AWS Secrets Manager, Vault, etc.)
- [ ] HTTPS/TLS is enabled
- [ ] Database credentials are encrypted at rest
- [ ] Redis is accessible only from the application
- [ ] Audit logs are backed up daily
- [ ] OIDC is configured for admin access
- [ ] Rate limits are tuned for your expected traffic
- [ ] PII detection is enabled and tested
- [ ] Error messages don't leak information

---

## Incident Response

### Security Contact

Report security vulnerabilities to `security@openproxyai.com`.

### Response SLA

- Critical (exploitable RCE, auth bypass): 4 hours
- High (data exposure, privilege escalation): 24 hours
- Medium (information disclosure): 72 hours
- Low (hardening recommendations): 30 days

### Breach Notification

In the event of a data breach:

1. Affected organizations are notified within 24 hours
2. Details of exposed data are provided
3. Recommended remediation steps are shared
4. Audit logs are preserved for forensics

---

## Next Steps

- **Deployment** — See [deployment.md](../architecture/deployment.md) for infrastructure setup
- **Policy Configuration** — See [policy-configuration.md](./policy-configuration.md) for guardrails
- **API Reference** — See [api-reference.md](../api-reference.md) for security-related endpoints
