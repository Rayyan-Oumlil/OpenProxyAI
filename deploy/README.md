# OpenProxyAI — Kubernetes Deployment

Production-grade Helm chart for deploying OpenProxyAI on Kubernetes.

## Prerequisites

| Tool | Minimum version |
|------|----------------|
| Helm | 3.10+ |
| kubectl | 1.26+ |
| Kubernetes cluster | 1.26+ |

Add the Bitnami chart repository (required for the PostgreSQL and Redis subcharts):

```bash
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update
```

## Quick Install

### 1. Create the secrets

The chart expects a Kubernetes Secret containing the three mandatory credentials:

```bash
kubectl create secret generic openproxy-secrets \
  --from-literal=DATABASE_URL="postgresql+asyncpg://openproxyai:<password>@openproxy-postgresql:5432/openproxyai" \
  --from-literal=REDIS_URL="redis://openproxy-redis-master:6379/0" \
  --from-literal=SECRET_KEY="$(openssl rand -hex 32)"
```

If you are using the bundled PostgreSQL subchart you also need the database
password secret it expects:

```bash
kubectl create secret generic openproxy-pg-secret \
  --from-literal=postgres-password="<admin-password>" \
  --from-literal=password="<app-user-password>"
```

### 2. Install the chart

```bash
helm install openproxy deploy/helm/openproxy/ \
  --set existingSecret=openproxy-secrets
```

Verify the rollout:

```bash
kubectl rollout status deployment/openproxy-openproxy
kubectl get pods -l app.kubernetes.io/name=openproxy
```

## Upgrading

```bash
helm upgrade openproxy deploy/helm/openproxy/ \
  --set existingSecret=openproxy-secrets
```

## Scaling

Override `replicaCount` for a one-off manual scale (autoscaling is enabled by
default — disable it first if you want to manage replicas manually):

```bash
helm upgrade openproxy deploy/helm/openproxy/ \
  --set autoscaling.enabled=false \
  --set replicaCount=5
```

## Enabling Ingress (nginx)

```bash
helm upgrade openproxy deploy/helm/openproxy/ \
  --set ingress.enabled=true \
  --set ingress.hosts[0].host=api.yourdomain.com \
  --set ingress.hosts[0].paths[0].path=/ \
  --set ingress.hosts[0].paths[0].pathType=Prefix
```

For TLS with cert-manager:

```bash
helm upgrade openproxy deploy/helm/openproxy/ \
  --set ingress.enabled=true \
  --set ingress.annotations."cert-manager\.io/cluster-issuer"=letsencrypt-prod \
  --set ingress.hosts[0].host=api.yourdomain.com \
  --set ingress.tls[0].secretName=openproxy-tls \
  --set "ingress.tls[0].hosts[0]=api.yourdomain.com"
```

## Using an External Managed Database

When using AWS RDS, Google Cloud SQL, or Azure Database, disable the bundled
PostgreSQL subchart and point the app at your managed instance via the secret:

```bash
# DATABASE_URL in the secret should point to your external host
kubectl create secret generic openproxy-secrets \
  --from-literal=DATABASE_URL="postgresql+asyncpg://user:pass@<rds-host>:5432/openproxyai" \
  --from-literal=REDIS_URL="redis://<elasticache-host>:6379/0" \
  --from-literal=SECRET_KEY="$(openssl rand -hex 32)"

helm install openproxy deploy/helm/openproxy/ \
  --set postgresql.enabled=false \
  --set redis.enabled=false \
  --set existingSecret=openproxy-secrets
```

## Values Reference

| Key | Default | Description |
|-----|---------|-------------|
| `replicaCount` | `3` | Number of API pods (ignored when `autoscaling.enabled=true`) |
| `image.repository` | `openproxyai/backend` | Container image repository |
| `image.tag` | `latest` | Image tag; override to pin a version |
| `image.pullPolicy` | `IfNotPresent` | Image pull policy |
| `service.type` | `ClusterIP` | Kubernetes Service type |
| `service.port` | `8000` | Service port (matches FastAPI's uvicorn port) |
| `ingress.enabled` | `false` | Enable Ingress resource |
| `ingress.className` | `nginx` | IngressClass name |
| `autoscaling.enabled` | `true` | Enable HPA |
| `autoscaling.minReplicas` | `2` | HPA minimum pod count |
| `autoscaling.maxReplicas` | `10` | HPA maximum pod count |
| `autoscaling.targetCPUUtilizationPercentage` | `70` | CPU threshold for scale-out |
| `resources.requests.cpu` | `250m` | CPU request |
| `resources.requests.memory` | `512Mi` | Memory request |
| `resources.limits.cpu` | `1000m` | CPU limit |
| `resources.limits.memory` | `1Gi` | Memory limit |
| `existingSecret` | `""` | Name of Secret with `DATABASE_URL`, `REDIS_URL`, `SECRET_KEY` |
| `env.APP_ENV` | `production` | Application environment |
| `env.PROMETHEUS_ENABLED` | `"true"` | Expose `/metrics` endpoint |
| `env.CORS_ORIGINS` | `""` | Comma-separated allowed CORS origins |
| `env.CLICKHOUSE_URL` | `""` | Optional ClickHouse connection string (Phase 3) |
| `env.LANGFUSE_SECRET_KEY` | `""` | Optional Langfuse secret key |
| `env.LANGFUSE_PUBLIC_KEY` | `""` | Optional Langfuse public key |
| `postgresql.enabled` | `true` | Deploy bundled PostgreSQL subchart |
| `postgresql.primary.persistence.size` | `20Gi` | PostgreSQL PVC size |
| `redis.enabled` | `true` | Deploy bundled Redis subchart |
| `redis.master.persistence.size` | `5Gi` | Redis PVC size |
| `serviceAccount.create` | `true` | Create a dedicated ServiceAccount |
| `podSecurityContext.runAsNonRoot` | `true` | Run as non-root user |
| `podSecurityContext.runAsUser` | `1000` | UID to run as |
| `securityContext.readOnlyRootFilesystem` | `true` | Mount root FS as read-only |
| `securityContext.allowPrivilegeEscalation` | `false` | Prevent privilege escalation |

## Health Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /health` | Liveness probe — always 200, no external dependency checks |
| `GET /ready` | Readiness probe — verifies Postgres + Redis connectivity |

The chart configures Kubernetes probes to match:
- **Liveness** → `/health` (initial delay 15s, period 10s)
- **Readiness** → `/ready` (initial delay 10s, period 5s)

## Uninstall

```bash
helm uninstall openproxy
```

Note: PersistentVolumeClaims are not deleted automatically. Remove them
manually if you want to reclaim storage:

```bash
kubectl delete pvc -l app.kubernetes.io/instance=openproxy
```
