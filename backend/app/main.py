"""FastAPI application entrypoint."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi import Depends, FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlmodel import Session
from starlette.types import Receive, Scope, Send

from app.api.admin import router as admin_router
from app.api.public import router as public_resumes_router
from app.core.cache_headers import StaticCacheHeadersMiddleware
from app.core.config import get_settings
from app.core.security import AdminBearerAuthMiddleware, warn_if_admin_key_is_weak
from app.core.security_headers import SecurityHeadersMiddleware
from app.db import get_engine, get_session
from app.mcp_server import build_mcp_asgi_app, build_mcp_server

logger = logging.getLogger("app.main")

_BACKEND_DIR = Path(__file__).resolve().parents[1]

# Arbitrary constant identifying "the schema migration" to pg_advisory_lock.
_MIGRATION_LOCK_KEY = 7_283_001


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
    alembic_config = Config(str(_BACKEND_DIR / "alembic.ini"))
    # The app owns logging; see migrations/env.py.
    alembic_config.attributes["configure_logger"] = False
    engine = get_engine()
    if engine.dialect.name != "postgresql":
        command.upgrade(alembic_config, "head")
        return
    # With Postgres the app can run as several instances that all start (and
    # migrate) at once after a deploy; two concurrent first-time
    # `CREATE TABLE`s would collide. A session-level advisory lock held on its
    # own connection makes the others wait, then find the schema already at
    # head. (SQLite is a single-process file, so it needs none of this.)
    with engine.connect() as lock_connection:
        lock_connection.execute(text("SELECT pg_advisory_lock(:key)"), {"key": _MIGRATION_LOCK_KEY})
        try:
            command.upgrade(alembic_config, "head")
        finally:
            lock_connection.execute(
                text("SELECT pg_advisory_unlock(:key)"), {"key": _MIGRATION_LOCK_KEY}
            )


class _MCPDispatch:
    """Forwards each request to whichever MCP ASGI app app.state.mcp_asgi_app
    currently holds.

    app.mount(...) below bakes in a fixed ASGI callable at mount time (this
    object), but the *actual* MCP server + ASGI app underneath it is
    rebuilt fresh on every lifespan startup (see app/mcp_server.py's
    docstring for why) — so the mount needs this indirection to always
    reach the current one instead of a stale reference to the previous
    startup's, which would be running a session manager that already
    shut down.
    """

    def __init__(self, app: FastAPI) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        await self._app.state.mcp_asgi_app(scope, receive, send)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    warn_if_admin_key_is_weak()
    _run_migrations()
    mcp_server = build_mcp_server()
    app.state.mcp_asgi_app = build_mcp_asgi_app(mcp_server)
    # A mounted sub-app's own lifespan never runs (Starlette doesn't nest
    # lifespans under Mount) — the session manager has to be entered here
    # instead, or the MCP server's first request fails. See
    # app/mcp_server.py and the SDK's docs/run/asgi.md.
    async with mcp_server.session_manager.run():
        yield


_docs_enabled = get_settings().enable_docs
app = FastAPI(
    title="someshwaran.dev API",
    lifespan=lifespan,
    docs_url="/docs" if _docs_enabled else None,
    redoc_url="/redoc" if _docs_enabled else None,
    openapi_url="/openapi.json" if _docs_enabled else None,
)
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
app.add_middleware(StaticCacheHeadersMiddleware)
# Added last so it is the outermost layer: it covers every response, including
# CORS preflights and the 401s the auth layers return.
app.add_middleware(SecurityHeadersMiddleware)
app.include_router(admin_router)
app.include_router(public_resumes_router)
# Same admin API key as every other admin route (see AdminBearerAuthMiddleware
# and app/mcp_server.py's docstring for why that check happens here, at the
# ASGI layer, rather than through FastAPI's Depends(require_admin)).
app.mount("/api/mcp", AdminBearerAuthMiddleware(_MCPDispatch(app)))


_FRONTEND_DIR = _BACKEND_DIR / "frontend_dist"


@app.get("/health")
def health_check() -> dict[str, str | bool]:
    """Liveness probe used by CI, deploy checks, and local smoke tests.

    Also reports whether the built frontend was found and mounted, and
    where it was looked for: a deploy can succeed while silently shipping
    without frontend_dist/ (it is a gitignored build output), and this
    makes that visible with a plain curl instead of needing platform logs.
    """
    return {
        "status": "ok",
        "frontend_mounted": _FRONTEND_DIR.is_dir(),
        "frontend_dir": str(_FRONTEND_DIR),
    }


@app.get("/health/ready")
def readiness(response: Response, session: Session = Depends(get_session)) -> dict[str, str]:
    """Readiness probe: can this instance actually serve requests, i.e. reach
    its database? ``/health`` only says the process is alive; during a database
    outage it would keep reporting "ok" while every resume request failed.
    Returns 503 when the database cannot be queried. The reason is logged, not
    returned: this endpoint is public."""
    try:
        session.exec(text("SELECT 1"))  # type: ignore[call-overload]
    except Exception:
        logger.exception("Readiness check failed: database unreachable")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "unavailable", "database": "unreachable"}
    return {"status": "ok", "database": "ok"}


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


_mount_frontend_if_built(app, _FRONTEND_DIR)
