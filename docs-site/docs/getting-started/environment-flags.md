---
title: Environment Flags
description: Environment variables that toggle optional OpenProxyAI subsystems.
---

# Environment Flags

OpenProxyAI's core request path (auth, rate limiting, policy, cache, provider routing) always runs. A small set of environment variables toggle optional subsystems on top of it.

| Flag | Effect |
|---|---|
| `OFF_REGISTRY_MAX_DATA_CLASS` | Default `internal`. The most sensitive data class that may go to destinations the model registry does not govern: the semantic cache's embedding endpoint and the evaluation hook or judge model. With `routing_mode=enforce`, a request above this class is kept away from them (no semantic cache, no evaluation). |
| `ALLOW_INTERNAL_PROVIDER_ENDPOINTS` | Default `false`. When `true`, an org admin may point an `openai` provider key at a private or plain-http `api_base` (vLLM, Ollama's `/v1`, an internal gateway), marked internal. Leave it off on a multi-tenant deployment: it lets an admin aim the gateway at the operator's private network. Link-local and cloud-metadata addresses are refused either way, and the setting is re-read on every connection, so turning it off takes effect immediately. The seeded demo turns it on. |
| `AIRGAP_MODE` | When `true`, disables everything that calls out to a third party the proxy doesn't strictly need to function: Langfuse observability, ClickHouse analytics dual-write, hosted spend reports, and Stripe metered billing sync. Use this for on-prem / air-gapped deployments. |
| `BATCH_SPEND_ENABLED` | Enables batched request-log flushing instead of writing each request individually — reduces database write load at high volume. |
| `VAULT_ADDR`, `VAULT_TOKEN` (or `VAULT_ROLE_ID` and `VAULT_SECRET_ID`), `VAULT_NAMESPACE`, `VAULT_KV_MOUNT`, `VAULT_PATH_PREFIX`, `VAULT_CACHE_SECONDS`, `VAULT_ALLOW_INSECURE_HTTP` | Let provider keys be read from HashiCorp Vault. See [Provider keys from Vault](/guides/secrets-from-vault). Off unless `VAULT_ADDR` and a credential are set. |
| `AWS_SECRETS_ENABLED`, `AWS_SECRETS_REGION`, `AWS_SECRET_PREFIX`, `AWS_SECRET_CACHE_SECONDS` | Let provider keys be read from AWS Secrets Manager. See [Provider keys from Vault](/guides/secrets-from-vault). Off unless enabled. |
| `REALTIME_ENABLED`, `REALTIME_MAX_SESSION_SECONDS`, `REALTIME_MAX_MESSAGE_BYTES`, `REALTIME_MAX_SESSIONS_PER_ORG`, `REALTIME_CHECK_SECONDS` | The realtime WebSocket endpoint and its limits. See [Realtime](/api-reference/realtime). On by default. |
| `UNPRICED_CALL_COST_USD` | Default `0.01`. Charged per unit (an image, a call) when the gateway cannot price a non-chat call, so an unpriced model still counts against budgets. |
| `PROMETHEUS_ENABLED` | Mounts a `/metrics` endpoint for Prometheus scraping. |
| `PROVIDER_HEALTH_CHECK_ENABLED` | Enables periodic background polling of provider health, used by the router to avoid sending traffic to a degraded provider key. |
| `ADAPTIVE_LB_ENABLED` | Enables adaptive load-balancer sampling — the router adjusts weighted rotation based on observed latency instead of using only the static configured weights. |

## Sidecar behavior

ClickHouse (analytics), Langfuse (observability), Prometheus (metrics), and outbound webhook delivery are all treated as **sidecars**: if one of them is unreachable or errors, the request still succeeds. Core request handling (auth, rate limiting, policy, provider calls, and the primary audit log in Postgres) never depends on a sidecar being up.

## Where these are set

Environment flags are set in `backend/.env` (or your deployment's equivalent — a Helm `values.yaml` override, a Kubernetes `ConfigMap`, etc.) and read once at process startup.
