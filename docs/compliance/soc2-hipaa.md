# SOC 2 & HIPAA Technical Controls — OpenProxyAI

## SOC 2 Trust Service Criteria

### CC6 — Logical and Physical Access Controls
| Control | Implementation |
|---------|---------------|
| CC6.1 — Unique user identification | `users` table, bcrypt passwords, JWT tokens with per-user claim |
| CC6.2 — Authentication credentials | bcrypt + pepper via SECRET_KEY; access tokens 24h TTL |
| CC6.3 — Role-based access control | `role` field: admin / developer / viewer; `require_admin` dependency |
| CC6.6 — Logical access restrictions | API keys scoped to org; RLS on request_logs (no UPDATE/DELETE) |
| CC6.7 — Encryption of data in transit | TLS enforced via HSTS header; internal traffic via cluster network |
| CC6.8 — Encryption of data at rest | Provider keys: AES-GCM via crypto_service; SSO client_secret: AES-GCM |

### CC7 — System Operations
| Control | Implementation |
|---------|---------------|
| CC7.2 — Monitoring for anomalies | Prometheus metrics + Langfuse traces; cost anomaly webhook |
| CC7.3 — Incident detection | Webhook delivery for policy violations; budget threshold alerts |

### CC8 — Change Management
| Control | Implementation |
|---------|---------------|
| CC8.1 — Authorized changes | Alembic migrations with revision chain; all schema changes versioned |

### CC9 — Risk Mitigation
| Control | Implementation |
|---------|---------------|
| CC9.1 — Risk identification | Per-org policy config; model allowlist; PII detection (regex-based; Presidio NLP disabled by default) |
| CC9.2 — Vendor risk management | Provider key rotation endpoint (`POST /provider-keys/{id}/rotate`) |

## HIPAA Technical Safeguards (§164.312)

| Safeguard | Standard | Implementation |
|-----------|----------|---------------|
| Access Control | §164.312(a)(1) | Role-based access; unique user IDs; per-org isolation |
| Audit Controls | §164.312(b) | Immutable `request_logs` (RLS); `archived_at` retention; all events logged |
| Integrity | §164.312(c)(1) | AES-GCM authenticated encryption; HMAC-SHA256 webhook signing |
| Transmission Security | §164.312(e)(1) | HSTS + CSP headers; TLS required in production |
| Person Authentication | §164.312(d) | Unique credentials per user; JWT + API key auth; invite-only provisioning |

## Data Residency

The `data_region` field on `organizations` (values: `us`, `eu`, `ap`) is intended for
operators to route traffic to region-specific deployments. Enforcement is at the
infrastructure layer (ingress routing rules, separate clusters per region).

## Audit Log Retention

| Plan | Retention |
|------|-----------|
| Free | 7 days |
| Starter | 30 days |
| Growth | 90 days |
| Enterprise | 365 days |

Logs older than the retention window are soft-archived (`archived_at` set).
Hard deletion requires a manual operator action (`DELETE FROM request_logs WHERE archived_at < ...`).
