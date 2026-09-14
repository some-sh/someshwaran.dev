#!/usr/bin/env bash
# Builds the frontend, copies it into backend/frontend_dist/ (see
# app/main.py's app.frontend() mount and backend/.fastapicloudignore),
# then deploys the backend — which now serves the API and the frontend
# from the same origin. Run from anywhere; only step 3 talks to FastAPI
# Cloud. Used both for a manual local deploy (an already-logged-in
# `fastapi` CLI session on this machine — see README's Auth/Deploying
# sections) and by the CI deploy job in .github/workflows/ci.yml (which
# has no login session, so it sets FASTAPI_CLOUD_TOKEN/FASTAPI_CLOUD_APP_ID
# instead — `fastapi deploy` picks either up) — one deploy procedure, not
# a CI-only copy of it that can drift.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "==> Building frontend"
(cd "$REPO_ROOT/frontend" && npm run build)

echo "==> Copying build into backend/frontend_dist"
rm -rf "$REPO_ROOT/backend/frontend_dist"
cp -r "$REPO_ROOT/frontend/dist" "$REPO_ROOT/backend/frontend_dist"

echo "==> Deploying backend (includes frontend_dist/ — see .fastapicloudignore)"
(cd "$REPO_ROOT/backend" && uv run fastapi deploy)
