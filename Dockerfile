# Docker fallback for FastAPI Cloud (CLAUDE.md phase 8: "keep the app
# Docker-friendly regardless, as a fallback if FastAPI Cloud has gaps").
# Builds and serves the exact same app scripts/deploy.sh ships to FastAPI
# Cloud: the frontend build baked into backend/frontend_dist and served
# from the same origin as the API (see app/main.py's app.frontend()).
#
# Build from the repo root:
#   docker build -t someshwaran-dev .
# Run (SQLite is a single file — mount a volume for anything but
# throwaway/local use, or point APP_DATABASE_URL elsewhere):
#   docker run -p 8000:8000 -e APP_ADMIN_API_KEY=... -v app-data:/app/data someshwaran-dev

FROM node:26-slim AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Matches backend/.python-version and CI — one version across dev, CI and this
# image, rather than three to keep in sync. (PyYAML has no 3.15 wheel yet, so uv
# builds it from source here; with no C compiler in -slim it falls back to the
# pure-Python implementation, which is all uvicorn's log config needs.)
FROM python:3.15-slim AS backend
WORKDIR /app

# Pinned (not :latest) so an image rebuild can't silently change the installer.
COPY --from=ghcr.io/astral-sh/uv:0.11.32 /uv /uvx /usr/local/bin/

# Dependencies in their own layer, installed from the lockfile before any
# app code is copied in — an app-code-only change then doesn't invalidate
# (and re-run) the slow dependency install.
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

COPY backend/ ./
RUN uv sync --frozen --no-dev

COPY --from=frontend /frontend/dist ./frontend_dist

# Run unprivileged: a compromise of the app shouldn't be root in the container.
# Only the SQLite directory needs to be writable; mount the volume at /app/data.
RUN useradd --system --uid 10001 --no-create-home app \
    && mkdir -p /app/data \
    && chown app:app /app/data
USER app

ENV PATH="/app/.venv/bin:${PATH}"
EXPOSE 8000
# Liveness only (/health never touches the database); stdlib so no curl is needed.
HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/health', timeout=2)"]
# Alembic migrations run at process startup (app/main.py's lifespan), the
# same as every other environment — no separate migration step needed here.
CMD ["fastapi", "run", "app/main.py"]
