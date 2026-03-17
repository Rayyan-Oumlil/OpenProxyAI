# OpenProxyAI Deployment Guide

OpenProxyAI supports two deployment modes: Docker Compose for development and small-scale deployments, and Kubernetes with Helm for production.

## Docker Compose (Development)

### Quick Start

Clone the repository and start the stack:

```bash
cd openproxyai
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
export SECRET_KEY="your-secret-key-minimum-32-characters-long"

docker compose up -d
```

This starts three services:

```yaml
backend:
  image: openproxyai/backend:latest
  ports:
    - "8000:8000"
  environment:
    DATABASE_URL: postgresql://openproxyai:password@postgres:5432/openproxyai
    REDIS_URL: redis://redis:6379/0
    OPENAI_API_KEY: ${OPENAI_API_KEY}
    ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
    SECRET_KEY: ${SECRET_KEY}

postgres:
  image: pgvector/pgvector:pg16
  volumes:
    - postgres_data:/var/lib/postgresql/data
  environment:
    POSTGRES_DB: openproxyai
    POSTGRES_USER: openproxyai
    POSTGRES_PASSWORD: password

redis:
  image: redis:7-alpine
  volumes:
    - redis_data:/data
```

### Database Migrations

After the containers are running, apply migrations:

```bash
docker compose exec backend alembic upgrade head
```

The backend service will automatically wait for PostgreSQL to be ready before starting. Check migration status:

```bash
docker compose exec backend alembic history
```

### Health Checks

Verify the proxy is ready:

```bash
# Liveness (returns 200 if process is alive)
curl http://localhost:8000/health

# Readiness (returns 200 only if DB and Redis are connected)
curl http://localhost:8000/ready
```

### Analytics Profile (Optional)

For local testing of analytics features, bring up ClickHouse:

```bash
docker compose --profile analytics up -d
```

This adds a ClickHouse container. Set in `.env`:

```
CLICKHOUSE_URL=http://clickhouse:8123/default
```

### Logs and Monitoring

View proxy logs:

```bash
docker compose logs -f backend
```

Access PostgreSQL:

```bash
docker compose exec postgres psql -U openproxyai -d openproxyai
```

Stop everything:

```bash
docker compose down
docker compose down -v  # Also remove volumes (careful!)
```

## Kubernetes with Helm

### Prerequisites

- Kubernetes 1.20+
- Helm 3.0+
- kubectl configured to access your cluster
- Secrets pre-created (API keys, database passwords)

### Installation

#### 1. Create Kubernetes Secrets

First, create a secret containing database credentials and LLM provider keys:

```bash
kubectl create secret generic openproxy-secrets \
  --from-literal=DATABASE_URL="postgresql://openproxyai:password@pg-service:5432/openproxyai" \
  --from-literal=REDIS_URL="redis://redis-service:6379/0" \
  --from-literal=SECRET_KEY="your-secret-key-minimum-32-characters" \
  --from-literal=OPENAI_API_KEY="sk-..." \
  --from-literal=ANTHROPIC_API_KEY="sk-ant-..." \
  -n openproxy
```

For PostgreSQL password (Bitnami chart):

```bash
kubectl create secret generic openproxy-pg-secret \
  --from-literal=postgres-password="postgres-admin-password" \
  --from-literal=password="openproxyai-user-password" \
  -n openproxy
```

#### 2. Customize values.yaml

Copy `deploy/helm/openproxy/values.yaml` and override key values:

```yaml
replicaCount: 3

image:
  repository: openproxyai/backend
  tag: "0.1.0"

service:
  type: LoadBalancer  # or ClusterIP for internal, NodePort for testing
  port: 8000

ingress:
  enabled: true
  className: nginx
  hosts:
    - host: api.example.com
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: openproxy-tls
      hosts:
        - api.example.com

autoscaling:
  enabled: true
  minReplicas: 2
  maxReplicas: 10
  targetCPUUtilizationPercentage: 70

resources:
  requests:
    cpu: 250m
    memory: 512Mi
  limits:
    cpu: 1000m
    memory: 1Gi

# PostgreSQL (set to false if using managed database)
postgresql:
  enabled: false  # use external RDS/Cloud SQL instead

# Redis (set to false if using managed cache)
redis:
  enabled: false  # use external ElastiCache/Memorystore instead

# Reference existing secret with DATABASE_URL, REDIS_URL, SECRET_KEY, API keys
existingSecret: openproxy-secrets

env:
  APP_ENV: production
  DEBUG: "false"
  PROMETHEUS_ENABLED: "true"
  CLICKHOUSE_URL: "http://clickhouse-service:8123/default"  # optional
  LANGFUSE_HOST: "https://cloud.langfuse.com"

# For Prometheus auto-discovery
prometheus:
  serviceMonitor:
    enabled: true
    additionalLabels:
      release: prometheus
```

