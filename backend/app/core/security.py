"""Admin authentication.

Per CLAUDE.md: one auth mechanism, shared by both the admin web routes and
the MCP server (phase 7) — not two separate systems. This is a personal,
single-admin site, so the mechanism is a single static API key rather than
a full user/password/JWT system: it's issued out of band (see
``.env.example``), passed as ``Authorization: Bearer <key>``, and checked
in constant time to avoid leaking the key through response-timing.

``is_valid_admin_key`` is the one place that check happens. ``require_admin``
(a FastAPI dependency) and ``AdminBearerAuthMiddleware`` (plain ASGI, for the
MCP transport mounted in app/main.py — it doesn't go through FastAPI's
dependency injection) both call it, so there is exactly one comparison to
get right rather than a second, parallel one growing on either surface.
"""

import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.config import get_settings

_bearer_scheme = HTTPBearer(
    auto_error=True,
    description="Admin API key, e.g. 'Bearer <key>'. See .env.example.",
)


def is_valid_admin_key(token: str | None) -> bool:
    """True iff ``token`` matches the configured admin API key.

    False whenever no key is configured (``APP_ADMIN_API_KEY`` unset), so a
    misconfigured deployment fails closed rather than silently accepting
    any bearer token.
    """
    admin_key = get_settings().admin_api_key
    if not admin_key or token is None:
        return False
    return secrets.compare_digest(token, admin_key)


def require_admin(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> None:
    """FastAPI dependency guarding admin-only routes."""
    if not is_valid_admin_key(credentials.credentials):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "Bearer"},
        )


def _bearer_token_from_scope(scope: Scope) -> str | None:
    headers = dict(scope.get("headers") or [])
    raw = headers.get(b"authorization")
    if raw is None:
        return None
    scheme, _, token = raw.decode("latin-1").partition(" ")
    return token if scheme.lower() == "bearer" and token else None


class AdminBearerAuthMiddleware:
    """ASGI middleware gating a mounted sub-app behind the same admin API
    key as ``require_admin``.

    The MCP server (app/mcp_server.py) is a Starlette app mounted with
    ``app.mount(...)`` rather than a set of FastAPI path operations, so it
    can't take a ``Depends(require_admin)`` — there's no FastAPI request
    object at that layer, just a raw ASGI scope. This wraps the mounted app
    directly instead, using the exact same ``is_valid_admin_key`` check.
    """

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        if not is_valid_admin_key(_bearer_token_from_scope(scope)):
            response = JSONResponse(
                {"detail": "Invalid or missing API key"},
                status_code=status.HTTP_401_UNAUTHORIZED,
                headers={"WWW-Authenticate": "Bearer"},
            )
            await response(scope, receive, send)
            return

        await self._app(scope, receive, send)
