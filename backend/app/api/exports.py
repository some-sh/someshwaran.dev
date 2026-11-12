"""The one place an export request becomes an HTTP response, shared by the
public routes (app/api/public.py) and the admin ones (app/api/admin.py).

Public responses are cacheable-with-revalidation: ``ETag`` plus
``Cache-Control: no-cache``, so a repeat request costs one narrow query and a
``304``. Admin responses stay ``no-store`` (admin data must never sit in a
browser or shared cache) but still use the server-side render cache.
"""

from __future__ import annotations

from typing import Literal

from fastapi import HTTPException, Request, Response, status
from sqlmodel import Session

from app.models.resume import Resume
from app.schemas.resume import ResumeRead
from app.services import export_service, resume_service
from app.services.response_cache import etag_for, matches, render_cache
from app.services.resume_service import ResumeStamp

PUBLIC_CACHE_CONTROL = "public, no-cache"

_MEDIA_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def _load(session: Session, resume_id: int) -> Resume:
    resume = resume_service.get_resume(session, resume_id)
    if resume is None:  # deleted between the stamp query and now
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Resume not found")
    return resume


def _not_modified(headers: dict[str, str]) -> Response:
    return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=headers)


def json_response(request: Request, session: Session, stamp: ResumeStamp) -> Response:
    etag = etag_for("json", stamp)
    headers = {"ETag": etag, "Cache-Control": PUBLIC_CACHE_CONTROL}
    if matches(request.headers.get("if-none-match"), etag):
        return _not_modified(headers)
    body = render_cache.get_or_render(
        etag,
        lambda: ResumeRead.model_validate(_load(session, stamp.id)).model_dump_json().encode(),
    )
    return Response(content=body, media_type="application/json", headers=headers)


def export_response(
    request: Request,
    session: Session,
    stamp: ResumeStamp,
    fmt: Literal["pdf", "docx"],
    template: export_service.Template,
    *,
    public: bool,
) -> Response:
    etag = etag_for(fmt, stamp, template)
    headers: dict[str, str] = {}
    if public:
        headers = {"ETag": etag, "Cache-Control": PUBLIC_CACHE_CONTROL}
        if matches(request.headers.get("if-none-match"), etag):
            return _not_modified(headers)

    def render() -> bytes:
        resume = _load(session, stamp.id)
        if fmt == "pdf":
            return export_service.render_resume_pdf(resume, template)
        return export_service.render_resume_docx(resume, template)

    content = render_cache.get_or_render(etag, render)
    filename = f"{export_service.slugify_filename(stamp.name)}.{fmt}"
    headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return Response(content=content, media_type=_MEDIA_TYPES[fmt], headers=headers)
