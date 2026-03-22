# OpenProxyAI Security Review Report

**Review Date:** March 21, 2025  
**Scope:** Authentication, sensitive data handling, OWASP Top 10, audit immutability, self-hosted deployments  
**Reviewer:** Security Reviewer Agent

---

## Executive Summary

OpenProxyAI demonstrates strong security practices for an enterprise LLM proxy: API keys are SHA-256 hashed, provider keys encrypted at rest (Fernet), passwords hashed with bcrypt, JWTs validated with blocklisting, Stripe webhooks verified, and webhook delivery protected against SSRF. Several findings require remediation, primarily around default configuration, IP handling consistency, and token storage hardening for air-gap deployments.

---

## Findings

### CRITICAL

#### 1. Default SECRET_KEY in Development Config

| Field | Value |
|-------|-------|
| **File** | `backend/app/config.py:22` |
| **Risk** | OWASP A02:2021 – Cryptographic Failures |
| **Line** | `SECRET_KEY: str = "dev-secret-key-change-in-production"` |

**Description:** A default secret key is hardcoded. If deployed without overriding, all JWT signatures, refresh token validation, provider key decryption (via PBKDF2 derivation), and SSO client secret decryption become vulnerable.

**Remediation:** The app already raises `RuntimeError` when `APP_ENV != "development"` and SECRET_KEY is default (`main.py:184-188`). Recommend also:
- Fail startup if `SECRET_KEY` is fewer than 32 characters in any environment
- Document in deployment guides that `SECRET_KEY` must be a cryptographically random 256-bit value

---

#### 2. Stripe Webhook Unauthenticated (by design) — Signature Verification Required

| Field | Value |
|-------|-------|
| **File** | `backend/app/routes/billing.py:79-90` |
| **Risk** | OWASP A07:2021 – Identification and Authentication Failures |
| **Line** | `@router.post("/webhook")` |

**Description:** The Stripe webhook endpoint is unauthenticated (no JWT). It relies solely on `stripe.Webhook.construct_event()` for signature verification. If `STRIPE_WEBHOOK_SECRET` is empty or misconfigured, `billing_service.handle_webhook` raises; if an attacker obtains a valid webhook secret, they could forge events.

**Status:** Correctly implemented. `STRIPE_WEBHOOK_SECRET` is required when Stripe is configured (`billing_service.py:288-293`). Rate limiting by IP is applied (`_check_webhook_rate_limit`).

**Recommendation:** Document that `STRIPE_WEBHOOK_SECRET` must be kept secret and different per environment. Add integration test that invalid signature returns 400.

---

### HIGH

#### 3. Admin Audit IP Logging Ignores TRUSTED_PROXY

| Field | Value |
|-------|-------|
| **File** | `backend/app/services/admin_audit_service.py:94-98` |
| **Risk** | OWASP A09:2021 – Security Logging and Monitoring Failures |
| **Line** | `def get_ip(request)` |

**Description:** `get_ip()` always uses `X-Forwarded-For` without checking `TRUSTED_PROXY`. `dependencies.get_real_ip()` correctly gates on `TRUSTED_PROXY`. Admin audit logs (provider keys, org changes, etc.) may record spoofed IPs when `TRUSTED_PROXY=False`, undermining forensic value.

**Remediation:** Applied. `get_ip()` now gates `X-Forwarded-For` on `TRUSTED_PROXY`, matching `dependencies.get_real_ip()`.

---

#### 4. JWT/Refresh Tokens Stored in localStorage (XSS Exposure)

| Field | Value |
|-------|-------|
| **File** | `admin-console/src/state/AuthContext.tsx:16-17, 70-71, 166-167` |
| **Risk** | OWASP A03:2021 – Injection (XSS), A07:2021 – Identification and Authentication Failures |
| **Line** | `localStorage.setItem(ACCESS_KEY, ...)` |

**Description:** Access and refresh tokens are stored in `localStorage`. Any XSS in the admin console (or a compromised dependency) can exfiltrate tokens. Refresh tokens have long expiry (14 days) and full session power.

**Remediation:**
- Prefer `httpOnly` cookies for tokens when the API supports it (requires backend cookie support and CSRF protection)
- If localStorage must be used: shorten refresh token expiry, implement strict CSP, and avoid rendering unsanitized user content
- For air-gap deployments: document that customers should deploy the admin console on an isolated domain and lock down CSP

---

#### 5. SSO Exchange-Code Endpoint Unauthenticated (by design)

| Field | Value |
|-------|-------|
| **File** | `backend/app/routes/sso.py:158-170` |
| **Risk** | OWASP A07:2021 – Identification and Authentication Failures |
| **Line** | `@router.post("/api/v1/auth/sso/exchange-code")` |

**Description:** The endpoint exchanges a one-time code for access/refresh tokens. No auth required by design (the code is the credential). If the code leaks (URL bar, referrer, logs), an attacker can steal the session. Code TTL is 90 seconds and single-use.

