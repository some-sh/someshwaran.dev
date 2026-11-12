"""Conditional-request and render caching for the public resume endpoints.

Every public response is a pure function of one resume *version* (see
resume_service.ResumeStamp) plus the code that renders it. So:

* The ETag is a hash of the version and a fingerprint of the rendering code,
  and the endpoints send ``Cache-Control: no-cache`` (cache it, but revalidate
  every time). A revalidation costs one narrow query and a ``304`` with no body;
  an edit is visible on the very next request, never after a cache timeout.
* Rendered bytes (JSON, PDF, DOCX) are kept in a small in-process LRU keyed by
  the same version, so a miss on the browser side still skips the nested-section
  queries and the rendering.

Nothing here can serve stale content: a new version has a new key, and the
fingerprint changes whenever the code that produces the bytes does.
"""

from __future__ import annotations

import hashlib
import threading
from collections import OrderedDict
from collections.abc import Callable
from pathlib import Path

from app.services.resume_service import ResumeStamp

# Hash of the source files that decide what a rendered response looks like. A
# deploy that changes a template (or the display model, or a schema) changes
# every ETag, so clients revalidate instead of keeping output from the old code.
_RENDERING_SOURCES = (
    "services/resume_document.py",
    "services/templates/ats_pdf.py",
    "services/templates/ats_docx.py",
    "schemas/resume.py",
)


def _fingerprint() -> str:
    root = Path(__file__).resolve().parents[1]
    digest = hashlib.sha256()
    for relative in _RENDERING_SOURCES:
        digest.update((root / relative).read_bytes())
    return digest.hexdigest()[:16]


RENDER_FINGERPRINT = _fingerprint()


def etag_for(kind: str, stamp: ResumeStamp, *extra: str) -> str:
    """A strong ETag (quoted, per RFC 9110) for one rendering of one version."""
    raw = "|".join([kind, str(stamp.id), stamp.updated_at.isoformat(), RENDER_FINGERPRINT, *extra])
    return '"' + hashlib.sha256(raw.encode()).hexdigest()[:32] + '"'


def matches(if_none_match: str | None, etag: str) -> bool:
    """True if the client's ``If-None-Match`` already has this ETag (or ``*``).
    Weak validators (``W/"..."``) compare equal for GET, per RFC 9110."""
    if not if_none_match:
        return False
    candidates = [part.strip().removeprefix("W/") for part in if_none_match.split(",")]
    return "*" in candidates or etag in candidates


class RenderCache:
    """A small thread-safe LRU of rendered bytes."""

    def __init__(self, max_entries: int = 32) -> None:
        self._max = max_entries
        self._items: OrderedDict[str, bytes] = OrderedDict()
        self._lock = threading.Lock()

    def get_or_render(self, key: str, render: Callable[[], bytes]) -> bytes:
        with self._lock:
            cached = self._items.get(key)
            if cached is not None:
                self._items.move_to_end(key)
                return cached
        rendered = render()  # outside the lock: rendering can take tens of ms
        with self._lock:
            self._items[key] = rendered
            self._items.move_to_end(key)
            while len(self._items) > self._max:
                self._items.popitem(last=False)
        return rendered

    def clear(self) -> None:
        with self._lock:
            self._items.clear()


render_cache = RenderCache()
