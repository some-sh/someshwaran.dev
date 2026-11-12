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

import logging
import secrets
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.config import get_settings
from app.core.rate_limit import FailureLimiter

logger = logging.getLogger("app.security")

_RECOMMENDED_KEY_LENGTH = 32

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


def warn_if_admin_key_is_weak() -> None:
    """Logs (never the key itself) when the admin key is missing or short.

    A warning, not an error: refusing to start over a short key would lock the
    owner out of their own deployment. A key from
    ``secrets.token_urlsafe(32)`` is 43 characters and cannot be guessed; a
    short or human-chosen one can."""
    key = get_settings().admin_api_key
    if not key:
        logger.warning("APP_ADMIN_API_KEY is not set: every admin and MCP request will be refused.")
    elif len(key) < _RECOMMENDED_KEY_LENGTH:
        logger.warning(
            "APP_ADMIN_API_KEY is only %d characters. Use %d or more random characters, e.g. "
            'python -c "import secrets; print(secrets.token_urlsafe(32))".',
            len(key),
            _RECOMMENDED_KEY_LENGTH,
        )


@lru_cache
def get_auth_limiter() -> FailureLimiter:
    settings = get_settings()
    return FailureLimiter(settings.admin_auth_max_failures, settings.admin_auth_window_seconds)


def client_identity(headers: Mapping[str, str], peer: str | None) -> str:
    """Who to count failed attempts against: the client address as reported by
    the proxy in front of the app (``CF-Connecting-IP``, else the first
    ``X-Forwarded-For`` hop), else the socket peer. Those headers are only as
    trustworthy as the proxy — see app/core/rate_limit.py. ``headers`` must
    have lower-case names (Starlette's request.headers is case-insensitive)."""
    forwarded = headers.get("x-forwarded-for", "").split(",")[0].strip()
    connecting = headers.get("cf-connecting-ip", "").strip()
    return (connecting or forwarded or peer or "unknown")[:64].lower()


@dataclass(frozen=True)
class AuthResult:
    ok: bool
    # Set (and ok is False) when the caller is locked out; seconds to wait.
    retry_after: int | None = None


def authenticate(token: str | None, identity: str) -> AuthResult:
    """The single admin-auth decision, shared by REST and MCP: lockout check,
    then the key check, then failure/success bookkeeping."""
    limiter = get_auth_limiter()
    wait = limiter.retry_after(identity)
    if wait is not None:
        return AuthResult(ok=False, retry_after=wait)
    if is_valid_admin_key(token):
        limiter.clear(identity)
        return AuthResult(ok=True)
    limiter.record_failure(identity)
    return AuthResult(ok=False)


def _locked_out(retry_after: int) -> dict[str, str]:
    return {"Retry-After": str(retry_after)}


def require_admin(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> None:
    """FastAPI dependency guarding admin-only routes."""
    identity = client_identity(request.headers, request.client.host if request.client else None)
    result = authenticate(credentials.credentials, identity)
    if result.retry_after is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed attempts. Try again later.",
            headers=_locked_out(result.retry_after),
        )
    if not result.ok:
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

        client = scope.get("client")
        identity = client_identity(
            {
                name.decode("latin-1").lower(): value.decode("latin-1")
                for name, value in scope["headers"]
            },
            client[0] if client else None,
        )
        result = authenticate(_bearer_token_from_scope(scope), identity)
        if not result.ok:
            if result.retry_after is not None:
                response = JSONResponse(
                    {"detail": "Too many failed attempts. Try again later."},
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    headers=_locked_out(result.retry_after),
                )
            else:
                response = JSONResponse(
                    {"detail": "Invalid or missing API key"},
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    headers={"WWW-Authenticate": "Bearer"},
                )
            await response(scope, receive, send)
            return

        await self._app(scope, receive, send)
