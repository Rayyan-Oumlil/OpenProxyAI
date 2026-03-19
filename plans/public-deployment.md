# Plan — Public Deployment (Phase 6.3)

**Objective:** Deploy OpenProxyAI to a public URL with SSL, custom domain, and CI/CD.
**Target:** DigitalOcean Kubernetes (DOKS) — cheapest managed K8s, 1-click cert-manager.
**Created:** 2026-03-19
**Status:** Ready to execute

---

## Context Brief (read this cold)

### What already exists
- `backend/Dockerfile` — multi-stage, non-root, production-ready
- `deploy/helm/openproxy/` — full Helm chart with HPA, PDB, ingress template, ServiceMonitor
- `docker-compose.yml` — local dev only (not used for deployment)
- Admin console: Vite + React, `npm run build` → `dist/` static files

### What's missing
- Frontend Dockerfile (nginx serving `dist/`)
- GitHub Actions CI/CD (build → push → deploy)
- Production `values.yaml` override
- TLS cert-manager setup
- DNS pointing to the cluster

### Domain strategy
```
app.openproxyai.com   → admin console (frontend nginx)
api.openproxyai.com   → FastAPI backend
```
(Or single domain with path-based routing — decided in Step 2)

---

## Dependency Graph

```
Step 1 (Frontend Dockerfile)
Step 2 (Helm values.prod.yaml)        ← parallel with Step 1
  └── Step 3 (GitHub Actions CI/CD)   ← needs Steps 1+2
        └── Step 4 (DOKS cluster + deploy)
              └── Step 5 (DNS + TLS)
```

---

## Step 1 — Frontend Dockerfile

**Branch:** `feat/deploy-frontend-dockerfile`
**Risk:** low — new file, no existing code changed

### Tasks
- [ ] Create `admin-console/Dockerfile`:
  ```dockerfile
  # Stage 1 — build
  FROM node:20-alpine AS builder
  WORKDIR /app
  COPY package*.json ./
  RUN npm ci
  COPY . .
  RUN npm run build

  # Stage 2 — serve
  FROM nginx:1.27-alpine
  COPY --from=builder /app/dist /usr/share/nginx/html
  COPY deploy/nginx/admin-console.conf /etc/nginx/conf.d/default.conf
  EXPOSE 80
  ```

- [ ] Create `deploy/nginx/admin-console.conf`:
  ```nginx
  server {
      listen 80;
      root /usr/share/nginx/html;
      index index.html;

      # SPA fallback — all routes serve index.html
      location / {
          try_files $uri $uri/ /index.html;
      }

      # Cache static assets aggressively (hashed filenames)
      location /assets/ {
          expires 1y;
          add_header Cache-Control "public, immutable";
      }
  }
  ```

- [ ] Add `.dockerignore` to `admin-console/`:
  ```
  node_modules
  dist
  .env*
  ```

- [ ] Add a `frontend` service to `deploy/helm/openproxy/templates/`:
  - `frontend-deployment.yaml` — 2 replicas, nginx container, liveness probe on `/`
  - `frontend-service.yaml` — ClusterIP, port 80
  - Add `frontend.image` to `values.yaml`

### Verification
```bash
cd admin-console && docker build -t openproxyai/frontend:test .
docker run -p 3000:80 openproxyai/frontend:test
# open http://localhost:3000 — should serve the React app
```

### Exit criteria
- Docker image builds in < 3 minutes
- `http://localhost:3000` serves the React app
- `http://localhost:3000/logs` (deep link) works — nginx SPA fallback

---

## Step 2 — Production Helm values

**Branch:** `feat/deploy-helm-prod-values`
**Parallel with:** Step 1

