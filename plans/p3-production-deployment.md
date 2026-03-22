# P3 Production Deployment Plan — OpenProxyAI

Step-by-step production deployment plan for OpenProxyAI on GCP Cloud Run with Vercel admin console. Each step is self-contained with context, verification commands, and exit criteria.

---

## Dependency Graph

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              PARALLEL (can run in any order)                         │
├─────────────────────────────────────────────────────────────────────────────────────┤
│  1. Pre-flight   │  2. GCP Infrastructure  │  3. GitHub Secrets  │  4. WIF Setup   │
└────────┬─────────┴────────────┬─────────────┴──────────┬──────────┴────────┬─────────┘
         │                     │                        │                   │
         ▼                     ▼                        ▼                   ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│  5. Admin Console Deploy (Vercel) — can run after secrets; before or parallel to 6 │
└─────────────────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│  6. Backend Deploy (GitHub Actions) — requires 1–4 complete                          │
└─────────────────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│  7. Post-Deploy Verification                                                        │
└─────────────────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│  8. Optional: Custom Domain, Stripe Webhook, Monitoring, Rollout                    │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

**Critical path:** 1 → 2 → 3 → 4 → 6 → 7. Steps 5 (admin console) can run after 3; Stripe webhook (8) must run after 6 when backend URL is known.

---

## 1. Pre-flight

**Context:** Validate local environment, GCP project, gcloud auth, and GitHub repo access before any provisioning.

| Task | Verification | Exit criteria |
|------|--------------|--------------|
| GCP project exists | `gcloud projects describe PROJECT_ID` | Returns project details |
| gcloud authenticated | `gcloud auth list` | Active account shown |
| Application default creds | `gcloud auth application-default login` | Creds configured |
| GitHub repo access | `gh repo view OWNER/REPO` or web UI | Can read repo |
| Python 3.11+ available | `python --version` | 3.11 or 3.12 |

### Commands

```bash
# Set project
export PROJECT_ID="your-gcp-project-id"
gcloud config set project "$PROJECT_ID"

# Verify
gcloud projects describe "$PROJECT_ID" --format="value(projectId)"
gcloud auth list
gcloud auth application-default login
```

---

## 2. GCP Infrastructure

**Context:** Run `deploy/gcp/setup.sh` once to provision Cloud SQL, Memorystore Redis, VPC connector, Artifact Registry, and service accounts. If resources already exist, the script skips creation.

| Resource | Name | Purpose |
|----------|------|---------|
| Cloud SQL | `openproxyai-db` | PostgreSQL 15 |
| Redis | `openproxyai-redis` | Cache, rate limiting |
| VPC Connector | `openproxyai-connector` | Cloud Run → Redis |
| Artifact Registry | `openproxyai` | Docker images |
| SA: Cloud Run | `openproxyai-run@PROJECT.iam.gserviceaccount.com` | Runtime identity |
| SA: GitHub Actions | `github-actions@PROJECT.iam.gserviceaccount.com` | CI/CD identity |

### Commands

```bash
cd deploy/gcp
# Optional: override region/password
# export GCP_REGION=northamerica-northeast1
# export DB_PASSWORD=$(openssl rand -hex 16)
./setup.sh
```

### Verification

```bash
gcloud sql instances describe openproxyai-db --format="value(connectionName)"
gcloud redis instances describe openproxyai-redis --region=$GCP_REGION --format="value(host)"
gcloud compute networks vpc-access connectors describe openproxyai-connector --region=$GCP_REGION
gcloud artifacts repositories describe openproxyai --location=$GCP_REGION
```

### Exit criteria

- Script prints summary with `DATABASE_URL`, `MIGRATION_DATABASE_URL`, `REDIS_URL`, `SECRET_KEY`
- **Save these values** — they are not stored. Add to GitHub secrets per step 3.

**Note:** The setup script applies an Artifact Registry cleanup policy from `deploy/gcp/artifact-registry-cleanup-policy.json` (keep last 2 images). If this file is missing, the step is skipped. The deploy workflow’s cleanup step has `continue-on-error: true`, so deploy still succeeds.

---

## 3. GitHub Secrets

**Context:** The deploy workflow passes ~25 env vars to Cloud Run. `deploy/gcp/env.template` lists 40+ variables. This checklist aligns both.

