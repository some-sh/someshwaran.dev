"""Cache headers for the static frontend.

Vite writes build output to ``/assets/`` with a content hash in every file name
(``index-B3tB1VH7.js``), so a given URL can never change: browsers may keep it
for a year and never revalidate. ``index.html`` is the opposite — it names the
current hashed files, so it must be revalidated on every load, or a deploy would
not reach visitors until their cache expired (and could point at files that no
longer exist).

Only fills in a header the response does not already have, and only for
successful responses, so errors are never cached.
"""

from __future__ import annotations

from starlette.types import ASGIApp, Message, Receive, Scope, Send

IMMUTABLE = "public, max-age=31536000, immutable"
REVALIDATE = "no-cache"


class StaticCacheHeadersMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        path: str = scope.get("path", "")

        async def send_with_cache_headers(message: Message) -> None:
            if message["type"] == "http.response.start" and message["status"] == 200:
                headers = list(message["headers"])
                names = {name.lower() for name, _ in headers}
                if b"cache-control" not in names:
                    content_type = dict(headers).get(b"content-type", b"").lower()
                    if path.startswith("/assets/"):
                        headers.append((b"cache-control", IMMUTABLE.encode()))
                    elif content_type.startswith(b"text/html") and not path.startswith("/api/"):
                        headers.append((b"cache-control", REVALIDATE.encode()))
                message["headers"] = headers
            await send(message)

        await self._app(scope, receive, send_with_cache_headers)