### Tasks
- [ ] Create `deploy/helm/openproxy/values.prod.yaml`:
  ```yaml
  # Backend
  image:
    repository: ghcr.io/rayyan-oumlil/openproxyai-backend
    tag: ""  # overridden by CI with git SHA
  replicaCount: 2

  # Frontend
  frontend:
    image:
      repository: ghcr.io/rayyan-oumlil/openproxyai-frontend
      tag: ""
    replicaCount: 2

  # Ingress — path-based routing on single domain
  ingress:
    enabled: true
    className: nginx
    host: app.openproxyai.com
    tls:
      enabled: true
      secretName: openproxyai-tls
    paths:
      - path: /api
        service: backend
      - path: /
        service: frontend

  # Use external managed DB + Redis (not bundled subcharts)
  postgresql:
    enabled: false
  redis:
    enabled: false

  # External DB + Redis injected via K8s secret
  externalDatabase:
    secretName: openproxyai-secrets
    databaseUrlKey: DATABASE_URL
    redisUrlKey: REDIS_URL
  ```

- [ ] Update `deploy/helm/openproxy/values.yaml` — add `frontend` section with defaults
- [ ] Update `deploy/helm/openproxy/Chart.yaml` — add `kubeVersion: ">=1.28"`

### Verification
```bash
helm template openproxy deploy/helm/openproxy -f deploy/helm/openproxy/values.prod.yaml | grep kind
# Should show: Deployment (×2), Service (×2), Ingress, HPA, PDB, ServiceAccount
```

### Exit criteria
- `helm template` renders without errors
- Ingress routes `/api/*` to backend, `/*` to frontend
- No bundled DB/Redis in prod (managed services used instead)

---

## Step 3 — GitHub Actions CI/CD

**Branch:** `feat/deploy-github-actions`
**Depends on:** Steps 1 + 2

### Tasks
- [ ] Create `.github/workflows/deploy.yml`:

```yaml
name: Build and Deploy

on:
  push:
    branches: [main]

env:
  REGISTRY: ghcr.io
  BACKEND_IMAGE: ghcr.io/${{ github.repository_owner }}/openproxyai-backend
  FRONTEND_IMAGE: ghcr.io/${{ github.repository_owner }}/openproxyai-frontend

jobs:
  build-and-push:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
    steps:
      - uses: actions/checkout@v4

      - name: Log in to GHCR
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Build and push backend
        uses: docker/build-push-action@v5
        with:
          context: ./backend
          push: true
          tags: |
            ${{ env.BACKEND_IMAGE }}:${{ github.sha }}
            ${{ env.BACKEND_IMAGE }}:latest

      - name: Build and push frontend
        uses: docker/build-push-action@v5
        with:
          context: ./admin-console
          push: true
          tags: |
            ${{ env.FRONTEND_IMAGE }}:${{ github.sha }}
            ${{ env.FRONTEND_IMAGE }}:latest

  deploy:
    needs: build-and-push
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install kubectl + helm
        uses: azure/setup-helm@v4

      - name: Set kubeconfig
        run: echo "${{ secrets.KUBECONFIG }}" | base64 -d > /tmp/kubeconfig

      - name: Deploy
        env:
          KUBECONFIG: /tmp/kubeconfig
        run: |
          helm upgrade --install openproxy deploy/helm/openproxy \
            -f deploy/helm/openproxy/values.prod.yaml \
            --set image.tag=${{ github.sha }} \
            --set frontend.image.tag=${{ github.sha }} \
            --namespace openproxy \
            --create-namespace \
            --wait --timeout 5m
```

- [ ] Add GitHub repository secrets:
  - `KUBECONFIG` — base64-encoded kubeconfig from DOKS cluster (see Step 4)

### Exit criteria
- Pushing to `main` triggers the workflow
- Both images push to GHCR
- Helm upgrade runs and waits for rollout
- Failed deploy does NOT mark the workflow as success

---

## Step 4 — DOKS cluster + first deploy

**Depends on:** Step 3

### Manual steps (one-time, done in DigitalOcean console)

1. **Create DOKS cluster:**
   - Region: choose closest to target customers (NYC3 or FRA1)
   - Node pool: 2× `s-2vcpu-4gb` ($48/mo total) — enough for early traffic
   - K8s version: latest stable

2. **Create managed PostgreSQL:**
   - DigitalOcean Managed Postgres (Starter, $15/mo)
   - Create database `openproxyai`, user `openproxyai`
   - Copy connection string → add to K8s secret

