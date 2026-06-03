#!/usr/bin/env bash
# Build + deploy victim_service to Cloud Run. Phase 1 fills out the real flags.
#
# Usage:
#   GOOGLE_CLOUD_PROJECT=... GOOGLE_CLOUD_REGION=... ./deploy_cloudrun.sh
#
# On Windows: run from Git Bash, WSL, or rewrite as PowerShell in phase 1.

set -euo pipefail

: "${GOOGLE_CLOUD_PROJECT:?GOOGLE_CLOUD_PROJECT must be set}"
: "${GOOGLE_CLOUD_REGION:?GOOGLE_CLOUD_REGION must be set}"

SERVICE_NAME="faultline-victim"
IMAGE="${GOOGLE_CLOUD_REGION}-docker.pkg.dev/${GOOGLE_CLOUD_PROJECT}/faultline/${SERVICE_NAME}:latest"

echo "Phase 0 scaffold — not deploying. Phase 1 will:"
echo "  1. gcloud builds submit --tag ${IMAGE} ."
echo "  2. gcloud run deploy ${SERVICE_NAME} --image ${IMAGE} \\"
echo "       --region ${GOOGLE_CLOUD_REGION} --allow-unauthenticated \\"
echo "       --set-env-vars OTEL_EXPORTER=gcp"
