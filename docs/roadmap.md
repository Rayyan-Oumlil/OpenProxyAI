# OpenProxyAI — Roadmap & Next Steps

> Last reviewed: 2026-03-17
> Current state: Phase 4 complete. 215 tests passing. Production-ready core.

---

## What is production-ready today

The foundation is solid and shippable to customers right now:

- **Proxy engine** — `/v1/chat/completions`, `/v1/embeddings`, streaming, LiteLLM multi-provider
- **Auth & RBAC** — API keys, roles (admin/developer/viewer), OIDC/SSO, invites
- **Rate limiting** — RPM, TPM, per-user daily budget, per-model overrides
- **Policy enforcement** — Enforcement modes, model allowlist, keyword blocking, PII detection (Presidio), prompt injection detection
- **Cost tracking** — Real-time Redis counters, anomaly detection, budget alert webhooks
- **Audit logging** — Immutable request logs, async fire-and-forget, plan-based retention
- **Admin console** — Dashboard, log viewer, policy editor, team management, provider key UI
- **SDKs** — Python (`openproxy-ai` on PyPI) and TypeScript (`openproxy-ai` on npm), streaming, typed errors
- **Kubernetes** — Production Helm chart with HPA, PDB, ServiceMonitor, init-container migrations

---

## Incomplete features (built but not finished)

These exist in the codebase but are not fully working:

### Response guardrails (code exists, logic missing)
- `response_guardrails_enabled` and `response_pii_redact` are toggleable in policy but the backend only checks request-side content. LLM responses are returned as-is.
- **Fix:** Implement `evaluate_response()` in `policy_service.py` to run keyword + PII checks on the response body before returning it to the client.

### ClickHouse dual-write (service exists, writes never happen)
- `clickhouse_service.py` is complete. `CLICKHOUSE_URL` env var is wired. But `audit_logger.py` never calls it.
- **Fix:** Add `asyncio.create_task(clickhouse_service.write_log(record))` in `log_request()`, gated on `clickhouse_service.is_enabled()`.

### Semantic / response cache (cache_service.py exists, nothing writes to it)
- `cache_service.py` has `get()` and `set()` with TTL. The proxy reads from it but never writes a cache hit.
- **Fix:** After a successful LLM response, serialize the response and call `cache_service.set(cache_key, response)`.

### Webhook retry job (table exists, no scheduler)
- `webhook_deliveries` table tracks attempts. The retry logic was documented as "Phase 3" but never scheduled.
- **Fix:** Add an APScheduler job (like the existing `mv_daily_spend` refresh) that retries `status='failed'` webhook deliveries with exponential backoff.

### Model fallback (LiteLLM Router initialized, fallback never invoked)
- `LLMService` initializes the LiteLLM Router but doesn't use fallback lists.
- Per ADR-9: only fall back on `429, 500, 502, 503, 504` — never on `4xx` client errors.
- **Fix:** Catch transient provider errors in `llm_service.py` and iterate to the next weighted provider key.

---

## Technical debt to fix before scaling

These will cause real problems at >10K requests/day:

### Rate limiter is O(N) per request
The sliding window adds all timestamps to a Redis sorted set and counts them on every request. At high throughput this becomes a bottleneck.
**Fix:** Switch to a fixed-window counter (`INCR` + `EXPIRE`) or token bucket pattern. The accuracy trade-off is acceptable.

### Policy config cache has no invalidation
When an admin updates policy, the old config stays cached in Redis for up to 60 seconds. For a "block immediately" use case this is a problem.
**Fix:** On `policy_store.save()`, delete the Redis key immediately so the next request reloads from the DB.

### No auth endpoint rate limiting
`POST /api/v1/auth/login` and `/auth/accept-invite` have no brute-force protection.
**Fix:** Add a Redis-backed IP + email counter with a 1-minute window. Return `429` after 10 attempts.

### Admin console session dies silently at 24h
JWTs expire with no refresh mechanism. Users get 401s with no warning.
**Fix:** Implement a refresh token endpoint (`POST /auth/refresh`) and add a silent refresh in the admin console before expiry.

### Admin actions not audited
Policy changes, provider key rotation, user deactivation, invite sends — none of these are logged.
**Fix:** Add a lightweight `admin_audit_log` table and write one row per admin action with actor, action, and before/after JSON.

---

## What competitors have that we don't

Derived from reading LiteLLM, Portkey, Helicone, Bifrost, and Envoy AI Gateway source code.

