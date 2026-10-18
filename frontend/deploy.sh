#!/bin/bash

set -e

# ============================================================
# AIBC FRONTEND DEPLOYMENT (SECURE EXPRESS BACKEND)
# ============================================================

PROJECT_ID="ai-builder-cup-2026"
SERVICE_NAME="aibc-frontend-secure"
REGION="us-central1"

echo ""
echo "============================================================"
echo " AIBC FRONTEND SECURE DEPLOYMENT"
echo "============================================================"
echo ""

# ------------------------------------------------------------
# 1. Verify required files
# ------------------------------------------------------------

echo "Checking required files..."

REQUIRED_FILES=(
  "package.json"
  "Dockerfile"
  "server.js"
  "cloudbuild.yaml"
)

for FILE in "${REQUIRED_FILES[@]}"; do
  if [ ! -f "$FILE" ]; then
    echo "ERROR: Missing $FILE"
    exit 1
  fi
done

echo "All required files found."
echo ""

# ------------------------------------------------------------
# 2. Set GCP project
# ------------------------------------------------------------

echo "Setting GCP project..."

gcloud config set project "$PROJECT_ID"

echo ""

# ------------------------------------------------------------
# 3. Check Google authentication
# ------------------------------------------------------------

echo "Checking Google Cloud authentication..."

if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
  echo ""
  echo "ERROR: No active Google Cloud account found."
  echo "Run:"
  echo "  gcloud auth login"
  echo ""
  exit 1
fi

echo "Authentication OK."
echo ""

# ------------------------------------------------------------
# 4. Local production build test
# ------------------------------------------------------------

echo "Running local production build..."

npm run build

echo ""
echo "Frontend build successful."
echo ""

# ------------------------------------------------------------
# 5. Submit build to Google Cloud Build
# ------------------------------------------------------------

echo "Starting Cloud Build..."
echo ""

gcloud builds submit \
  --config=cloudbuild.yaml \
  .

echo ""

# ------------------------------------------------------------
# 6. Ensure Cloud Run is publicly accessible
# ------------------------------------------------------------

echo "Configuring Cloud Run public access..."

gcloud run services add-iam-policy-binding "$SERVICE_NAME" \
  --region="$REGION" \
  --member="allUsers" \
  --role="roles/run.invoker" \
  --quiet

echo ""

# ------------------------------------------------------------
# 7. Get deployed URL
# ------------------------------------------------------------

SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" \
  --region="$REGION" \
  --format="value(status.url)")

echo ""
echo "============================================================"
echo " DEPLOYMENT SUCCESSFUL"
echo "============================================================"
echo ""
echo "Service:"
echo "  $SERVICE_NAME"
echo ""
echo "Region:"
echo "  $REGION"
echo ""
echo "URL:"
echo "  $SERVICE_URL"
echo ""
echo "============================================================"
echo ""