### Required for deploy workflow (`.github/workflows/deploy.yml`)

| Secret | Source | Notes |
|--------|--------|-------|
| `GCP_REGION` | setup.sh output | e.g. `northamerica-northeast1` |
| `GCP_AR_IMAGE` | setup.sh output | `REGION-docker.pkg.dev/PROJECT/openproxyai/backend` |
| `GCP_CLOUD_RUN_SERVICE` | Fixed | `openproxyai-backend` |
| `GCP_DB_CONNECTION_NAME` | setup.sh output | `PROJECT:REGION:openproxyai-db` |
| `GCP_VPC_CONNECTOR` | setup.sh output | `projects/PROJECT/locations/REGION/connectors/openproxyai-connector` |
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | Step 4 | Full WIF provider resource name |
| `GCP_SERVICE_ACCOUNT` | Fixed | `github-actions@PROJECT.iam.gserviceaccount.com` |
| `GCP_RUNTIME_SERVICE_ACCOUNT` | Fixed | `openproxyai-run@PROJECT.iam.gserviceaccount.com` |
| `DATABASE_URL` | setup.sh output | PostgreSQL URL for app user |
| `MIGRATION_DATABASE_URL` | setup.sh output | PostgreSQL URL for postgres (superuser) |
| `REDIS_URL` | setup.sh output | `redis://HOST:6379/0` |
| `SECRET_KEY` | setup.sh output | Min 32 chars; `openssl rand -hex 32` |
| `CORS_ORIGINS` | **You define** | JSON array: `["https://your-app.vercel.app","https://app.example.com"]` |

### Stripe (required if billing enabled)

| Secret | Value |
|--------|-------|
| `STRIPE_SECRET_KEY` | `sk_live_...` or `sk_test_...` |
| `STRIPE_PUBLISHABLE_KEY` | `pk_live_...` or `pk_test_...` |
| `STRIPE_WEBHOOK_SECRET` | `whsec_...` (create webhook **after** backend URL known) |
| `STRIPE_STARTER_PRICE_ID` | `price_...` |
| `STRIPE_GROWTH_PRICE_ID` | `price_...` |
| `STRIPE_METERED_PRICE_ID` | `price_...` (optional, metered plans) |
| `STRIPE_SUCCESS_URL` | `https://YOUR_VERCEL_URL/billing?success=1` |
| `STRIPE_CANCEL_URL` | `https://YOUR_VERCEL_URL/billing?canceled=1` |

### Optional (deploy workflow passes these if set)

| Secret | Default / Notes |
|--------|-----------------|
| `OPENAI_API_KEY` | Org keys via dashboard; empty ok |
| `ANTHROPIC_API_KEY` | Same |
| `LANGFUSE_SECRET_KEY` | Observability |
| `LANGFUSE_PUBLIC_KEY` | Observability |
| `PROMETHEUS_ENABLED` | `true` (hardcoded in workflow) |

### Gaps: Not in deploy workflow today

These are in `env.template` and `config.py` but **not** passed by `deploy.yml`. Add to deploy workflow or set via Secret Manager + Cloud Run env:

| Variable | Purpose | Action |
|----------|---------|--------|
| `APP_BASE_URL` | SSO redirect_uri validation | Add `--set-env-vars="APP_BASE_URL=https://api.example.com"` |
| `FRONTEND_BASE_URL` | SSO post-auth redirect | Add `--set-env-vars="FRONTEND_BASE_URL=https://app.example.com"` |
| `STRIPE_METERED_BASE_PRICE_ID` | Optional metered base | Add if using metered |
| `TRUSTED_PROXY` | X-Forwarded-For trust | `false` unless behind trusted proxy |
| `LANGFUSE_HOST` | Langfuse server | Default `https://cloud.langfuse.com` |

### Verification

```bash
gh secret list
# Or: GitHub → Settings → Secrets and variables → Actions
```

### Exit criteria

- All required secrets set
- `CORS_ORIGINS` includes your Vercel URL (and custom domain when added)
- If using Stripe: webhook secret can be added after first backend deploy (step 6)

---

## 4. Workload Identity Federation (WIF)

**Context:** WIF allows GitHub Actions to authenticate to GCP without storing a JSON key. Setup is manual; commands are from `deploy/gcp/setup.sh` comments.