**Status:** Acceptable for standard OIDC flows. Ensure:
- Frontend navigates with `replace` to avoid code persisting in history
- No logging of the `code` query parameter
- SSOCallbackPage uses `navigate(..., { replace: true })` — verified

**Recommendation:** Add rate limiting per IP on `exchange-code` to prevent brute-force of codes (32-byte entropy makes this theoretical).

---

### MEDIUM

#### 6. CORS allow_credentials=True with Configurable Origins

| Field | Value |
|-------|-------|
| **File** | `backend/app/middleware/cors.py:26-32` |
| **Risk** | OWASP A05:2021 – Security Misconfiguration |
| **Line** | `allow_credentials=True` |

**Description:** `allow_credentials=True` means browsers send cookies/Authorization with cross-origin requests. If `CORS_ORIGINS` is misconfigured (e.g. `*` or overly broad), a malicious site could make authenticated requests.

**Status:** Pydantic Settings loads `CORS_ORIGINS` from env; default lists specific localhost origins. No wildcard in default.

**Remediation:** Add startup validation that `CORS_ORIGINS` does not contain `*` when `allow_credentials=True`. Document in deployment that origins must be explicit.

---

#### 7. EVAL_HOOK_URL — SSRF via Configuration

| Field | Value |
|-------|-------|
| **File** | `backend/app/services/eval_service.py:64-67` |
| **Risk** | OWASP A10:2021 – Server-Side Request Forgery (SSRF) |
| **Line** | `url = settings.EVAL_HOOK_URL.strip()` |

**Description:** `EVAL_HOOK_URL` is an environment variable. If an attacker controls deployment config (e.g. injected env), they could point it to internal services (metadata, VPC). The URL is not user-controlled.

**Status:** Low risk under normal threat model. Document for air-gap deployments: restrict which URLs can be configured and use a denylist for internal IP ranges if hook URL is user-configurable in future.

---

#### 8. Provider Key Update Allows All Schema Fields

| Field | Value |
|-------|-------|
| **File** | `backend/app/routes/provider_keys.py:119-121` |
| **Risk** | OWASP A01:2021 – Broken Access Control |
| **Line** | `updates = payload.model_dump(exclude_unset=True)` |

**Description:** The update applies `model_dump(exclude_unset=True)` directly to the model. `ProviderKeyUpdateRequest` correctly omits `api_key` and `api_key_encrypted`, so encrypted keys cannot be overwritten via this route. Verified schema allows only `key_alias`, `weight`, `is_active`, `region`.

**Status:** No vulnerability. Re-verify if schema is extended to include sensitive fields.

---

#### 9. Accept-Invite Rate Limit Uses Token as Key

| Field | Value |
|-------|-------|
| **File** | `backend/app/routes/auth.py:147-148` |
| **Risk** | OWASP A07:2021 – Identification and Authentication Failures |
| **Line** | `_check_auth_rate_limit(get_real_ip(request), payload.token, redis)` |

**Description:** Rate limit key is `auth:attempts:{ip}:{token}`. The token is the invite token, not email. This is correct—limits attempts per IP per token, preventing brute-force of 256-bit invite tokens.

**Status:** Acceptable.

---

### LOW

#### 10. Fixed Salt in Crypto Service

| Field | Value |
|-------|-------|
| **File** | `backend/app/services/crypto_service.py:24` |
| **Risk** | OWASP A02:2021 – Cryptographic Failures |
| **Line** | `_SALT = b"openproxyai-llm-provider-keys-v1"` |

**Description:** Fixed salt is used for PBKDF2 key derivation. Security relies on `SECRET_KEY`. If `SECRET_KEY` is compromised, all encrypted provider keys and SSO client secrets are at risk regardless of salt.

**Status:** Acceptable for deterministic derivation. Document that `SECRET_KEY` compromise requires key rotation and re-encryption of all stored secrets.

---

#### 11. Database URL in Config

| Field | Value |
|-------|-------|
| **File** | `backend/app/config.py:29-31` |
| **Risk** | Sensitive data exposure |
| **Line** | `DATABASE_URL: str = "postgresql+asyncpg://openproxyai:openproxyai_dev@postgres:5432/openproxyai"` |

**Description:** Default contains credentials. Override via env in production. No logging of `DATABASE_URL` observed.

**Recommendation:** Ensure `.env` and any config dumps exclude `DATABASE_URL`, `SECRET_KEY`, `STRIPE_*`, etc.

---

#### 12. No Explicit Security Headers

| Field | Value |
|-------|-------|
| **File** | `backend/app/main.py` |
| **Risk** | OWASP A05:2021 – Security Misconfiguration |

**Description:** No `X-Content-Type-Options`, `X-Frame-Options`, `Strict-Transport-Security`, or `Content-Security-Policy` set at the application level. May be provided by reverse proxy.

**Remediation:** Add middleware or reverse proxy config:
```python
# Example headers
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Strict-Transport-Security: max-age=31536000; includeSubDomains
```

---

## Positive Security Controls Verified

