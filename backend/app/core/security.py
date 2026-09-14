"""Admin authentication.

Per CLAUDE.md: one auth mechanism, shared by both the admin web routes and
the MCP server (phase 7) — not two separate systems. This is a personal,
single-admin site, so the mechanism is a single static API key rather than
a full user/password/JWT system: it's issued out of band (see
``.env.example``), passed as ``Authorization: Bearer <key>``, and checked
in constant time to avoid leaking the key through response-timing.

``require_admin`` is the one dependency every admin route (phase 4+) and
every MCP tool (phase 7) should depend on — resist the temptation to grow
a second, parallel check for either surface.
"""

import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_settings

_bearer_scheme = HTTPBearer(
    auto_error=True,
    description="Admin API key, e.g. 'Bearer <key>'. See .env.example.",
)


def require_admin(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> None:
    """FastAPI dependency guarding admin-only routes.

    Raises 401 when no key is configured (``APP_ADMIN_API_KEY`` unset) or
    the presented key doesn't match, so a misconfigured deployment fails
    closed rather than silently accepting any bearer token.
    """
    settings = get_settings()
    if not settings.admin_api_key or not secrets.compare_digest(
        credentials.credentials, settings.admin_api_key
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
