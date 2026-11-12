#!/usr/bin/env bash
# Builds the frontend, copies it into backend/frontend_dist/ (see
# app/main.py's app.frontend() mount and backend/.fastapicloudignore),
# then deploys the backend (from the repo root, see below) — which now serves the API and the frontend
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
# Run from the repo root, not backend/: the FastAPI Cloud app is connected to
# this repository with its app directory set to `backend`, so the CLI expects
# to upload the whole repo and finds `backend/` inside it. Uploading from
# backend/ itself made the remote build look for `backend/backend` and fail
# with "Python setup could not access a required path". `--project` makes uv
# use backend/'s environment (and .python-version) without changing cwd.
(cd "$REPO_ROOT" && uv run --project backend fastapi deploy)
