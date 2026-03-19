# Plan — Public Deployment (Phase 6.3)

**Objective:** Deploy OpenProxyAI to a public URL with SSL, custom domain, and CI/CD.
**Target:** DigitalOcean Kubernetes (DOKS)
**Status:** Code complete — waiting on manual infra setup

---

## What's already shipped (2026-03-19)

| File | What it does |
|------|-------------|
| `admin-console/Dockerfile` | Multi-stage build: node:20-alpine → nginx:1.27-alpine |
| `admin-console/nginx.conf` | SPA fallback, asset caching, `/nginx-health` probe |
| `deploy/helm/openproxy/templates/frontend-deployment.yaml` | nginx Deployment (conditional on `frontend.enabled`) |
| `deploy/helm/openproxy/templates/frontend-service.yaml` | ClusterIP Service for frontend |
| `deploy/helm/openproxy/templates/ingress.yaml` | Path-based: `/api` + `/health` → backend, `/` → frontend; cert-manager TLS |
| `deploy/helm/openproxy/values.prod.yaml` | Production overrides (GHCR images, managed DB/Redis, HPA 3-15 replicas) |
| `deploy/k8s/cluster-issuer.yaml` | cert-manager Let's Encrypt HTTP-01 ClusterIssuer |
| `.github/workflows/deploy.yml` | test → build+push GHCR → helm upgrade pipeline |

CI/CD fires on every push to `main`. Images pushed to `ghcr.io/rayyan-oumlil/openproxyai/{backend,frontend}:<sha>`.

---

## Remaining manual steps (do when ready to go live)

### Step 1 — Create DOKS cluster (~30 min, DigitalOcean console)

1. Create cluster: region NYC3 or FRA1, node pool 2× `s-2vcpu-4gb` ($48/mo)
2. Create **Managed PostgreSQL** (Starter, $15/mo) — database `openproxyai`, user `openproxyai`
3. Create **Managed Redis** (Starter, $15/mo)

### Step 2 — Bootstrap cluster (~20 min, terminal)

```bash
# Download kubeconfig from DO console, then:

# Install nginx-ingress
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm install ingress-nginx ingress-nginx/ingress-nginx --namespace ingress-nginx --create-namespace

# Install cert-manager
helm repo add jetstack https://charts.jetstack.io
helm install cert-manager jetstack/cert-manager \
  --namespace cert-manager --create-namespace \
  --set installCRDs=true

# Apply ClusterIssuer
kubectl apply -f deploy/k8s/cluster-issuer.yaml

# Create app secret
kubectl create namespace openproxyai
kubectl create secret generic openproxy-app-secret \
  --namespace openproxyai \
  --from-literal=DATABASE_URL="postgresql+asyncpg://openproxyai:<password>@<host>:25060/openproxyai?sslmode=require" \
  --from-literal=REDIS_URL="rediss://:<password>@<host>:25061" \
  --from-literal=SECRET_KEY="$(openssl rand -hex 32)"
```

### Step 3 — Add GitHub secret

```bash
cat ~/.kube/config | base64
# Paste output into: GitHub repo → Settings → Environments → production → Secrets → KUBECONFIG
```

### Step 4 — First deploy

```bash
git push origin main  # triggers CI/CD — watch the Actions tab
```

### Step 5 — DNS + TLS (~5 min + propagation)

```bash
# Get load balancer IP
kubectl get svc -n ingress-nginx ingress-nginx-controller \
  -o jsonpath='{.status.loadBalancer.ingress[0].ip}'
```

Add DNS A record in your domain registrar:
```
app.openproxyai.com  A  <LOAD_BALANCER_IP>  TTL 300
```

Wait for cert: `kubectl get certificate -n openproxyai --watch`

---

## Done when

- `https://app.openproxyai.com` loads the React app
- `https://app.openproxyai.com/api/health` returns `{"status": "ok"}`
- Certificate is valid (Let's Encrypt, not self-signed)

---

## Cost (DigitalOcean)

| Resource | Monthly |
|----------|---------|
| DOKS (2× s-2vcpu-4gb) | $48 |
| Managed PostgreSQL Starter | $15 |
| Managed Redis Starter | $15 |
| Load balancer | $12 |
| **Total** | **~$90/mo** |

First Starter customer ($2,500/mo) covers 28 months of infra.

## Rollback

Bad deploy: `helm rollback openproxyai --namespace openproxyai`