#### 3. Install the Chart

```bash
helm install openproxy ./deploy/helm/openproxy \
  -f custom-values.yaml \
  -n openproxy \
  --create-namespace
```

#### 4. Verify Deployment

```bash
# Check pod status
kubectl get pods -n openproxy

# Check service
kubectl get svc -n openproxy

# Tail logs
kubectl logs -f -n openproxy -l app=openproxy --all-containers=true

# Test health
kubectl port-forward -n openproxy svc/openproxy 8000:8000
curl http://localhost:8000/health
```

### Production Configuration

#### High Availability Setup

For production, enable these features:

```yaml
replicaCount: 3

autoscaling:
  enabled: true
  minReplicas: 2
  maxReplicas: 20
  targetCPUUtilizationPercentage: 70

podDisruptionBudget:
  enabled: true
  minAvailable: 1  # Ensures 1 pod stays running during drain

resources:
  requests:
    cpu: 500m
    memory: 1Gi
  limits:
    cpu: 2000m
    memory: 2Gi

securityContext:
  readOnlyRootFilesystem: true
  allowPrivilegeEscalation: false
  capabilities:
    drop:
      - ALL
  runAsNonRoot: true
  runAsUser: 1000

# Use external managed PostgreSQL (AWS RDS, Cloud SQL, Azure Database)
postgresql:
  enabled: false

# Use external managed Redis (AWS ElastiCache, Cloud Memorystore)
redis:
  enabled: false
```

#### Liveness and Readiness Probes

The Helm chart includes default probes. Customize in values.yaml if needed:

```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 15
  periodSeconds: 10
  failureThreshold: 3
  timeoutSeconds: 5

readinessProbe:
  httpGet:
    path: /ready
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 5
  failureThreshold: 3
  timeoutSeconds: 5
```

- **Liveness probe** (`/health`) returns 200 if the process is alive. Failure triggers pod restart.
- **Readiness probe** (`/ready`) checks database and Redis connectivity. Failure removes pod from service endpoints until dependencies recover.

#### Network Policy (Optional)

Restrict traffic to the proxy:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: openproxy-network-policy
  namespace: openproxy
spec:
  podSelector:
    matchLabels:
      app: openproxy
  policyTypes:
    - Ingress
    - Egress
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              name: ingress-nginx
      ports:
        - protocol: TCP
          port: 8000
  egress:
    # Allow DNS
    - to:
        - namespaceSelector: {}
      ports:
        - protocol: UDP
          port: 53
    # Allow PostgreSQL
    - to:
        - podSelector:
            matchLabels:
              app: postgres
      ports:
        - protocol: TCP
          port: 5432
    # Allow Redis
    - to:
        - podSelector:
            matchLabels:
              app: redis
      ports:
        - protocol: TCP
          port: 6379
    # Allow external HTTPS (to LLM providers)
    - to:
        - namespaceSelector: {}
      ports:
        - protocol: TCP
          port: 443
```

#### Monitoring with Prometheus

Enable Prometheus scraping by setting:

```yaml
prometheus:
  serviceMonitor:
    enabled: true
    interval: 30s
    scrapeTimeout: 10s
    additionalLabels:
      release: prometheus  # Must match your Prometheus' serviceMonitorSelector
```

This creates a `ServiceMonitor` that tells Prometheus to scrape metrics from the proxy at `/metrics`.

#### RBAC and Service Account

The chart creates a service account by default. Grant it permissions if needed:

```yaml
serviceAccount:
  create: true
  name: openproxy
```

Create a `Role` if the proxy needs to query Kubernetes API (e.g., for dynamism config loading):

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: openproxy-reader
  namespace: openproxy
rules:
  - apiGroups: [""]
    resources: ["configmaps", "secrets"]
    verbs: ["get", "list", "watch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: openproxy-reader-binding
  namespace: openproxy
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: openproxy-reader
subjects:
  - kind: ServiceAccount
    name: openproxy
    namespace: openproxy
```

### Database Migrations in Kubernetes

Migrations run automatically via an init container in the deployment spec:

```yaml
initContainers:
  - name: migrate
    image: "openproxyai/backend:latest"
    imagePullPolicy: IfNotPresent
    command: ["alembic", "upgrade", "head"]
    envFrom:
      - configMapRef:
          name: openproxy-config
      - secretRef:
          name: openproxy-secrets
```