3. **Create managed Redis:**
   - DigitalOcean Managed Redis (Starter, $15/mo)
   - Copy connection string → add to K8s secret

4. **Create K8s secrets:**
   ```bash
   kubectl create namespace openproxy
   kubectl create secret generic openproxyai-secrets \
     --namespace openproxy \
     --from-literal=DATABASE_URL="postgresql+asyncpg://..." \
     --from-literal=REDIS_URL="rediss://..." \
     --from-literal=SECRET_KEY="$(openssl rand -hex 32)"
   ```

5. **Install nginx-ingress + cert-manager:**
   ```bash
   helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
   helm install ingress-nginx ingress-nginx/ingress-nginx --namespace ingress-nginx --create-namespace

   helm repo add jetstack https://charts.jetstack.io
   helm install cert-manager jetstack/cert-manager \
     --namespace cert-manager --create-namespace \
     --set installCRDs=true
   ```

6. **Create LetsEncrypt ClusterIssuer:**
   ```yaml
   # deploy/k8s/cluster-issuer.yaml
   apiVersion: cert-manager.io/v1
   kind: ClusterIssuer
   metadata:
     name: letsencrypt-prod
   spec:
     acme:
       server: https://acme-v02.api.letsencrypt.org/directory
       email: rayya@openproxyai.com
       privateKeySecretRef:
         name: letsencrypt-prod
       solvers:
         - http01:
             ingress:
               class: nginx
   ```
   ```bash
   kubectl apply -f deploy/k8s/cluster-issuer.yaml
   ```

7. **Download kubeconfig → encode → add to GitHub secret:**
   ```bash
   cat ~/.kube/config | base64 | pbcopy  # macOS
   # paste into GitHub → Settings → Secrets → KUBECONFIG
   ```

8. **Trigger first deploy:**
   ```bash
   git push origin main  # CI/CD fires
   ```

### Exit criteria
- `kubectl get pods -n openproxy` shows all pods Running
- `kubectl get ingress -n openproxy` shows ADDRESS (load balancer IP)

---

## Step 5 — DNS + TLS

**Depends on:** Step 4 (need the load balancer IP)

### Tasks
- [ ] Get load balancer IP:
  ```bash
  kubectl get svc -n ingress-nginx ingress-nginx-controller -o jsonpath='{.status.loadBalancer.ingress[0].ip}'
  ```
- [ ] Add DNS A records (in your DNS provider, e.g. Cloudflare):
  ```
  app.openproxyai.com  A  <LOAD_BALANCER_IP>
  ```
- [ ] Update ingress in `values.prod.yaml` with `host: app.openproxyai.com`
- [ ] Add cert-manager annotation to ingress template:
  ```yaml
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
  ```
- [ ] Re-deploy via `git push origin main`
- [ ] Wait for certificate: `kubectl get certificate -n openproxy`

### Exit criteria
- `https://app.openproxyai.com` loads the React app with valid TLS
- `https://app.openproxyai.com/api/health` returns `{"status": "ok"}`
- Certificate is valid (not self-signed)

---

## Cost estimate (DigitalOcean)

| Resource | Monthly cost |
|----------|-------------|
| DOKS (2× s-2vcpu-4gb) | $48 |
| Managed PostgreSQL (Starter) | $15 |
| Managed Redis (Starter) | $15 |
| Load balancer | $12 |
| **Total** | **~$90/mo** |

At $2,500/mo Starter plan, first paying customer covers 28 months of infra.

---

## Execution order

```
Day 1: Step 1 + Step 2 in parallel (code changes)
Day 1: Step 3 (GitHub Actions)
Day 2: Step 4 (manual DOKS setup — ~2 hours)
Day 2: Step 5 (DNS + TLS — ~30 min + propagation wait)
```

## Rollback

- Bad deploy: `helm rollback openproxy -n openproxy` — instant
- Bad DNS: revert A record — propagates in seconds (low TTL during setup)
