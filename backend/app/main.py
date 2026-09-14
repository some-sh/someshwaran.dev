"""FastAPI application entrypoint."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.admin import router as admin_router
from app.api.public import router as public_resumes_router
from app.core.config import get_settings

_BACKEND_DIR = Path(__file__).resolve().parents[1]


def _run_migrations() -> None:
    """Applies any pending Alembic migrations against the configured
    database. There's no separate deploy-time migration step yet (that's
    phase 8), so this runs once at process startup instead — the same
    thing a fresh deploy or a first local run would otherwise need done
    manually before the app could serve a single DB-backed route.
    migrations/env.py reads the DB URL from the same app.core.config
    settings the app itself uses, so this always targets the right
    database, and it's a no-op once a database is already at head.
    """
    command.upgrade(Config(str(_BACKEND_DIR / "alembic.ini")), "head")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    _run_migrations()
    yield


app = FastAPI(title="someshwaran.dev API", lifespan=lifespan)
# The frontend (phase 5) is served from its own origin (Vite dev server
# locally; a separate static host once deployed), not this API's — the
# browser needs an explicit allowlist rather than same-origin defaults.
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_allowed_origins_list,
    allow_credentials=False,  # auth is a bearer header, not cookies
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(admin_router)
app.include_router(public_resumes_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    """Liveness probe used by CI, deploy checks, and local smoke tests."""
    return {"status": "ok"}


def _mount_frontend_if_built(app: FastAPI, directory: Path) -> None:
    """Serves the built frontend (frontend/dist, copied to
    backend/frontend_dist by scripts/deploy.sh before `fastapi deploy` —
    see that script and README) as a single-page app at "/". FastAPI's
    own app.frontend() checks real path operations first and falls back
    to index.html only for unmatched GET/HEAD requests, so this can
    never shadow /api/* or /health regardless of where it's registered.

    A no-op when the directory doesn't exist, so the API keeps working
    standalone in local dev, CI, and every existing test — none of which
    build the frontend first.
    """
    if directory.is_dir():
        app.frontend("/", directory=directory, fallback="auto")


_mount_frontend_if_built(app, _BACKEND_DIR / "frontend_dist")
