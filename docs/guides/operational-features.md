# Operational Features

> Background jobs and optional config for production deployments. See [deploy/gcp/env.template](../../deploy/gcp/env.template) for all env vars.

## Batched spend writes

Reduces database write load under high traffic by queuing spend updates in Redis and flushing to Postgres on an interval.

| Env var | Default | Description |
|---------|---------|-------------|
| `BATCH_SPEND_ENABLED` | `false` | Enable batched spend writes |
| `BATCH_SPEND_FLUSH_INTERVAL_SECONDS` | `60` | Flush interval |
| `BATCH_SPEND_MAX_SIZE` | `500` | Max queued items per flush |

When disabled, spend is written to Postgres on each request.

## Provider health check

APScheduler pings provider keys periodically. Unhealthy keys are excluded from routing.

| Env var | Default | Description |
|---------|---------|-------------|
| `PROVIDER_HEALTH_CHECK_ENABLED` | `false` | Enable health pings |
| `PROVIDER_HEALTH_FAILURE_THRESHOLD` | `3` | Consecutive failures before marking unhealthy |

Runs every 5 minutes. See [model-routing.md](./model-routing.md) for provider key setup.

## Circuit breaker

When enabled, tracks per-key failures (429/5xx). After N consecutive failures, the key is skipped until cooldown expires. Uses Redis for state.

| Env var | Default | Description |
|---------|---------|-------------|
| `CIRCUIT_BREAKER_ENABLED` | `false` | Enable per-key circuit breaker |
| `CIRCUIT_BREAKER_FAILURE_THRESHOLD` | `5` | Consecutive failures before opening circuit |
| `CIRCUIT_BREAKER_COOLDOWN_SECONDS` | `60` | Seconds before circuit closes and key is retried |

When all keys for a model have open circuits, the gateway returns 503 with `Retry-After` header.

## Adaptive load balancing

Samples latency and error rate per provider key from `request_logs` and adjusts effective weights for key selection. Healthier keys (lower p99 latency, lower error rate) receive more traffic.

| Env var | Default | Description |
|---------|---------|-------------|
| `ADAPTIVE_LB_ENABLED` | `false` | Enable adaptive sampling and dynamic weights |
| `ADAPTIVE_LB_SAMPLE_MINUTES` | `10` | Lookback window for request_logs aggregation |
| `ADAPTIVE_LB_WEIGHT_FLOOR` | `0.1` | Minimum effective weight multiplier for degraded keys |

**Dashboard:** Provider Keys page shows **P99 (ms)**, **Error %**, and **Eff. Weight** when adaptive LB is enabled. Effective weight is `base_weight × health_factor`, where health penalizes high latency and errors.

See [model-routing.md](./model-routing.md#adaptive-load-balancing) for selection behavior.

## Spend reports

Weekly (Monday 9am UTC) and monthly (1st 9am UTC) digest of org spend. Orgs opt-in via settings.

**Org settings** (JSON in `Organization.settings`):

```json
{
  "spend_report": {
    "webhook": "https://hooks.slack.com/services/...",
    "email": "admin@org.com"
  }
}
```

- **Slack:** Set `webhook` to your incoming webhook URL.
- **Email:** Requires `SENDGRID_API_KEY` and `EMAIL_FROM` env vars.

| Env var | Description |
|---------|-------------|
| `SENDGRID_API_KEY` | SendGrid API key for email delivery |
| `EMAIL_FROM` | From address (e.g. `noreply@openproxyai.com`) |

## Key rotation scheduler

Re-encrypts provider keys on a schedule (keeps same plaintext, rotates ciphertext). Complements [manual key rotation](./model-routing.md#key-rotation) and satisfies SOC 2 CC9.2.

| Env var | Default | Description |
|---------|---------|-------------|
| `KEY_ROTATION_SCHEDULER_ENABLED` | `false` | Enable scheduled rotation |
| `KEY_ROTATION_INTERVAL_DAYS` | `30` | Days between rotations |

See [security.md](../compliance/security.md#provider-key-rotation) for compliance context.