| Feature | Who has it | Priority for OpenProxyAI |
|---|---|---|
| Percentile latency analytics (p50/p95/p99) | Helicone | High — enterprise customers ask for this |
| Real-time dashboard (WebSocket) | Helicone | Medium — REST polling is OK for now |
| Semantic caching | LiteLLM, Portkey | High — reduces cost for repetitive workloads |
| Provider fallback chains | LiteLLM | High — critical for reliability SLAs |
| Model A/B testing (% traffic split) | Portkey | Medium — useful for prompt engineering |
| Request tagging (department/project/team) | Helicone | High — needed for departmental chargebacks |
| Budget forecasting | Helicone | Medium — customers want end-of-month projections |
| Compliance report export | None | High — SOC 2 auditors want one-click reports |
| ML-based prompt injection detection | None (all regex) | High — regex is easy to bypass |
| WASM plugin system | Bifrost, Envoy | Low — enterprise Phase 4 |
| Multi-region routing | Helicone, Bifrost | Low — Phase 4 for EU customers |

---

## Prioritized next steps

### P0 — Fix before first paying customer (Month 1)

1. **Finish response guardrails** — Customers who enable `response_guardrails_enabled` expect it to actually work. This is a broken promise.

2. **Fix rate limiter O(N) scaling** — Simple swap from sorted-set sliding window to fixed-window counter. Blocks scaling.

3. **Add auth endpoint rate limiting** — A paying enterprise will ask "can someone brute-force our API?" before signing. Answer must be no.

4. **Policy cache invalidation on save** — Admins expect policy changes to take effect immediately.

5. **Complete ClickHouse dual-write** — The service is written. The wiring is a 5-line change. Turn it on.

---

### P1 — Ship before reaching $50K ARR (Month 2–3)

6. **Request tagging (metadata labels)** — Let users attach `{"team": "marketing", "project": "chatbot-v2"}` to requests. This unlocks per-team analytics and chargebacks — the #1 enterprise ask.

7. **Provider fallback chains** — Reliability SLA is impossible to promise without automatic failover. Implement ADR-9 (selective fallback on 429/5xx only).

8. **Webhook retry job** — Compliance customers need guaranteed delivery. One attempt is not enough.

9. **Admin action audit log** — Needed for SOC 2 CC6 (logical access changes must be logged). Already mapped in `docs/compliance/soc2-hipaa.md`.

10. **Response cache write** — `cache_service.py` is ready. Complete the write path. Start with exact-match caching — semantic caching can come later.

11. **p95/p99 latency in analytics** — Every enterprise status page shows latency percentiles. PostgreSQL `percentile_cont()` makes this a 2-line query change.

---

### P2 — Ship before reaching $200K ARR (Month 3–4)

12. **ML-based prompt injection detection** — Replace regex with a small classification model (e.g. `protectai/deberta-v3-base-prompt-injection` on HuggingFace). Regex is trivially bypassed in production.

13. **Budget forecasting** — Project end-of-month spend based on current daily average. One query + one dashboard card. High customer perceived value, low effort.

14. **Admin console session refresh** — Implement refresh token. Customers hate being logged out mid-work.

15. **Compliance report export** — Generate a PDF/CSV of: policy violations by period, user access list, key rotation log, budget vs actual. Directly maps to SOC 2 CC7 evidence.

16. **Presidio in Helm chart** — Add `presidio-analyzer` as an optional sidecar deployment so PII detection works out-of-the-box on Kubernetes without manual setup.

---

### P3 — Ship before reaching $500K ARR (Month 4–6)

17. **Voice: `/v1/audio/transcriptions` endpoint** — Wrap Whisper API (or self-hosted) with the same auth/policy/audit pipeline as chat completions. Phase 1 of the voice roadmap documented in `docs/guides/voice-integration.md`.

18. **Semantic caching** — Embed requests with a small model, cosine-match against cached responses within a configurable similarity threshold. Reduces cost 20–40% for repetitive workloads.

19. **Model A/B testing** — Route X% of traffic to model A, Y% to model B. Aggregate latency/cost/quality metrics per variant. Portkey has this; enterprise prompt engineers will ask for it.

20. **Multi-region deployment** — EU customers (GDPR data residency) need `data_region=eu` to route to an EU-hosted instance. The `data_region` column already exists on `organizations`. Wire up the routing.

21. **WASM plugin system** — Let enterprise customers write custom policy hooks in any language that compiles to WASM. This is a moat feature — no competitor has it as a hosted SaaS offering.

---

## Fastest path to first revenue

If the goal is a paying customer in the next 60 days, the minimum credible product is:

1. Fix the P0 items above (1–5)
2. Deploy to a public URL (Helm on any managed Kubernetes — EKS, GKE, or DigitalOcean)
3. Create a Stripe billing integration for the Starter plan ($2,500/mo)
4. Target one regulated-industry company (a fintech or healthcare startup) where compliance is a pain point they already feel

The proxy, auth, rate limiting, policy, audit trail, and Kubernetes chart are all production-grade. The product is ready to charge for — the remaining gaps are features, not showstoppers.
