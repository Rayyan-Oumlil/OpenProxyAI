# Policy Configuration

> **Applies to:** All plans

Policies are rules that govern how requests are processed before being forwarded to LLM providers. Configure content filtering, model allowlists, PII detection, and response guardrails via the policy API.

## Enforcement Modes

Each policy can operate in one of three modes:

| Mode | Behavior |
|------|----------|
| `off` | No policy checks — all requests allowed |
| `log_only` | Policy violations logged but requests allowed to proceed |
| `enforce` | Policy violations blocked — request returns HTTP 446 |

**When to use each:**

- **`off`:** Development, testing, or organizations with no compliance requirements
- **`log_only`:** Monitoring period before enforcement; understand violation patterns
- **`enforce`:** Production, regulated industries (finance, healthcare), high-risk environments

## Getting the Current Policy

Retrieve the organization's current policy configuration:

```bash
curl -X GET https://api.openproxy.ai/api/v1/organizations/current/policy \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Response:**

```json
{
  "enforcement_mode": "enforce",
  "allowed_models": ["openai/gpt-4o", "anthropic/claude-3-sonnet"],
  "blocked_keywords": ["password", "secret"],
  "pii_detection_enabled": true,
  "pii_entities": ["PERSON", "EMAIL", "PHONE_NUMBER", "CREDIT_CARD"],
  "model_rate_limits": {
    "openai/gpt-4o": {
      "rpm": 60,
      "tpm": 100000
    }
  },
  "prompt_injection_detection_enabled": true,
  "response_guardrails_enabled": true,
  "response_pii_redact": true,
  "updated_at": "2026-03-15T14:30:00Z"
}
```

## Updating Policy Configuration

Update policy settings with a PATCH request. Only provided fields are changed; omitted fields retain their current values.

```bash
curl -X PATCH https://api.openproxy.ai/api/v1/organizations/current/policy \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "enforcement_mode": "enforce",
    "allowed_models": ["openai/gpt-4o", "anthropic/claude-3-sonnet"],
    "blocked_keywords": ["password", "api_key"],
    "pii_detection_enabled": true,
    "pii_entities": ["EMAIL", "CREDIT_CARD"],
    "prompt_injection_detection_enabled": true,
    "response_guardrails_enabled": true,
    "response_pii_redact": true
  }'
```

**Changes take effect within 60 seconds** (Redis cache TTL).

### Request Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enforcement_mode` | `"off" \| "log_only" \| "enforce"` | `"off"` | How violations are handled |
| `allowed_models` | array[string] | `[]` | Allowlist of model names; empty = allow all |
| `blocked_keywords` | array[string] | `[]` | Words/phrases that trigger a violation (case-insensitive substring match) |
| `pii_detection_enabled` | boolean | `true` | Enable PII detection (requires Presidio service) |
| `pii_entities` | array[string] | `[]` | Entity types to detect (e.g., `["EMAIL", "CREDIT_CARD", "PERSON"]`) |
| `model_rate_limits` | object | `{}` | Per-model rate limits (see below) |
| `prompt_injection_detection_enabled` | boolean | `false` | Detect prompt injection patterns |
| `response_guardrails_enabled` | boolean | `false` | Check LLM responses for violations |
| `response_pii_redact` | boolean | `false` | Redact PII from responses instead of blocking |

## Model Allowlist

Control which models users can access. An empty list allows all models.

```json
{
  "allowed_models": [
    "openai/gpt-4o",
    "openai/gpt-4-turbo",
    "anthropic/claude-3-sonnet",
    "anthropic/claude-3-opus"
  ]
}
```

When a request uses a model not in the allowlist:

- **Mode `off`:** Request allowed
- **Mode `log_only`:** Request allowed, violation logged with reason code `model_not_allowed`
- **Mode `enforce`:** Request blocked with HTTP 446, reason code `model_not_allowed`

## Blocked Keywords

Specify words or phrases that trigger policy violations. Matching is case-insensitive and substring-based.

```json
{
  "blocked_keywords": [
    "password",
    "api_key",
    "secret",
    "credit card"
  ]
}
```

If a user's prompt contains any blocked keyword:

