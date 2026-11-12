"""Renders a Resume into downloadable PDF/DOCX bytes.

Per CLAUDE.md's architecture principle, this is the ONLY place resume
content becomes a document: both the public default-resume export and the
admin per-resume export (app/api/public.py, app/api/admin.py) call into the
two functions below, so there is exactly one rendering path per output format
for the whole app — never one copy of the layout per route.

Three layers, so formatting rules live in exactly one place:

1. ``resume_document.build_document`` turns the stored resume into a display
   model (formatted dates, safe links, grouped bullets).
2. A *template* draws that model: ``templates/ats_pdf.py`` and
   ``templates/ats_docx.py``. Templates contain layout only.
3. This module picks the template and exposes the two entry points.

Adding a template means adding its two modules and one name to ``Template``
and the registries below; callers select it with ``?template=``.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Literal

from app.models.resume import Resume
from app.services.resume_document import ResumeDocument, build_document
from app.services.templates import ats_docx, ats_pdf

Template = Literal["ats"]
DEFAULT_TEMPLATE: Template = "ats"

_PDF_TEMPLATES: dict[str, Callable[[ResumeDocument], bytes]] = {"ats": ats_pdf.render}
_DOCX_TEMPLATES: dict[str, Callable[[ResumeDocument], bytes]] = {"ats": ats_docx.render}


def slugify_filename(name: str) -> str:
    """'Backend-focused (copy)' -> 'backend-focused-copy', used as the
    download filename stem for both export formats."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "resume"


def render_resume_pdf(resume: Resume, template: Template = DEFAULT_TEMPLATE) -> bytes:
    return _PDF_TEMPLATES[template](build_document(resume))


def render_resume_docx(resume: Resume, template: Template = DEFAULT_TEMPLATE) -> bytes:
    return _DOCX_TEMPLATES[template](build_document(resume))
