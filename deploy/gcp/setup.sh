#!/usr/bin/env bash
# =============================================================================
# OpenProxyAI — GCP one-time setup script
# Run this ONCE from your local machine to provision all infrastructure.
#
# Prerequisites:
#   1. Install gcloud CLI: https://cloud.google.com/sdk/docs/install
#   2. Run: gcloud auth login
#   3. Fill in the variables below
# =============================================================================
set -euo pipefail

# =============================================================================
# CONFIGURE THESE
# =============================================================================
PROJECT_ID="${GCP_PROJECT_ID:-project-ebccbe1a-a432-4e88-887}"
REGION="${GCP_REGION:-northamerica-northeast1}"
# Generated at runtime — never hardcode secrets in this file
DB_PASSWORD="${DB_PASSWORD:-$(python3 -c "import secrets; print(secrets.token_hex(16))" 2>/dev/null || python -c "import secrets; print(secrets.token_hex(16))")}"
SECRET_KEY="${SECRET_KEY:-$(python3 -c "import secrets; print(secrets.token_hex(32))" 2>/dev/null || python -c "import secrets; print(secrets.token_hex(32))")}"

# These stay as-is
APP_NAME="openproxyai"
DB_INSTANCE="openproxyai-db"
DB_NAME="openproxyai"
DB_USER="openproxyai"
REDIS_INSTANCE="openproxyai-redis"
AR_REPO="openproxyai"
CLOUD_RUN_SERVICE="openproxyai-backend"
# =============================================================================

echo "▶ Setting project to $PROJECT_ID"
gcloud config set project "$PROJECT_ID"

# ── Enable required APIs ──────────────────────────────────────────────────────
echo "▶ Enabling GCP APIs..."
gcloud services enable \
  run.googleapis.com \
  sqladmin.googleapis.com \
  redis.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  secretmanager.googleapis.com \
  vpcaccess.googleapis.com \
  servicenetworking.googleapis.com \
  --quiet

# ── Artifact Registry (Docker images) ────────────────────────────────────────
echo "▶ Creating Artifact Registry repository..."
gcloud artifacts repositories create "$AR_REPO" \
  --repository-format=docker \
  --location="$REGION" \
  --description="OpenProxyAI Docker images" \
  --quiet 2>/dev/null || echo "  (already exists, skipping)"

echo "▶ Setting Artifact Registry cleanup policy (keep last 2 images)..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if gcloud artifacts repositories set-cleanup-policies "$AR_REPO" \
  --project="$PROJECT_ID" \
  --location="$REGION" \
  --policy="${SCRIPT_DIR}/artifact-registry-cleanup-policy.json" \
  --no-dry-run \
  --quiet; then
  echo "  ✓ Cleanup policy applied"
else
  echo "  ⚠ Run manually: gcloud artifacts repositories set-cleanup-policies $AR_REPO --project=$PROJECT_ID --location=$REGION --policy=${SCRIPT_DIR}/artifact-registry-cleanup-policy.json --no-dry-run"
fi

# ── Cloud SQL — PostgreSQL 15 ─────────────────────────────────────────────────
echo "▶ Creating Cloud SQL instance (this takes ~5 minutes)..."
gcloud sql instances create "$DB_INSTANCE" \
  --database-version=POSTGRES_15 \
  --tier=db-f1-micro \
  --region="$REGION" \
  --storage-size=10GB \
  --storage-type=SSD \
  --backup \
  --backup-start-time=03:00 \
  --deletion-protection \
  --quiet 2>/dev/null || echo "  (already exists, skipping)"

echo "▶ Creating database and user..."
gcloud sql databases create "$DB_NAME" --instance="$DB_INSTANCE" --quiet 2>/dev/null || true
gcloud sql users create "$DB_USER" \
  --instance="$DB_INSTANCE" \
  --password="$DB_PASSWORD" \
  --quiet 2>/dev/null || true

# ── Set postgres superuser password (used by migration job for CREATE EXTENSION)
echo "▶ Setting postgres superuser password..."
POSTGRES_PASSWORD=$(python3 -c "import secrets; print(secrets.token_hex(16))" 2>/dev/null || python -c "import secrets; print(secrets.token_hex(16))")
gcloud sql users set-password postgres \
  --instance="$DB_INSTANCE" \
  --password="$POSTGRES_PASSWORD" \
  --quiet

# Get Cloud SQL connection name
DB_CONNECTION_NAME=$(gcloud sql instances describe "$DB_INSTANCE" --format="value(connectionName)")
echo "  Cloud SQL connection name: $DB_CONNECTION_NAME"

