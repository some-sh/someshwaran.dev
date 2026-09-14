#!/usr/bin/env bash
# Builds the frontend, wires it into the backend (same mechanism as
# scripts/deploy.sh), and starts the full app against a disposable temp
# SQLite DB. This is what playwright.config.ts's webServer runs before
# the E2E suite — one real process, same as production, not a mocked
# frontend or backend.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DB_FILE="${TMPDIR:-/tmp}/someshwaran-dev-e2e.db"

rm -f "$DB_FILE"

echo "==> Building frontend"
(cd "$REPO_ROOT/frontend" && npm run build)

echo "==> Copying build into backend/frontend_dist"
rm -rf "$REPO_ROOT/backend/frontend_dist"
cp -r "$REPO_ROOT/frontend/dist" "$REPO_ROOT/backend/frontend_dist"

echo "==> Starting the app against a fresh temp DB"
cd "$REPO_ROOT/backend"
export APP_DATABASE_URL="sqlite:///$DB_FILE"
export APP_ADMIN_API_KEY="${E2E_ADMIN_KEY:-e2e-test-key}"
exec uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
