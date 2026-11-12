"""Link safety, shared by input validation and every renderer.

Resume fields hold URLs (website, GitHub, LinkedIn, project and certificate
links) that end up as clickable links in a PDF, a DOCX and a web page. Only
http, https and mailto are ever linked; anything else (``javascript:``,
``data:``, ``file:``, ...) must never become a link.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

_LINKABLE_SCHEMES = {"http", "https", "mailto"}
_HAS_SCHEME = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.\-]*:")
_HOST_AND_PORT = re.compile(r"^[^/:\s]+:\d+(/|$)")


def safe_url(value: str | None) -> str | None:
    """The URL if it is safe to emit as a link (http, https or mailto), else
    None. A bare host ("linkedin.com/in/x", "example.com:8080") gets https://.
    Anything that starts with some other scheme — javascript:, data:, file: —
    is shown as text and never linked; note "javascript:alert(1)" has no "//",
    so "has a scheme" is decided by the leading ``name:``, not by "://"."""
    if not value or not value.strip():
        return None
    candidate = value.strip()
    if not _HAS_SCHEME.match(candidate) or _HOST_AND_PORT.match(candidate):
        candidate = f"https://{candidate}"
    parsed = urlparse(candidate)
    scheme = parsed.scheme.lower()
    if scheme not in _LINKABLE_SCHEMES:
        return None
    if scheme == "mailto":
        return candidate if parsed.path else None
    return candidate if parsed.netloc else None


def display_url(value: str) -> str:
    """'https://www.linkedin.com/in/x/' -> 'linkedin.com/in/x'."""
    shown = value.strip()
    for prefix in ("https://", "http://", "mailto:"):
        if shown.lower().startswith(prefix):
            shown = shown[len(prefix) :]
    if shown.lower().startswith("www."):
        shown = shown[4:]
    return shown.rstrip("/")
