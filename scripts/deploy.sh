#!/usr/bin/env bash
# Builds the frontend, copies it into backend/frontend_dist/ (see
# app/main.py's app.frontend() mount and backend/.fastapicloudignore),
# then deploys the backend — which now serves the API and the frontend
# from the same origin. Run from anywhere; only step 3 talks to FastAPI
# Cloud, and it uses whatever `fastapi` CLI session is already logged
# in on this machine.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "==> Building frontend"
(cd "$REPO_ROOT/frontend" && npm run build)

echo "==> Copying build into backend/frontend_dist"
rm -rf "$REPO_ROOT/backend/frontend_dist"
cp -r "$REPO_ROOT/frontend/dist" "$REPO_ROOT/backend/frontend_dist"

echo "==> Deploying backend (includes frontend_dist/ — see .fastapicloudignore)"
(cd "$REPO_ROOT/backend" && uv run fastapi deploy)