### Exact gcloud commands

Replace `YOUR_ORG/YOUR_REPO` with your GitHub org/repo (e.g. `myorg/OpenProxyAI`).

```bash
# 1. Get project number
PROJECT_NUM=$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)")

# 2. Create workload identity pool
gcloud iam workload-identity-pools create github-actions-pool \
  --location=global \
  --display-name="GitHub Actions"

# 3. Create OIDC provider
gcloud iam workload-identity-pools providers create-oidc github \
  --workload-identity-pool=github-actions-pool \
  --location=global \
  --display-name="GitHub" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
  --attribute-condition="assertion.repository=='YOUR_ORG/YOUR_REPO'"

# 4. Allow GitHub Actions from this repo to impersonate the service account
gcloud iam service-accounts add-iam-policy-binding \
  github-actions@${PROJECT_ID}.iam.gserviceaccount.com \
  --role=roles/iam.workloadIdentityUser \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUM}/locations/global/workloadIdentityPools/github-actions-pool/attribute.repository/YOUR_ORG/YOUR_REPO"
```

### Get WIF provider for GitHub secret

```bash
gcloud iam workload-identity-pools providers describe github \
  --workload-identity-pool=github-actions-pool \
  --location=global \
  --format="value(name)"
```

Use the full resource name (e.g. `projects/123456789/locations/global/workloadIdentityPools/github-actions-pool/providers/github`) as `GCP_WORKLOAD_IDENTITY_PROVIDER`.

### Verification

```bash
# Trigger deploy workflow manually
gh workflow run "Build & Deploy" --ref main
gh run watch
```

### Exit criteria

- Build job authenticates without errors
- No "could not find default credentials" or permission denied

---

## 5. Admin Console Deploy (Vercel)

**Context:** The admin console is a React/Vite app with `vercel.json`. It is not part of the main deploy workflow. Deploy via Vercel CLI or Git integration.

### Vercel environment variable

| Variable | Value |
|----------|-------|
| `VITE_API_BASE_URL` | Your Cloud Run URL (e.g. `https://openproxyai-backend-xxx-xx.a.run.app`) |

Set in Vercel Dashboard → Project → Settings → Environment Variables for Production.

### Deploy options

**A. Vercel Git integration (recommended)**

