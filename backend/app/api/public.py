"""Public resume routes: the profile data (and its PDF/DOCX exports) the
public site (phase 5) renders, unauthenticated. Always scoped to whichever
resume is currently marked default — there is no public listing of, or
access to, non-default resumes.

Export logic itself lives in app.services.export_service and is shared
byte-for-byte with the admin per-resume export in app/api/admin.py, per
CLAUDE.md's "one schema, one renderer" architecture principle.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlmodel import Session

from app.api import exports
from app.db import get_session
from app.schemas.resume import ResumeRead
from app.services import export_service, resume_service
from app.services.resume_service import ResumeStamp

router = APIRouter(prefix="/api/resumes", tags=["public"])


def _default_stamp_or_404(session: Session) -> ResumeStamp:
    stamp = resume_service.get_default_stamp(session)
    if stamp is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No default resume is set")
    return stamp


@router.get("/default", response_model=ResumeRead)
def get_default_resume(request: Request, session: Session = Depends(get_session)) -> Response:
    return exports.json_response(request, session, _default_stamp_or_404(session))


@router.get("/default/export.pdf")
def export_default_resume_pdf(
    request: Request,
    template: export_service.Template = export_service.DEFAULT_TEMPLATE,
    session: Session = Depends(get_session),
) -> Response:
    stamp = _default_stamp_or_404(session)
    return exports.export_response(request, session, stamp, "pdf", template, public=True)


@router.get("/default/export.docx")
def export_default_resume_docx(
    request: Request,
    template: export_service.Template = export_service.DEFAULT_TEMPLATE,
    session: Session = Depends(get_session),
) -> Response:
    stamp = _default_stamp_or_404(session)
    return exports.export_response(request, session, stamp, "docx", template, public=True)
