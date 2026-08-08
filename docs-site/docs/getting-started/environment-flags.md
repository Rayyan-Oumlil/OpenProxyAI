---
title: Environment Flags
description: Environment variables that toggle optional OpenProxyAI subsystems.
---

# Environment Flags

OpenProxyAI's core request path (auth, rate limiting, policy, cache, provider routing) always runs. A small set of environment variables toggle optional subsystems on top of it.

| Flag | Effect |
|---|---|
| `AIRGAP_MODE` | When `true`, disables everything that calls out to a third party the proxy doesn't strictly need to function: Langfuse observability, ClickHouse analytics dual-write, hosted spend reports, and Stripe metered billing sync. Use this for on-prem / air-gapped deployments. |
| `BATCH_SPEND_ENABLED` | Enables batched request-log flushing instead of writing each request individually — reduces database write load at high volume. |
| `PROMETHEUS_ENABLED` | Mounts a `/metrics` endpoint for Prometheus scraping. |
| `PROVIDER_HEALTH_CHECK_ENABLED` | Enables periodic background polling of provider health, used by the router to avoid sending traffic to a degraded provider key. |
| `ADAPTIVE_LB_ENABLED` | Enables adaptive load-balancer sampling — the router adjusts weighted rotation based on observed latency instead of using only the static configured weights. |

## Sidecar behavior

ClickHouse (analytics), Langfuse (observability), Prometheus (metrics), and outbound webhook delivery are all treated as **sidecars**: if one of them is unreachable or errors, the request still succeeds. Core request handling (auth, rate limiting, policy, provider calls, and the primary audit log in Postgres) never depends on a sidecar being up.

## Where these are set

Environment flags are set in `backend/.env` (or your deployment's equivalent — a Helm `values.yaml` override, a Kubernetes `ConfigMap`, etc.) and read once at process startup.