- **Mode `off`:** Request allowed
- **Mode `log_only`:** Request allowed, violation logged with reason code `blocked_keyword` and the matched keyword in `detail`
- **Mode `enforce`:** Request blocked with HTTP 446

Example: if `"password"` is blocked and user sends a message containing `"My password is..."`, it matches (case-insensitive substring).

## PII Detection

Detect personally identifiable information (emails, phone numbers, SSNs, credit card numbers, names).

### Requirements

Regex-based PII detection is active by default — no additional setup required. It detects:
- Email addresses
- SSN (XXX-XX-XXXX)
- Credit card numbers (13-19 digits)

Presidio NLP is available but disabled by default due to image size (+800MB) — uncomment `presidio-analyzer` in `requirements.txt` to enable.

### Configuration

```json
{
  "pii_detection_enabled": true,
  "pii_entities": [
    "EMAIL",
    "PHONE_NUMBER",
    "CREDIT_CARD",
    "PERSON",
    "DATE_TIME",
    "DOMAIN_NAME",
    "LOCATION",
    "IP_ADDRESS"
  ]
}
```

**Supported Entities (Presidio NLP, when enabled):**

| Entity | Description |
|--------|-------------|
| `EMAIL` | Email addresses |
| `PHONE_NUMBER` | Phone numbers (international) |
| `CREDIT_CARD` | Credit card numbers |
| `PERSON` | Person names |
| `DATE_TIME` | Dates, times, timestamps |
| `DOMAIN_NAME` | Domain names and URLs |
| `LOCATION` | Geographic locations |
| `IP_ADDRESS` | IPv4/IPv6 addresses |

When PII is detected:

- **Mode `off`:** Request allowed
- **Mode `log_only`:** Request allowed, violation logged with the entity type in `detail`
- **Mode `enforce`:** Request blocked with HTTP 446

## Prompt Injection Detection

Detect common prompt injection patterns that attempt to override system instructions.

```json
{
  "prompt_injection_detection_enabled": true
}
```

**Patterns detected:**

- "ignore all previous/prior instructions"
- "you are now..."
- "act as..."
- "pretend you are / to be..."
- "jailbreak"
- "DAN mode"
- "developer mode"
- "disregard your training / guidelines / rules"

When injection detected:

- **Mode `off`:** Request allowed
- **Mode `log_only`:** Request allowed, violation logged with reason code `prompt_injection_detected`
- **Mode `enforce`:** Request blocked with HTTP 446

## Response Guardrails

Check LLM responses for policy violations before returning them to the user.

```json
{
  "response_guardrails_enabled": true,
  "response_pii_redact": true
}
```

### Behavior

**If `response_guardrails_enabled = false`:**
- No response checking; responses returned as-is

**If `response_guardrails_enabled = true` and `response_pii_redact = false`:**
- Response is checked for blocked keywords and PII
- If violation found, response is blocked (HTTP 446)
- User sees error message instead of LLM output

**If `response_guardrails_enabled = true` and `response_pii_redact = true`:**
- Response is checked for PII
- If PII found, it's automatically redacted (replaced with `[REDACTED]`)
- Response is allowed through with redacted content
- Blocked keywords still trigger a block (not redacted)

### Example: PII Redaction

Request:

```json
{
  "model": "openai/gpt-4o",
  "messages": [{"role": "user", "content": "What's my account info?"}]
}
```

Original Response:

```
Your account email is john.doe@example.com and phone is 555-1234.
```

With `response_pii_redact = true`:

```
Your account email is [REDACTED] and phone is [REDACTED].
```

## Per-Model Rate Limits

Apply different rate limits to specific models beyond the organization's default.

```json
{
  "model_rate_limits": {
    "openai/gpt-4o": {
      "rpm": 60,
      "tpm": 100000
    },
    "anthropic/claude-3-opus": {
      "rpm": 30,
      "tpm": 50000
    }
  }
}
```

**Dictionary structure:** `model_name` → `{ "rpm": number, "tpm": number }`

- **`rpm`:** Requests per minute for this model
- **`tpm`:** Tokens per minute for this model

If a model is not listed, it uses the organization's default rate limits.

When a per-model limit is exceeded:

- Request is blocked with HTTP 429 (Too Many Requests)
- Headers include `Retry-After` and remaining quota info
- Applies regardless of enforcement mode

