---
title: Deploying OpenProxyAI
description: "Run OpenProxyAI with Docker Compose on one host or with the Helm chart on Kubernetes, and check the settings that matter before production."
---

# Deploying OpenProxyAI

OpenProxyAI is one API service backed by Postgres (with the pgvector extension) and Redis. This page covers two ways to run it: Docker Compose for a local or single-host setup, and the Helm chart for Kubernetes. It ends with a production checklist drawn from the files that ship in the repository. Read it if you operate the gateway; you do not need it to use the API.

## What you need to run

| Component | Role | Notes |
|---|---|---|
| API | The gateway and admin API | Listens on the port in `PORT` (default 8080 in the image). |
| Postgres | Primary data store | Needs the `vector` extension; migrations run `CREATE EXTENSION vector`. |
| Redis | Rate limits, caches, sign-in state | Must be reachable at startup. |
| ClickHouse | Optional analytics dual-write | Off by default; the proxy runs without it. |
| Admin console | Web UI | Optional in the Helm chart (`frontend.enabled`). |

Configuration is read from environment variables once at startup. The three you must set are `DATABASE_URL`, `REDIS_URL` and `SECRET_KEY`. With `APP_ENV=production`, the default `SECRET_KEY` is rejected and the process refuses to start. Provider API keys and SSO client secrets are encrypted with a key derived from `SECRET_KEY`, so changing it later makes them undecryptable. See [Environment flags](/getting-started/environment-flags) for optional subsystems.

## Docker Compose

The repository's `docker-compose.yml` defines `api`, `postgres`, `redis` and an optional `clickhouse`. Treat it as a development setup: the `api` service bind-mounts `./backend` and runs uvicorn with `--reload`.

### Start the data stores

Copy `backend/.env.example` to `backend/.env` and fill it in, then:

```bash
docker compose up -d postgres redis
```

| Service | Host port | Notes |
|---|---|---|
| `postgres` (pgvector 16) | `127.0.0.1:5434` | Port 5434 avoids clashing with a local Postgres. Password comes from `DB_PASSWORD`, default `openproxyai_dev`. |
| `redis` | `127.0.0.1:6379` | Both bind to localhost only. |

### Run migrations and start the API

```bash
docker compose up -d api
docker compose exec api alembic upgrade head
```

The `api` service in the main Compose file requests an NVIDIA GPU. On a host without a GPU runtime, remove the `deploy.resources` block or use the demo stack, which needs no GPU. The in-network database address (`postgres:5432`) and the host-mapped one (`localhost:5434`) are not interchangeable: the `.env.example` value suits the container, and a host process needs the host port.

To run the API on the host instead:

```bash
cd backend
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### Verify

```bash
curl http://localhost:8000/health
```

```json
{"status": "healthy", "app": "OpenProxyAI", "version": "0.1.0"}
```

`/health` only proves the process is up. `GET /ready` checks Postgres and Redis and returns `503` with `{"status": "not ready", "postgres": "...", "redis": "..."}` when either is down. The log line "Startup complete" marks the end of startup.

### Optional analytics sidecar

```bash
docker compose --profile analytics up -d clickhouse
```

ClickHouse loads its schema on first start. Keep its ports 8123 and 9000 on a trusted network.

### Try it with seeded data

```bash
docker compose -f docker-compose.demo.yml up --build
```

This starts a self-contained stack with its own Postgres, Redis and a fake OpenAI-compatible upstream, runs migrations, creates a demo organization and sends traffic so the console opens with data (console on `http://localhost:5173`, API on `http://localhost:8000`). Its credentials are public demo values. Never deploy that file.

## Kubernetes with Helm

The chart lives at `deploy/helm/openproxy`. It deploys the API as a `Deployment` with a Service, a HorizontalPodAutoscaler, a PodDisruptionBudget, an optional Ingress, an optional Prometheus `ServiceMonitor`, and an optional console (`frontend.enabled`).

### Install

Create a Secret holding the three required values, then install:

```bash
kubectl create secret generic openproxy-secrets \
  --from-literal=DATABASE_URL="postgresql+asyncpg://user:pass@db-host:5432/openproxyai" \
  --from-literal=REDIS_URL="redis://redis-host:6379/0" \
  --from-literal=SECRET_KEY="$(openssl rand -hex 32)"

helm install openproxy deploy/helm/openproxy/ \
  --set existingSecret=openproxy-secrets
kubectl rollout status deployment/openproxy-openproxy
```

The chart runs the gateway and, optionally, the console. Point it at your own managed PostgreSQL (with pgvector) and Redis through the Secret, as `values.prod.yaml` does.

### What happens on each rollout

- An init container runs `alembic upgrade head` before the API starts, using the same ConfigMap and Secret.
- The liveness probe calls `/health` (15s delay, every 10s); the readiness probe calls `/ready` (10s delay, every 5s), so a pod leaves the Service while Postgres or Redis is unreachable.
- Pods run as non-root (UID 1000) with a read-only root filesystem, all capabilities dropped and an `emptyDir` mounted at `/tmp`.
- Changing the ConfigMap restarts the pods.

### Port