# ── Memorystore Redis ─────────────────────────────────────────────────────────
echo "▶ Creating Memorystore Redis instance (this takes ~5 minutes)..."
gcloud redis instances create "$REDIS_INSTANCE" \
  --size=1 \
  --region="$REGION" \
  --tier=basic \
  --quiet 2>/dev/null || echo "  (already exists, skipping)"

REDIS_HOST=$(gcloud redis instances describe "$REDIS_INSTANCE" \
  --region="$REGION" \
  --format="value(host)")
echo "  Redis host: $REDIS_HOST"

# ── VPC Connector (needed for Cloud Run → Memorystore) ───────────────────────
echo "▶ Creating VPC connector..."
gcloud compute networks vpc-access connectors create openproxyai-connector \
  --region="$REGION" \
  --range=10.8.0.0/28 \
  --min-instances=1 \
  --max-instances=3 \
  --quiet 2>/dev/null || echo "  (already exists, skipping)"

# ── Service Account for Cloud Run ────────────────────────────────────────────
echo "▶ Creating service account..."
SA_EMAIL="${APP_NAME}-run@${PROJECT_ID}.iam.gserviceaccount.com"
gcloud iam service-accounts create "${APP_NAME}-run" \
  --display-name="OpenProxyAI Cloud Run" \
  --quiet 2>/dev/null || echo "  (already exists, skipping)"

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/cloudsql.client" --quiet
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/artifactregistry.reader" --quiet

# ── GitHub Actions Service Account ───────────────────────────────────────────
echo "▶ Creating GitHub Actions service account..."
GH_SA_EMAIL="github-actions@${PROJECT_ID}.iam.gserviceaccount.com"
gcloud iam service-accounts create "github-actions" \
  --display-name="GitHub Actions CI/CD" \
  --quiet 2>/dev/null || echo "  (already exists, skipping)"

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:$GH_SA_EMAIL" \
  --role="roles/run.admin" --quiet
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:$GH_SA_EMAIL" \
  --role="roles/artifactregistry.writer" --quiet
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:$GH_SA_EMAIL" \
  --role="roles/iam.serviceAccountUser" --quiet

# Auth uses Workload Identity Federation (no JSON key needed).
# To set up WIF, run:
#   gcloud iam workload-identity-pools create github-actions-pool --location=global
#   gcloud iam workload-identity-pools providers create-oidc github \
#     --workload-identity-pool=github-actions-pool --location=global \
#     --issuer-uri=https://token.actions.githubusercontent.com \
#     --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
#     --attribute-condition="assertion.repository=='YOUR_ORG/YOUR_REPO'"
#   gcloud iam service-accounts add-iam-policy-binding $GH_SA_EMAIL \
#     --role=roles/iam.workloadIdentityUser \
#     --member="principalSet://iam.googleapis.com/projects/PROJECT_NUM/locations/global/workloadIdentityPools/github-actions-pool/attribute.repository/YOUR_ORG/YOUR_REPO"

# ── Print summary ─────────────────────────────────────────────────────────────
AR_IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}/backend"
DATABASE_URL="postgresql+asyncpg://${DB_USER}:${DB_PASSWORD}@/${DB_NAME}?host=/cloudsql/${DB_CONNECTION_NAME}"
# Migrations run as postgres (superuser) so CREATE EXTENSION IF NOT EXISTS vector works
MIGRATION_DATABASE_URL="postgresql+asyncpg://postgres:${POSTGRES_PASSWORD}@/${DB_NAME}?host=/cloudsql/${DB_CONNECTION_NAME}"
REDIS_URL="redis://${REDIS_HOST}:6379/0"

echo ""
echo "============================================================"
echo "  SETUP COMPLETE — add these as GitHub repository secrets"
echo "============================================================"
echo ""
echo "GCP_REGION=$REGION"
echo "GCP_AR_IMAGE=$AR_IMAGE"
echo "GCP_CLOUD_RUN_SERVICE=$CLOUD_RUN_SERVICE"
echo "GCP_DB_CONNECTION_NAME=$DB_CONNECTION_NAME"
echo "GCP_VPC_CONNECTOR=projects/${PROJECT_ID}/locations/${REGION}/connectors/openproxyai-connector"
echo ""
echo "DATABASE_URL=$DATABASE_URL"
echo "MIGRATION_DATABASE_URL=$MIGRATION_DATABASE_URL"
echo "REDIS_URL=$REDIS_URL"
echo "SECRET_KEY=$SECRET_KEY"
echo ""
echo "⚠  SAVE THESE VALUES — they are generated at runtime and not stored."
echo "   Add them as GitHub repository secrets (Settings → Secrets → Actions)."
echo "   See deploy/gcp/env.template for the full list."
echo "============================================================"
