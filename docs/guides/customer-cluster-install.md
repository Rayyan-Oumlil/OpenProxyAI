# Customer-Cluster Install (Data Residency Tier 2)

This guide describes how to install OpenProxyAI on **your own Kubernetes cluster** using customer-provided PostgreSQL and Redis. No OpenProxyAI-managed services (Cloud SQL, Memorystore, Cloud Run) are used. Data stays in your infrastructure.

---

## Overview

| Aspect | Managed (Tier 1) | Customer Cluster (Tier 2) |
|--------|------------------|----------------------------|
| PostgreSQL | Cloud SQL, RDS, etc. | Customer-provided (on-prem or your cloud) |
| Redis | Memorystore, ElastiCache, etc. | Customer-provided |
| Deployment | Cloud Run, EKS, etc. | Your Kubernetes cluster |
| Dependencies | SaaS integrations optional | Fully within your control |

---

## Prerequisites

| Component | Minimum Version |
|-----------|-----------------|
| Kubernetes | 1.20+ |
| PostgreSQL | 15+ (with `pgvector` extension) |
| Redis | 7+ |
| Helm | 3.0+ |

---

## No Managed Dependency Checklist

When installing on your cluster, confirm you are **not** using:

- [ ] Cloud Run or other OpenProxyAI-managed compute
- [ ] Cloud SQL, Memorystore, or other OpenProxyAI-managed databases
- [ ] External SaaS calls except to LLM providers (OpenAI, Anthropic, etc.) you configure
- [ ] Langfuse, ClickHouse dual-write, or analytics beacons (optional — can be disabled)

All data flows through your PostgreSQL and Redis. LLM API calls go only to the providers you configure (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, etc.).

---

## 1. Provision PostgreSQL and Redis

Create PostgreSQL 15+ and Redis 7+ in your environment. Ensure:

- **PostgreSQL**: Create database `openproxyai`, enable `pgvector` extension:
  ```sql
  CREATE EXTENSION IF NOT EXISTS vector;
  ```
- **Redis**: No special config required. Default port 6379.

---

## 2. Create Kubernetes Secret

Create a secret with all required connection strings and keys:

```bash
kubectl create secret generic openproxy-secrets \
  --from-literal=DATABASE_URL="postgresql://user:password@postgres-host:5432/openproxyai" \
  --from-literal=REDIS_URL="redis://redis-host:6379/0" \
  --from-literal=SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')" \
  --from-literal=OPENAI_API_KEY="sk-..." \
  --from-literal=ANTHROPIC_API_KEY="sk-ant-..." \
  -n openproxy
# For air-gap mode, also add:
#   --from-literal=LICENSE_KEY="your-license-key-min-16-chars"
```

### Required env vars

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `REDIS_URL` | Redis connection string |
| `SECRET_KEY` | App secret (min 32 chars) for JWT signing |
| `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` | At least one LLM provider key |

---

## 3. Helm Values Override

Use a values override file that disables bundled PostgreSQL and Redis, and points to your secret:

```yaml
# customer-cluster-values.yaml

# Use customer-provided PostgreSQL (no bundled postgresql subchart)
postgresql:
  enabled: false

# Use customer-provided Redis (no bundled redis subchart)
redis:
  enabled: false

# Inject secrets from your pre-created secret
existingSecret: openproxy-secrets

# Non-secret config
env:
  APP_ENV: production
  PROMETHEUS_ENABLED: "true"
  DEBUG: "false"
  # Optional — leave empty to disable
  CLICKHOUSE_URL: ""
  LANGFUSE_SECRET_KEY: ""
  LANGFUSE_PUBLIC_KEY: ""
  CORS_ORIGINS: "https://your-admin-console.example.com"
  # Air-gap: set both when running fully disconnected (see section 5)
  # AIRGAP_MODE: "true"
  # LICENSE_KEY: "your-license-key-min-16-chars"

# Scaling
replicaCount: 2
autoscaling:
  enabled: true
  minReplicas: 2
  maxReplicas: 10
  targetCPUUtilizationPercentage: 70
```

---

## 4. Install the Chart

```bash
helm install openproxy ./deploy/helm/openproxy \
  -f customer-cluster-values.yaml \
  -n openproxy \
  --create-namespace
```

Migrations run automatically via an init container before the main app starts.

---

## 5. Air-gap mode (optional)

For fully disconnected deployments (no outbound telemetry), set:

| Variable | Description |
|----------|-------------|
| `AIRGAP_MODE` | `true` — disables Langfuse, ClickHouse dual-write, spend reports (Slack/email), and Stripe metered sync. LLM provider calls remain. |
| `LICENSE_KEY` | **Required when AIRGAP_MODE=true.** Min 16 chars. Validates at startup; app fails to start without it. |

**Disabled in air-gap:**
- Langfuse tracing
- ClickHouse dual-write
- Weekly/monthly spend reports (Slack/email)
- Hourly Stripe metered usage sync

**Still active:** Proxy requests to LLM providers, provider health check (pings your configured keys), webhook delivery (to customer-configured URLs), all core gateway features.

---

## 6. Verify

```bash
# Pods running
kubectl get pods -n openproxy

# Health
kubectl port-forward -n openproxy svc/openproxy 8000:8000
curl http://localhost:8000/health
curl http://localhost:8000/ready
```

---

## External Secrets

If you use HashiCorp Vault, External Secrets Operator, or similar, create a secret with the same keys (`DATABASE_URL`, `REDIS_URL`, `SECRET_KEY`, `*_API_KEY`) and set `existingSecret` to that secret name. The Helm chart injects all keys from `existingSecret` via `envFrom`.

---

## Next Steps

- [Deployment guide](../architecture/deployment.md) — full Kubernetes options, ingress, Prometheus
- [Enterprise deployment](./enterprise-deployment.md) — PAC file, DNS, firewall options
- [Security architecture](../compliance/security.md) — encryption, audit logs