1. Import repo in [Vercel](https://vercel.com/new)
2. Root directory: `admin-console`
3. Build command: `npm run build` (from vercel.json)
4. Output directory: `dist`
5. Add `VITE_API_BASE_URL` as env var
6. Deploy on push to main (or configure branch)

**B. Vercel CLI**

```bash
cd admin-console
npx vercel --prod
# When prompted, set VITE_API_BASE_URL via dashboard or:
# vercel env add VITE_API_BASE_URL production
```

### Verification

```bash
curl -s -o /dev/null -w "%{http_code}" https://YOUR_VERCEL_URL
# Expect 200
```

### Exit criteria

- Admin console loads
- Login/register works (calls backend `/api/v1/auth/...`)
- Update `CORS_ORIGINS` in GitHub secrets to include Vercel URL

### Dependency note

You need the backend URL for `VITE_API_BASE_URL`. Options:
- Deploy backend first (step 6), get URL, then deploy admin console
- Or use a placeholder Cloud Run URL if you’ve deployed before; update after

---

## 6. Backend Deploy

**Context:** Triggered on push to `main` or via `workflow_dispatch`. Jobs: test → build → migrate → deploy.

### Trigger

```bash
git push origin main
# Or manual:
gh workflow run "Build & Deploy" -f environment=production
gh run watch
```

### What runs

1. **test** — pytest in backend with Postgres/Redis services
2. **build** — Docker build, push to Artifact Registry
3. **migrate** — Cloud Run job runs `alembic upgrade head`
4. **deploy** — Cloud Run service updated with new image + env vars

### Verification

```bash
# After deploy completes
URL=$(gcloud run services describe openproxyai-backend \
  --region=$GCP_REGION --format="value(status.url)")
echo "Backend URL: $URL"
```

### Exit criteria

- All jobs pass
- Backend URL returned
- Ready for step 7 (post-deploy verification)

---

## 7. Post-Deploy Verification

**Context:** Validate health, auth, proxy, and Stripe webhook (if enabled).

### Health

```bash
BACKEND_URL="https://your-cloud-run-url.a.run.app"
curl -s "$BACKEND_URL/health" | jq .
# Expect: {"status":"healthy","app":"OpenProxyAI","version":"0.1.0"}

curl -s "$BACKEND_URL/ready" | jq .
# Expect: {"status":"ready","postgres":"ok","redis":"ok"}
```

### Auth

```bash
# Register (or use existing user)
curl -s -X POST "$BACKEND_URL/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"SecurePass123!","org_name":"Test Org"}' | jq .
# Expect token or 200
```

### Proxy call

```bash
# Create API key via dashboard, then:
curl -s -X POST "$BACKEND_URL/v1/chat/completions" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"openai/gpt-4o-mini","messages":[{"role":"user","content":"Hi"}]}' | jq .
# Expect chat completion or appropriate error
```

### Stripe webhook (if enabled)

1. Stripe Dashboard → Developers → Webhooks → Add endpoint
2. URL: `https://YOUR_BACKEND_URL/api/v1/billing/webhook`
3. Events: `checkout.session.completed`, `invoice.paid`, `invoice.payment_failed`, `customer.subscription.updated`, `customer.subscription.deleted`
4. Copy signing secret → add as `STRIPE_WEBHOOK_SECRET` in GitHub secrets
5. Redeploy backend (or update Cloud Run env) to pick up secret
6. Test: create checkout from admin console billing page; use Stripe test card `4242 4242 4242 4242` if in test mode

### Exit criteria

- `/health` and `/ready` return OK
- Auth flows work
- Proxy returns completion (or expected error if no provider keys)
- Stripe webhook receives events (check Stripe Dashboard → Webhooks → Recent deliveries)

---

## 8. Optional Enhancements

### Custom domain for Cloud Run

```bash
# Map custom domain to Cloud Run service
gcloud run domain-mappings create \
  --service=openproxyai-backend \
  --domain=api.example.com \
  --region=$GCP_REGION
# Follow DNS instructions in output
```

Update `APP_BASE_URL`, `CORS_ORIGINS`, and Stripe webhook URL to use `https://api.example.com`.

### Custom domain for Vercel

Vercel Dashboard → Project → Settings → Domains → Add. Update `FRONTEND_BASE_URL` and `CORS_ORIGINS`.

### Prometheus / GCP observability

- Backend exposes `GET /metrics` when `PROMETHEUS_ENABLED=true` (default)
- Cloud Run does not scrape Prometheus by default. Options:
  - **GCP Managed Service for Prometheus**: Use [Collector config](https://cloud.google.com/stackdriver/docs/managed-prometheus/exporters) to scrape `/metrics`
  - **Cloud Monitoring**: Use custom metrics or log-based metrics
  - **GCP Observability MCP**: If project has `project-0-OpenProxyAI-gcp-observability`, use for dashboard/alerts

### Rollout strategy

- **Blue/green**: Deploy new revision, run `gcloud run services update-traffic` to shift traffic
- **Canary**: Use `--tag` for new revision, route a fraction of traffic
- **Rollback**: `gcloud run services update-traffic openproxyai-backend --to-revisions=PREVIOUS=100`

---

## Rollback Notes

| Scenario | Action |
|----------|--------|
| Bad backend deploy | `gcloud run services update-traffic openproxyai-backend --to-revisions=REVISION_NAME=100` or deploy previous commit |
| Bad migration | Fix migration locally, revert commit, re-run workflow (migrations are forward-only; may require manual SQL) |
| Admin console broken | Revert Vercel deployment or redeploy previous commit |
| Secrets wrong | Update GitHub secrets, re-run workflow; or update Cloud Run env directly: `gcloud run services update openproxyai-backend --set-env-vars=...` |
| WIF misconfigured | Re-run step 4 commands with correct repo; verify `attribute.repository` matches exactly |

---

## Quick Reference

| Item | Value |
|------|-------|
| Backend health | `GET /health` |
| Backend readiness | `GET /ready` |
| Stripe webhook path | `POST /api/v1/billing/webhook` |
| Prometheus metrics | `GET /metrics` |
| Admin console API base | `VITE_API_BASE_URL` → backend URL |
| SSO callback | `{APP_BASE_URL}/api/v1/auth/sso/callback` |

---

*Last updated: 2026-03-21*
