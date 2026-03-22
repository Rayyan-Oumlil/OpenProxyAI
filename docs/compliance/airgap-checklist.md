# Air-Gap Deployment Checklist — OpenProxyAI

Use this checklist when deploying OpenProxyAI in a **fully disconnected** environment (no outbound internet except to configured LLM providers).

---

## Prerequisites

- [ ] Customer-provided PostgreSQL 15+ and Redis 7+
- [ ] At least one LLM provider key (OpenAI, Anthropic, etc.) — you bring your own
- [ ] License key (min 16 chars) from OpenProxyAI

---

## Enabling Air-Gap Mode

| Variable | Value |
|----------|-------|
| `AIRGAP_MODE` | `true` |
| `LICENSE_KEY` | Your license key (required when `AIRGAP_MODE=true`) |

Startup fails with a clear error if `AIRGAP_MODE=true` and `LICENSE_KEY` is missing or too short.

---

## Disabled in Air-Gap

When `AIRGAP_MODE=true`, the following are **disabled**:

| Integration | Purpose |
|-------------|---------|
| Langfuse | Optional LLM tracing |
| ClickHouse dual-write | Log mirroring for OLAP |
| Spend reports | Weekly/monthly Slack/email digest |
| Stripe metered sync | Hourly usage reporting to Stripe |

**Still active:** Proxy requests to LLM providers, provider health check (pings your keys), webhook delivery to customer URLs, all core gateway features.

---

## Outbound Telemetry

**No phone-home:** OpenProxyAI does not call any OpenProxyAI-hosted analytics or telemetry endpoints.

**Allowed outbound (your choice):**
- LLM provider APIs (OpenAI, Anthropic, Azure, etc.) — required for proxy
- Webhook URLs you configure (Slack, PagerDuty, etc.) — optional
- OIDC/SSO provider (Auth0, Okta, etc.) — if you use SSO

---

## License Validation

- **Format:** `LICENSE_KEY` must be non-empty and at least 16 characters
- **Validation:** At startup; app exits with error if invalid
- **Offline:** No network call for validation; key is checked locally
- **Rotation:** Update `LICENSE_KEY` and restart

---

## Upgrade Path

1. Obtain new image/tarball from OpenProxyAI
2. Transfer to air-gapped environment (USB, air-gap transfer, etc.)
3. Run database migrations (Alembic)
4. Deploy new backend/frontend
5. Restart with existing `LICENSE_KEY` (or new key if rotated)

**No in-place auto-updates:** Upgrades are manual and under your control.

---

## Checklist Summary

- [ ] `AIRGAP_MODE=true` set
- [ ] `LICENSE_KEY` set (min 16 chars)
- [ ] PostgreSQL and Redis provisioned
- [ ] No Langfuse / ClickHouse / Stripe env vars (or leave blank)
- [ ] Firewall allows egress only to LLM providers you use
- [ ] Upgrade process documented for your ops team

---

## References

- [Customer-cluster install](../guides/customer-cluster-install.md) — installation steps, section 5 (air-gap)
- [Self-hosted security](./self-hosted-security.md) — encryption, RLS, key rotation
- [SOC 2 & HIPAA](./soc2-hipaa.md) — control mapping, deployment options
