# Self-Hosted Security — OpenProxyAI

Security controls and deployment considerations when running OpenProxyAI on **your own infrastructure** (customer cluster or air-gapped environment). See [customer-cluster-install.md](../guides/customer-cluster-install.md) for installation and [airgap-checklist.md](./airgap-checklist.md) for air-gap specifics.

---

## Encryption at Rest

| Asset | Control |
|-------|---------|
| Provider API keys | Fernet (AES-128-CBC + HMAC-SHA256) derived from `SECRET_KEY` via PBKDF2 |
| SSO client secrets | Same Fernet encryption as provider keys |
| Gateway API keys | SHA-256 hashed; plaintext never stored |
| PostgreSQL | Use encrypted storage (LUKS, cloud provider disk encryption) at the infrastructure layer |
| Redis | Redis 7+ supports TLS; use for sensitive state; consider Redis AOF with encryption |

**Your responsibility:** Ensure PostgreSQL and Redis volumes are encrypted. OpenProxyAI encrypts application-level secrets; underlying DB/Redis encryption is your infrastructure choice.

---

## Key Rotation

| Item | How |
|------|-----|
| Provider keys | `POST /api/v1/provider-keys/{id}/rotate` — re-encrypts without changing plaintext |
| Gateway API keys | Create new key, update clients, revoke old |
| SECRET_KEY | Maintenance window required; re-encrypt all provider keys; see [security.md](./security.md#secret-rotation) |
| LICENSE_KEY (air-gap) | Swap key; restart with new value |

**Schedule:** Rotate provider keys every 90 days; SECRET_KEY annually or per compliance policy.

---

## Audit Log Immutability

- **PostgreSQL RLS:** `request_logs` enforces org isolation; admins cannot bypass
- **Soft archival:** Hourly job sets `archived_at` for logs older than plan retention
- **No in-place edits:** Logs are append-only; no `UPDATE` or `DELETE` on active rows
- **Export for cold storage:** Archived logs can be copied to S3 Glacier, tape, etc. for long-term retention

**Evidence:** Run `verify_rls.py` to generate CSV evidence for auditors (see [soc2-hipaa.md](./soc2-hipaa.md)).

---

## Client IP and Trusted Proxy (X-Forwarded-For)

When deployed behind a reverse proxy (nginx, Cloud Run, etc.), the application receives `X-Forwarded-For` with the real client IP. **By default, `X-Forwarded-For` is not trusted** to prevent IP spoofing (H03). Set `TRUSTED_PROXY=true` only when:

- The app receives traffic **solely** from a reverse proxy that overwrites/strips `X-Forwarded-For`
- The proxy is not reachable directly by untrusted clients

Configure your proxy to overwrite `X-Forwarded-For` with the real client IP (e.g. nginx: `proxy_set_header X-Forwarded-For $remote_addr`). Never trust `X-Forwarded-For` from the public internet without a trusted proxy in front.

---

## Row-Level Security (RLS)

OpenProxyAI uses PostgreSQL RLS on:

- `request_logs`
- `api_keys`
- `llm_provider_keys`
- `webhook_deliveries`
- `semantic_cache_entries`
- `prompt_templates`

Each request sets `app.current_org_id` via `SET LOCAL`; policies restrict access to that org. Database superusers cannot read cross-org data without disabling policies (audit trail).

---

## Network Isolation

| Layer | Recommendation |
|-------|----------------|
| Ingress | TLS 1.2+; restrict to known IPs if possible |
| Backend ↔ PostgreSQL | Private subnet; no public exposure |
| Backend ↔ Redis | Private subnet; Redis AUTH enabled |
| Backend → LLM providers | Egress allowed to OpenAI, Anthropic, etc.; no other outbound required for core proxy |
| Air-gap | `AIRGAP_MODE=true` disables Langfuse, ClickHouse, spend reports, Stripe metered sync |

**Firewall:** Allow outbound only to configured LLM provider endpoints when in air-gap mode.

---

## Compliance Mapping

| Framework | Self-hosted mapping |
|-----------|---------------------|
| SOC 2 CC6.8 | Encryption at rest — provider keys encrypted; DB/Redis encryption your responsibility |
| SOC 2 CC9.2 | Key rotation — use `/rotate` endpoint; scheduled rotation available |
| HIPAA §164.312(a)(1) | Access control — RBAC, RLS, invite-only provisioning |
| HIPAA §164.312(b) | Audit controls — immutable logs, retention per plan |
| FedRAMP | US-only provider keys via `region` field; `data_region` on orgs |

See [soc2-hipaa.md](./soc2-hipaa.md) for full control mapping.

---

## Next Steps

- [Air-gap checklist](./airgap-checklist.md) — license validation, no outbound telemetry
- [Customer-cluster install](../guides/customer-cluster-install.md) — Helm values, PostgreSQL/Redis
- [Security architecture](./security.md) — full security reference
