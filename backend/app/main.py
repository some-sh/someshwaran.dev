"""FastAPI application entrypoint."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi import FastAPI

from app.api.admin import router as admin_router
from app.api.public import router as public_resumes_router

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
app.include_router(admin_router)
app.include_router(public_resumes_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    """Liveness probe used by CI, deploy checks, and local smoke tests."""
    return {"status": "ok"}