## Policy Violation Response (HTTP 446)

When enforcement mode is `enforce` and a violation is detected:

```
HTTP 446 Policy Violation

{
  "error": "policy_violation",
  "detail": {
    "reason_code": "blocked_keyword",
    "detail": "Request matched blocked keyword: password",
    "action": "block",
    "triggered_rules": ["blocked_keyword"],
    "mode": "enforce"
  }
}
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `reason_code` | string | Why violation occurred (e.g., `model_not_allowed`, `blocked_keyword`, `pii_detected`, `prompt_injection_detected`) |
| `detail` | string | Human-readable violation description |
| `action` | string | What happened (`"block"` in enforce mode) |
| `triggered_rules` | array[string] | List of rules that triggered (e.g., `["blocked_keyword"]`) |
| `mode` | string | Enforcement mode (`"enforce"`) |

## Log-Only Mode Response (HTTP 200)

In `log_only` mode, requests are allowed but violations are recorded:

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "choices": [
    {
      "message": {
        "role": "assistant",
        "content": "..."
      }
    }
  ],
  "_policy_metadata": {
    "allowed": true,
    "action": "log_only",
    "reason_code": "blocked_keyword",
    "detail": "Request matched blocked keyword: password",
    "triggered_rules": ["blocked_keyword"],
    "mode": "log_only"
  }
}
```

The response includes policy metadata in `_policy_metadata` for auditing (not in stream mode).

## Plan Gating

Some policy features require higher-tier plans:

| Feature | Free | Starter+ | Growth+ | Enterprise |
|---------|------|----------|---------|------------|
| Policy enforcement | ✓ | ✓ | ✓ | ✓ |
| Model allowlist | ✓ | ✓ | ✓ | ✓ |
| Blocked keywords | ✓ | ✓ | ✓ | ✓ |
| PII detection | — | ✓ | ✓ | ✓ |
| Prompt injection detection | — | ✓ | ✓ | ✓ |
| Response guardrails | — | ✓ | ✓ | ✓ |
| Per-model rate limits | — | ✓ | ✓ | ✓ |

Attempting to enable a feature your plan doesn't support returns:

```
HTTP 402 Payment Required

{
  "detail": "Plan does not support PII detection. Upgrade to Starter or higher."
}
```

## Webhook Notifications

When policy violations occur, webhooks can be dispatched. See [Cost Management](./cost-management.md) for webhook configuration.

**Policy-related events:**

- `policy.violation` — Fired when a request is blocked or logged (depending on mode and configuration)

## Compliance Templates

Pre-built policy configurations for regulated industries. Templates apply on top of existing policy using merge semantics — your current `allowed_models` and `model_rate_limits` are preserved.

### Available Templates

| Template | Industry | What it configures |
|----------|----------|-------------------|
| `healthcare_hipaa` | Healthcare | SSN/MRN PII detection, PHI keyword blocking, `enforce` mode, model allowlist (no external fine-tunes) |
| `finance_pci` | Finance | Credit card regex, trade compliance keywords, `enforce` mode, SOX audit format |
| `government_fedramp` | Government | US-only model allowlist, classified keyword blocking, `enforce` mode, strict PII |

### Listing Templates

```bash
curl https://api.openproxy.ai/api/v1/organizations/current/policy/templates \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Applying a Template

```bash
curl -X POST https://api.openproxy.ai/api/v1/organizations/current/policy/apply-template \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"template_id": "healthcare_hipaa"}'
```

**Merge behavior:**
- `enforcement_mode` is set to the template's value (typically `enforce`)
- `blocked_keywords` are replaced with the template's list
- `pii_entities` are replaced with the template's list
- `allowed_models` are **preserved** (not overwritten)
- `model_rate_limits` are **preserved** (not overwritten)

An audit log entry is created with `action = "policy.template_applied"`.

The Redis policy cache is invalidated immediately — the new config takes effect on the next request.

## Caching and Propagation

Policy changes are cached in Redis with a 60-second TTL. After updating:

1. Changes are written to the organization's `settings.policy` in PostgreSQL
2. Redis cache is invalidated
3. Next request loads fresh policy from database
4. Policy is cached for 60 seconds

For a globally distributed setup, policy changes propagate within ~60 seconds per instance.
