"""Security headers on every response.

The site is one origin serving a static React app plus a JSON API, so a strict
policy is practical: scripts and styles only from this origin, no framing, no
plugins, forms and fetches only to this origin. That also limits what a script
injected through some future bug could do with the admin API key, which the
admin UI keeps in localStorage.

Pure ASGI (not BaseHTTPMiddleware) so it adds no per-request overhead and does
not interfere with streaming responses such as the MCP transport.
"""

from __future__ import annotations

from starlette.types import ASGIApp, Message, Receive, Scope, Send

CONTENT_SECURITY_POLICY = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self'",
        "img-src 'self' data:",
        "font-src 'self'",
        "connect-src 'self'",
        "object-src 'none'",
        "base-uri 'none'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    ]
)

# Fixed headers added to every response (unless a handler already set one).
_STATIC_HEADERS: dict[str, str] = {
    "x-content-type-options": "nosniff",
    # frame-ancestors in the CSP is the modern control; this covers old browsers.
    "x-frame-options": "DENY",
    "referrer-policy": "strict-origin-when-cross-origin",
    "permissions-policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
    "cross-origin-opener-policy": "same-origin",
}

# 6 months. No includeSubDomains/preload: this app does not own the parent
# domain, so it must not make promises about it.
_HSTS = "max-age=15552000"

# Swagger UI / ReDoc load scripts from a CDN, which the CSP above (rightly)
# forbids. They are off by default; when switched on for local development
# these paths get no CSP rather than a broken page.
_DOCS_PATHS = ("/docs", "/redoc", "/openapi.json")

# Admin data, exports and the MCP transport must never be stored by a browser
# or shared cache.
_NO_STORE_PREFIXES = ("/api/admin", "/api/mcp")


def _is_https(scope: Scope) -> bool:
    if scope.get("scheme") == "https":
        return True
    forwarded = dict(scope.get("headers") or []).get(b"x-forwarded-proto", b"")
    return bool(forwarded.split(b",")[0].strip().lower() == b"https")


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        path: str = scope.get("path", "")
        https = _is_https(scope)

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                present = {name.lower() for name, _ in message["headers"]}
                headers = list(message["headers"])

                def add(name: str, value: str) -> None:
                    if name.encode() not in present:
                        headers.append((name.encode(), value.encode()))

                for name, value in _STATIC_HEADERS.items():
                    add(name, value)
                if not path.startswith(_DOCS_PATHS):
                    add("content-security-policy", CONTENT_SECURITY_POLICY)
                if https:
                    add("strict-transport-security", _HSTS)
                if path.startswith(_NO_STORE_PREFIXES):
                    add("cache-control", "no-store")
                message["headers"] = headers
            await send(message)

        await self._app(scope, receive, send_with_headers)