The chart sets `PORT` to 8000 so the container, the probes and the Service agree. Keep `env.PORT`, `service.port` and the container port equal if you change one.

### Common values

| Key | Default | Purpose |
|---|---|---|
| `replicaCount` | `3` | Used only when `autoscaling.enabled` is `false`. |
| `autoscaling.minReplicas` / `maxReplicas` | `2` / `10` | HPA bounds; scales at 70% CPU. |
| `image.repository` / `image.tag` | `openproxyai/backend` / `latest` | Pin a tag for real deployments. |
| `resources` | 250m / 512Mi requests, 1 CPU / 1Gi limits | Per pod. |
| `existingSecret` | `""` | Secret with `DATABASE_URL`, `REDIS_URL`, `SECRET_KEY`. |
| `env.CORS_ORIGINS` | `""` | Allowed browser origins. |
| `env.PROMETHEUS_ENABLED` | `"true"` | Serves `/metrics`. |
| `podDisruptionBudget.minAvailable` | `1` | Keep this below the minimum replica count. |
| `prometheus.serviceMonitor.enabled` | `false` | Turn on with kube-prometheus-stack. |

Other `env` keys you set (for example `AIRGAP_MODE`, `PORT`, `FRONTEND_BASE_URL`, `APP_BASE_URL`) are passed to the container as environment variables. `values.prod.yaml` is a production starting point: three replicas minimum, 500m/768Mi requests, a minimum availability of 2 and the ServiceMonitor on.

```bash
helm upgrade --install openproxy deploy/helm/openproxy/ \
  -f deploy/helm/openproxy/values.prod.yaml \
  --set image.tag=<git-sha>
```

### Ingress and TLS

Enable the Ingress with a single host. Set `ingress.host` and, for HTTPS, `ingress.tls.secretName`.

```yaml
ingress:
  enabled: true
  className: nginx
  host: gateway.example.com
  tls:
    secretName: openproxy-tls
```

When `ingress.tls` is set, the Ingress asks cert-manager for a certificate from a `ClusterIssuer` named `letsencrypt-prod` and forces HTTPS. `deploy/k8s/cluster-issuer.yaml` defines one with a placeholder contact email; edit it before applying.

The Ingress sends `/api`, `/v1`, `/scim/v2`, `/health` and `/ready` to the API, and everything else to the console when `frontend.enabled` is true, otherwise to the API.

### Air-gapped deployments

Set `AIRGAP_MODE` to `"true"` under `env`. It disables Langfuse, ClickHouse dual-write, hosted spend reports and Stripe metered sync. It also requires `LICENSE_KEY` (at least 16 characters); add it to the Secret, because startup fails without it. See [Data residency](/security/data-residency).

### Scale, upgrade and remove

```bash
helm upgrade openproxy deploy/helm/openproxy/ --set autoscaling.enabled=false --set replicaCount=5
helm upgrade openproxy deploy/helm/openproxy/ --set existingSecret=openproxy-secrets
helm uninstall openproxy
```

Uninstalling does not delete PersistentVolumeClaims; remove them yourself if you used any.

## Production checklist

- [ ] `APP_ENV=production` and a random `SECRET_KEY` of 32 or more characters, stored in a Secret and backed up. Losing it loses stored provider keys.
- [ ] Postgres with pgvector and Redis are managed, backed up and reachable from the pods.
- [ ] Image tag pinned (not `latest`) and the migration init container succeeds on rollout.
- [ ] `CORS_ORIGINS` lists only your console origin; `FRONTEND_BASE_URL` and `APP_BASE_URL` are set if you use [SSO](/guides/sso-and-scim).
- [ ] HTTPS at the Ingress and a `/v1` route that reaches the API.
- [ ] `/ready` used for readiness; `podDisruptionBudget.minAvailable` is lower than the minimum replica count.
- [ ] If `/metrics` is scraped, set `METRICS_BEARER_TOKEN`: the labels include organization ids and models.
- [ ] `DEBUG` is `"false"`.
- [ ] Optional sidecars (ClickHouse, Langfuse) are off unless you run them; `ALLOW_INTERNAL_PROVIDER_ENDPOINTS` is left off on shared deployments.
- [ ] Docker Compose files are not used for production: the main one reloads code from disk, and the demo one has public credentials.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Process exits at startup in production | Default `SECRET_KEY`, or `AIRGAP_MODE` without a valid `LICENSE_KEY`. | Set the missing value in the Secret. |
| `api` container will not start in Compose | The service reserves an NVIDIA GPU. | Remove the reservation or run the API on the host. |
| Migration fails on `CREATE EXTENSION vector` | The Postgres image or managed instance lacks pgvector. | Use a pgvector-enabled database. |
| Pods never become ready | `/ready` returns `503`. | Check Postgres and Redis reachability. |
| Host process cannot reach the database | Using `postgres:5432` from outside Docker. | Use `localhost:5434`. |
| `/v1/...` returns the console page | Console enabled and no route for `/v1`. | Add an Ingress route to the API. |

## Next steps

- [Environment flags](/getting-started/environment-flags)
- [Single sign-on and SCIM](/guides/sso-and-scim)
- [Data residency](/security/data-residency)
- [Quickstart](/getting-started/quickstart)