This ensures the schema is up-to-date before the main container starts. If migration fails, the pod does not become Ready.

Check migration status:

```bash
kubectl run -it --rm --image=openproxyai/backend:latest --restart=Never \
  -e DATABASE_URL="..." \
  -- alembic history
```

### Scaling and Auto-Scaling

#### Manual Scaling

Scale replicas up or down:

```bash
kubectl scale deployment/openproxy --replicas=5 -n openproxy
```

#### Horizontal Pod Autoscaling (HPA)

The Helm chart configures HPA automatically:

```yaml
autoscaling:
  enabled: true
  minReplicas: 2
  maxReplicas: 10
  targetCPUUtilizationPercentage: 70
```

Monitor HPA status:

```bash
kubectl get hpa -n openproxy
kubectl describe hpa openproxy -n openproxy
```

HPA will scale the deployment from 2 to 10 replicas based on CPU usage averaging 70%.

### Logging and Observability

#### Container Logs

Access logs from all replicas:

```bash
# All pods
kubectl logs -f -n openproxy -l app=openproxy --all-containers=true

# Specific pod
kubectl logs -f openproxy-abc123-xyz789 -n openproxy

# Follow in real-time with timestamps
kubectl logs -f openproxy-abc123-xyz789 -n openproxy --timestamps=true
```

#### Metrics

If Prometheus is enabled:

```bash
kubectl port-forward -n openproxy svc/openproxy 8000:8000
curl http://localhost:8000/metrics | grep openproxy
```

#### Ingress and Load Balancing

Configure ingress for external access:

```yaml
ingress:
  enabled: true
  className: nginx
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
  hosts:
    - host: api.example.com
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: openproxy-tls
      hosts:
        - api.example.com
```

Create the issuer:

```yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: ops@example.com
    privateKeySecretRef:
      name: letsencrypt-prod
    solvers:
      - http01:
          ingress:
            class: nginx
```

### Troubleshooting

#### Pod Stuck in Pending

Usually a resource issue or node affinity problem:

```bash
kubectl describe pod <pod-name> -n openproxy
kubectl get nodes --show-labels
```

#### Pod Crashing

Check logs and probe configuration:

```bash
kubectl logs <pod-name> -n openproxy --previous
kubectl describe pod <pod-name> -n openproxy
```

#### Database Connection Errors

Verify the connection string in the secret:

```bash
kubectl get secret openproxy-secrets -n openproxy -o yaml
```

Test database connectivity from a pod:

```bash
kubectl run -it --rm --image=postgres:16 --restart=Never \
  -- psql "postgresql://user:pass@host:5432/db"
```

#### Redis Connection Errors

Test Redis:

```bash
kubectl run -it --rm --image=redis:7 --restart=Never \
  -- redis-cli -h redis-service ping
```

### Uninstalling

```bash
helm uninstall openproxy -n openproxy
kubectl delete namespace openproxy
```

## Environment Variables for Kubernetes

Non-secret variables are stored in a ConfigMap created by the Helm chart. Secret variables (DATABASE_URL, REDIS_URL, API keys) are stored in the existing secret specified in values.yaml.

Example `.env` for Docker Compose or manual Kubernetes setup:

```bash
# Required
APP_ENV=production
DEBUG=false
DATABASE_URL=postgresql://openproxyai:password@postgres:5432/openproxyai
REDIS_URL=redis://redis:6379/0
SECRET_KEY=your-secret-key-minimum-32-characters

# LLM providers (at least one)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Observability (optional)
PROMETHEUS_ENABLED=true
CLICKHOUSE_URL=http://clickhouse:8123/default
LANGFUSE_PUBLIC_KEY=...
LANGFUSE_SECRET_KEY=...

# Policy
POLICY_ENFORCEMENT_MODE=log_only
POLICY_PII_DETECTION_ENABLED=true
PRESIDIO_ENABLED=true
DEFAULT_BUDGET_DAILY_USD=100.00
```

## Health Checks and Readiness

### GET /health

Always returns HTTP 200 (liveness probe). Used by Kubernetes to determine if the process is alive. No database queries.

### GET /ready

Returns HTTP 200 only if:
- Database connection is active
- Redis connection is active
- All scheduler jobs are running

Used by Kubernetes to determine if the pod should receive traffic. Failure removes pod from service endpoints.

```bash
curl http://localhost:8000/ready
# {"ready": true, "database": "connected", "redis": "connected"}
```