| Control | Location | Notes |
|---------|----------|-------|
| API key hashing | `utils/crypto.py` | SHA-256 + constant-time compare |
| Password hashing | `utils/crypto.py` | bcrypt via passlib |
| Provider key encryption | `services/crypto_service.py` | Fernet (AES-128-CBC + HMAC-SHA256), PBKDF2 100k iterations |
| JWT algorithm | `auth_service.py` | HS256 only, no algorithm confusion |
| JWT blocklisting | `auth_service.py` | Redis blocklist by jti, logout/refresh invalidates |
| Refresh token rotation | `auth_service.py` | New refresh token on refresh, old blocklisted |
| Stripe webhook verification | `billing_service.py` | Signature verified before processing |
| Webhook SSRF protection | `webhook_service.py` | HTTPS only, private/CGN IPs rejected, hostname resolved |
| Invite token | `invite_service.py` | SHA-256 hashed, constant-time compare |
| SQL injection | `auth_service.py`, `analytics_service.py` | Parameterized queries, `text()` with bound params |
| Audit log immutability | `f1a9c3e7d5b2` migration | RLS allows INSERT and SELECT only, no UPDATE/DELETE for app_user |
| Org isolation | RLS policies | `app.current_org_id` used for multi-tenant isolation |
| Rate limiting | `auth.py`, `billing.py` | Login, register, accept-invite, Stripe webhook |
| Admin audit serialization | `admin_audit_service.py` | `serialize_provider_key` excludes raw key; `serialize_webhook_config` excludes secret |

---

## OWASP Top 10 Mapping

| OWASP 2021 | Finding | Status |
|------------|---------|--------|
| A01 Broken Access Control | Provider key, API key, org scoping | ✅ Enforced via RLS and route checks |
| A02 Cryptographic Failures | Default SECRET_KEY, fixed salt | ⚠️ See findings 1, 10 |
| A03 Injection | SQL, NoSQL, XSS | ✅ Parameterized SQL; no dangerous React patterns found |
| A04 Insecure Design | Token storage, SSO flow | ⚠️ See findings 4, 5 |
| A05 Security Misconfiguration | CORS, headers, TRUSTED_PROXY | ⚠️ See findings 3, 6, 12 |
| A06 Vulnerable Components | Not assessed | Run `npm audit`, `pip audit` |
| A07 Auth Failures | JWT, Stripe webhook, SSO exchange | ⚠️ See findings 2, 4, 5 |
| A08 Software/Data Integrity | Stripe signature, JWT blocklist | ✅ Verified |
| A09 Logging Failures | Admin audit IP spoofing | ⚠️ See finding 3 |
| A10 SSRF | Webhook, EVAL_HOOK_URL | ✅ Webhook protected; EVAL_HOOK env-only |

---

## Self-Hosted / Air-Gap Considerations

1. **Key rotation:** `KEY_ROTATION_SCHEDULER_ENABLED` and `key_rotation_scheduler.py` rotate Fernet ciphertext only (zero-downtime). Provider API keys are unchanged; only the encryption envelope is rotated. Document rotation cadence for SOC 2.

2. **Encryption at rest:** Provider keys and SSO client secrets use Fernet. Ensure `SECRET_KEY` is in a secrets manager and DB is encrypted at rest (e.g. Cloud SQL, RDS).

3. **Network isolation:** Webhook delivery blocks private/CGN IPs. EVAL_HOOK_URL and Langfuse are disabled in `AIRGAP_MODE`. Document that customers must restrict outbound connectivity in air-gap.

4. **LICENSE_KEY:** Required when `AIRGAP_MODE=true`. Validated at startup (min 16 chars). Ensure license validation cannot be bypassed.

---

## Recommendations Summary

| Priority | Action |
|----------|--------|
| Critical | Ensure SECRET_KEY is never default in production (already enforced; add length check) |
| High | Align `admin_audit_service.get_ip()` with `TRUSTED_PROXY` |
| High | Consider httpOnly cookies for tokens or shorten refresh TTL; strengthen CSP |
| Medium | Validate CORS_ORIGINS does not contain `*` when credentials allowed |
| Medium | Add security headers (HSTS, X-Frame-Options, etc.) |
| Low | Document SECRET_KEY and crypto key rotation for self-hosted |
| Low | Run `pip audit` and `npm audit` regularly |

---

## Appendix: Files Reviewed

- `backend/app/routes/`: auth.py, api_keys.py, provider_keys.py, billing.py, sso.py
- `backend/app/services/`: auth_service.py, llm_service.py, policy_service.py, audit_logger.py, crypto_service.py, sso_service.py, billing_service.py, webhook_service.py, invite_service.py, admin_audit_service.py, eval_service.py
- `backend/app/models/`: api_key.py, user.py, llm_provider_key.py, request_log.py
- `backend/app/dependencies.py`, `middleware/cors.py`, `middleware/request_id.py`
- `backend/app/utils/crypto.py`, `config.py`
- `admin-console/src/`: AuthContext.tsx, api/client.ts, LoginPage.tsx, SSOCallbackPage.tsx
- `backend/alembic/versions/`: f1a9c3e7d5b2_audit_log_immutability.py
