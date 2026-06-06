#!/usr/bin/env bash
# Build the victim image once, deploy three Cloud Run services from it.
#
# Required env (or pass via flags):
#   GOOGLE_CLOUD_PROJECT  -> GCP project id
#   GOOGLE_CLOUD_REGION   -> e.g. us-central1
#
# Optional env:
#   REGRESSION_MODE       -> "" | n_plus_one | slow_query | bad_dep | leaky
#   IMAGE_TAG             -> defaults to git short SHA, or "manual" if not a repo
#
# Run from Git Bash / WSL on Windows, or any *nix shell with gcloud installed.
#
# Idempotent: re-running redeploys with the latest image and updates env vars.

set -euo pipefail

: "${GOOGLE_CLOUD_PROJECT:?GOOGLE_CLOUD_PROJECT must be set}"
: "${GOOGLE_CLOUD_REGION:?GOOGLE_CLOUD_REGION must be set}"

REGRESSION_MODE="${REGRESSION_MODE:-}"

if git rev-parse --short HEAD >/dev/null 2>&1; then
  IMAGE_TAG="${IMAGE_TAG:-$(git rev-parse --short HEAD)}"
else
  IMAGE_TAG="${IMAGE_TAG:-manual}"
fi

REPO="faultline"
AR_HOST="${GOOGLE_CLOUD_REGION}-docker.pkg.dev"
IMAGE="${AR_HOST}/${GOOGLE_CLOUD_PROJECT}/${REPO}/victim:${IMAGE_TAG}"

# ---- 1. one-time Artifact Registry repo (no-op if it exists) ---------------
if ! gcloud artifacts repositories describe "${REPO}" \
      --location="${GOOGLE_CLOUD_REGION}" >/dev/null 2>&1; then
  echo ">>> creating Artifact Registry repo ${REPO} in ${GOOGLE_CLOUD_REGION}"
  gcloud artifacts repositories create "${REPO}" \
    --repository-format=docker \
    --location="${GOOGLE_CLOUD_REGION}" \
    --description="Faultline images"
fi

# ---- 2. build + push image with Cloud Build --------------------------------
# Build context = repo root so the Dockerfile can `COPY victim_service ...`.
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
echo ">>> building ${IMAGE} (context=${REPO_ROOT})"
( cd "${REPO_ROOT}" && \
  gcloud builds submit . \
    --config=victim_service/cloudbuild.yaml \
    --substitutions="_IMAGE=${IMAGE}" )

# ---- 3. deploy three Cloud Run services from the same image ----------------
deploy_one() {
  local svc="$1"   # frontend | auth | data
  local extra_env="$2"
  echo ">>> deploying faultline-victim-${svc}"
  gcloud run deploy "faultline-victim-${svc}" \
    --image="${IMAGE}" \
    --region="${GOOGLE_CLOUD_REGION}" \
    --allow-unauthenticated \
    --min-instances=0 \
    --max-instances=2 \
    --memory=256Mi \
    --cpu=1 \
    --set-env-vars="SERVICE_NAME=${svc},GOOGLE_CLOUD_PROJECT=${GOOGLE_CLOUD_PROJECT}${extra_env:+,${extra_env}}"
}

deploy_one data "REGRESSION_MODE=${REGRESSION_MODE}"
deploy_one auth ""

DATA_URL=$(gcloud run services describe faultline-victim-data \
  --region="${GOOGLE_CLOUD_REGION}" --format='value(status.url)')
AUTH_URL=$(gcloud run services describe faultline-victim-auth \
  --region="${GOOGLE_CLOUD_REGION}" --format='value(status.url)')

deploy_one frontend "AUTH_URL=${AUTH_URL},DATA_URL=${DATA_URL}"

FRONTEND_URL=$(gcloud run services describe faultline-victim-frontend \
  --region="${GOOGLE_CLOUD_REGION}" --format='value(status.url)')

echo
echo "Done."
echo "  data:     ${DATA_URL}"
echo "  auth:     ${AUTH_URL}"
echo "  frontend: ${FRONTEND_URL}"
echo
echo "Put this in faultline/.env:"
echo "  VICTIM_SERVICE_URL=${FRONTEND_URL}"
