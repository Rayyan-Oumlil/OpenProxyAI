# Plan: Complete GCP Cloud Run Deployment for OpenProxyAI

**Created:** 2026-03-19
**Objective:** Get OpenProxyAI backend live on GCP Cloud Run with automated CI/CD
**Mode:** Direct (operational deployment, no feature branches)
**Invariant:** No secrets ever appear in source code or git history

---

## Infrastructure Status (verified)

| Resource | Type | Status | Value |
|---|---|---|---|
| Cloud SQL | PostgreSQL 15, db-f1-micro | RUNNABLE | `openproxyai-db` |
| Redis | Memorystore Basic 1GB | READY | `10.135.4.115` |
| VPC Connector | Cloud Run → Redis | READY | `openproxyai-connector` |
| Artifact Registry | Docker repo | EXISTS | `openproxyai` |
| WIF Pool | GitHub Actions OIDC | ACTIVE | `github-actions-pool` |
| SA (deploy) | GitHub Actions CI/CD | EXISTS | `github-actions@...` |
| SA (runtime) | Cloud Run service | EXISTS | `openproxyai-run@...` |
| GitHub Secrets | Repository secrets | **0 SET** | needs all secrets |

---

## Step 1: Security Scan — Audit Git History for Leaked Secrets

**Agent:** `security-engineer`
**Depends on:** none
**Can run parallel with:** Step 4

### Context Brief
Commit `8e214ae` contained hardcoded `DB_PASSWORD` and `SECRET_KEY` in `deploy/gcp/setup.sh`. GitGuardian flagged both. Credentials were rotated in commit `29e5094`, but the old values remain in git history. This step verifies:
1. No secrets remain in current tracked files
2. The leaked credentials were actually rotated (old values don't work)
3. No other files contain hardcoded credentials

### Tasks
- [ ] `grep -rn` across the repo for patterns: hex strings >30 chars near password/key/secret variables
- [ ] Verify `deploy/gcp/setup.sh` generates secrets at runtime (uses `${VAR:-$(python ...)}` pattern)
- [ ] Verify `deploy/gcp/env.template` contains only placeholders, no real values
- [ ] Verify `.gitignore` includes `github-actions-key.json` and `*.env`
- [ ] Check for any `.env` files that shouldn't be tracked

### Verification
```bash
# No hardcoded hex secrets in tracked files
git grep -E '(PASSWORD|SECRET_KEY|API_KEY)\s*=\s*"[a-f0-9]{16,}"' -- ':(exclude)*.md'
# Should return 0 results

# .gitignore covers sensitive files
grep -q 'github-actions-key.json' .gitignore && echo "OK" || echo "MISSING"
```

### Exit Criteria
- Zero hardcoded secrets in any tracked file
- `.gitignore` covers `*.env`, `*-key.json`
- PASS/FAIL — if FAIL, fix before proceeding to Step 5

---

## Step 2: Set Postgres Password and Rotate App DB Password

**Agent:** `cloud-architect`
**Depends on:** none (but must complete before Step 3)

### Context Brief
Two database passwords are needed:
1. `openproxyai` user password — used by the running app (`DATABASE_URL`)
2. `postgres` superuser password — used by migration job (`MIGRATION_DATABASE_URL`) for `CREATE EXTENSION`

The `openproxyai` user password was rotated after the GitGuardian incident. The postgres password was set during setup.sh but the value wasn't captured. Both must be re-generated fresh at execution time.

### Tasks
- [ ] Generate a fresh postgres password: `python -c "import secrets; print(secrets.token_hex(16))"`
- [ ] Set it: `gcloud sql users set-password postgres --instance=openproxyai-db --password=<generated>`
- [ ] Verify the `openproxyai` user password is the rotated one (test login via Cloud SQL Proxy if possible, or just confirm via `gcloud sql users list`)
- [ ] Capture both passwords as shell variables for Step 3

### Tasks
- [ ] Generate fresh DB password: `python -c "import secrets; print(secrets.token_hex(16))"`
- [ ] Set it: `gcloud sql users set-password openproxyai --instance=openproxyai-db --password=<generated>`
- [ ] Generate fresh postgres password: `python -c "import secrets; print(secrets.token_hex(16))"`
- [ ] Set it: `gcloud sql users set-password postgres --instance=openproxyai-db --password=<generated>`
- [ ] Capture values as shell variables — NEVER write to any file

### Output Variables (passed to Step 3 — all queried live, never hardcoded)
```bash
DB_PASSWORD=<generated above — in shell variable only>
POSTGRES_PASSWORD=<generated above — in shell variable only>
DB_CONNECTION_NAME=$(gcloud sql instances describe openproxyai-db --format="value(connectionName)")
REDIS_HOST=$(gcloud redis instances describe openproxyai-redis --region=northamerica-northeast1 --format="value(host)")
```

### Exit Criteria
- Both passwords are set in Cloud SQL
- Values are captured (not written to any file)

---

## Step 3: Set All GitHub Repository Secrets via `gh secret set`

**Agent:** `devops-engineer`
**Depends on:** Step 2 (needs password values)

### Context Brief
Zero GitHub secrets are currently set. The deploy.yml pipeline requires these secrets to authenticate to GCP, connect to databases, and configure the app. All values must come from live `gcloud` queries or generated at runtime — never hardcoded.

### Tasks

**GCP Infrastructure Secrets:**
- [ ] `gh secret set GCP_REGION -b "northamerica-northeast1"`
- [ ] `gh secret set GCP_AR_IMAGE -b "northamerica-northeast1-docker.pkg.dev/project-ebccbe1a-a432-4e88-887/openproxyai/backend"`
- [ ] `gh secret set GCP_CLOUD_RUN_SERVICE -b "openproxyai-backend"`
- [ ] `gh secret set GCP_DB_CONNECTION_NAME` (from `gcloud sql instances describe`)
- [ ] `gh secret set GCP_VPC_CONNECTOR` (full resource path)
- [ ] `gh secret set GCP_WORKLOAD_IDENTITY_PROVIDER -b "projects/922337014925/locations/global/workloadIdentityPools/github-actions-pool/providers/github"`
- [ ] `gh secret set GCP_SERVICE_ACCOUNT -b "github-actions@PROJECT_ID.iam.gserviceaccount.com"`
- [ ] `gh secret set GCP_RUNTIME_SERVICE_ACCOUNT -b "openproxyai-run@PROJECT_ID.iam.gserviceaccount.com"`

**Database & App Secrets:**
- [ ] `gh secret set DATABASE_URL` (using openproxyai user + DB_PASSWORD from Step 2, via Cloud SQL socket)
- [ ] `gh secret set MIGRATION_DATABASE_URL` (using postgres user + POSTGRES_PASSWORD from Step 2)
- [ ] `gh secret set REDIS_URL` (from `gcloud redis instances describe` — never hardcode the IP)
- [ ] `gh secret set SECRET_KEY` (generate fresh: `python -c "import secrets; print(secrets.token_hex(32))"`)
- [ ] `gh secret set CORS_ORIGINS` (set to Cloud Run URL after first deploy, or `["*"]` initially — tighten in Step 6)

**Optional Secrets (empty placeholders to prevent deploy.yml errors):**
- [ ] `gh secret set STRIPE_SECRET_KEY -b ""`
- [ ] `gh secret set STRIPE_PUBLISHABLE_KEY -b ""`
- [ ] `gh secret set STRIPE_WEBHOOK_SECRET -b ""`
- [ ] `gh secret set STRIPE_STARTER_PRICE_ID -b ""`
- [ ] `gh secret set STRIPE_GROWTH_PRICE_ID -b ""`
- [ ] `gh secret set STRIPE_METERED_PRICE_ID -b ""`
- [ ] `gh secret set STRIPE_SUCCESS_URL -b ""`
- [ ] `gh secret set STRIPE_CANCEL_URL -b ""`
- [ ] `gh secret set OPENAI_API_KEY -b ""`
- [ ] `gh secret set ANTHROPIC_API_KEY -b ""`
- [ ] `gh secret set LANGFUSE_SECRET_KEY -b ""`
- [ ] `gh secret set LANGFUSE_PUBLIC_KEY -b ""`
- [ ] `gh secret set STRIPE_METERED_BASE_PRICE_ID -b ""`

### Verification
```bash
# Count secrets — should be 27
gh secret list | wc -l
# Should output: 25
```

### Exit Criteria
- `gh secret list` shows all 25 secrets
- No secret value appears in terminal history or any file

---

## Step 4: Validate deploy.yml Configuration

**Agent:** `devops-engineer`
**Depends on:** none
**Can run parallel with:** Step 1

### Context Brief
The deploy.yml was rewritten from DOKS/Kubernetes to GCP Cloud Run. It uses Workload Identity Federation (not JSON keys). This step validates correctness before triggering a real deploy.

### Tasks
- [ ] Verify `permissions.id-token: write` is present (required for WIF)
- [ ] Verify all 3 auth steps use `workload_identity_provider` + `service_account` (not `credentials_json`)
- [ ] Verify migrate job uses `MIGRATION_DATABASE_URL` (not `DATABASE_URL`)
- [ ] Verify deploy job uses `DATABASE_URL` (not `MIGRATION_DATABASE_URL`)
- [ ] Verify deploy job sets `--service-account` flag (Cloud Run runtime identity)
- [ ] Verify test job uses `-m "not integration"` (no real DB in CI)
- [ ] Verify image tag uses `${GITHUB_SHA::8}` (deterministic, traceable)
- [ ] Check for any remaining references to `GCP_SA_KEY` or `credentials_json`

### Verification
```bash
# No JSON key references
grep -c "credentials_json\|GCP_SA_KEY" .github/workflows/deploy.yml
# Should output: 0

# WIF auth present
grep -c "workload_identity_provider" .github/workflows/deploy.yml
# Should output: 3 (build, migrate, deploy jobs)

# id-token permission
grep -c "id-token: write" .github/workflows/deploy.yml
# Should output: 1
```

### Exit Criteria
- All checks pass
- No references to JSON key auth pattern

---

## Step 5: Trigger Deployment

**Agent:** `devops-engineer`
**Depends on:** Steps 1, 3, 4 (all must pass)
**GATE:** Do not proceed if any prior step failed

### Context Brief
With all secrets set and deploy.yml validated, trigger the GitHub Actions pipeline. Prefer `gh workflow run` (no code change needed) over a no-op commit.

### Tasks
- [ ] Trigger: `gh workflow run "Build & Deploy" --ref main`
- [ ] Capture run ID: `gh run list --workflow=deploy.yml --limit=1 --json databaseId -q '.[0].databaseId'`
- [ ] Stream logs: `gh run watch <run_id>`

### Rollback
If the deploy fails:
1. Check which job failed (`gh run view <run_id>`)
2. Read job logs (`gh run view <run_id> --log-failed`)
3. Fix the issue and re-trigger (do NOT force-push or revert infrastructure)

### Exit Criteria
- All 4 jobs pass: test, build, migrate, deploy
- Cloud Run service is deployed

---

## Step 6: Verify Live Service

**Agent:** `devops-engineer` or `sre-engineer`
**Depends on:** Step 5

### Context Brief
After deployment, verify the Cloud Run service is actually responding. Get the URL from gcloud and hit the health endpoint.

### Tasks
- [ ] Get URL: `gcloud run services describe openproxyai-backend --region=northamerica-northeast1 --format="value(status.url)"`
- [ ] Hit health endpoint: `curl -s <URL>/health | jq .`
- [ ] Verify response includes `status: ok` or similar
- [ ] Check Cloud Run logs for startup errors: `gcloud run services logs read openproxyai-backend --region=northamerica-northeast1 --limit=20`

### Exit Criteria
- `/health` returns 200 with valid JSON
- No crash loops in Cloud Run logs
- Service is publicly accessible

---

## Execution Summary

| Step | Agent | Parallel? | Effort |
|---|---|---|---|
| 1. Security scan | security-engineer | Yes (with 4) | 2 min |
| 2. Set DB passwords | cloud-architect | No | 1 min |
| 3. Set GitHub secrets | devops-engineer | No (after 2) | 3 min |
| 4. Validate deploy.yml | devops-engineer | Yes (with 1) | 1 min |
| 5. Trigger deploy | devops-engineer | No (gate) | 5-10 min |
| 6. Verify live | sre-engineer | No | 1 min |

**Total estimated time:** ~15-20 minutes (most is waiting for CI/CD)

**Execution command:** Tell Claude: "Execute the deployment plan at `plans/openproxyai-deploy.md`, starting from Step 1"
