"""Public resume routes: the profile data (and its PDF/DOCX exports) the
public site (phase 5) renders, unauthenticated. Always scoped to whichever
resume is currently marked default — there is no public listing of, or
access to, non-default resumes.

Export logic itself lives in app.services.export_service and is shared
byte-for-byte with the admin per-resume export in app/api/admin.py, per
CLAUDE.md's "one schema, one renderer" architecture principle.
"""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlmodel import Session

from app.db import get_session
from app.models.resume import Resume
from app.schemas.resume import ResumeRead
from app.services import export_service, resume_service

router = APIRouter(prefix="/api/resumes", tags=["public"])


def _get_default_or_404(session: Session) -> Resume:
    resume = resume_service.get_default_resume(session)
    if resume is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No default resume is set")
    return resume


@router.get("/default", response_model=ResumeRead)
def get_default_resume(session: Session = Depends(get_session)) -> Resume:
    return _get_default_or_404(session)


@router.get("/default/export.pdf")
def export_default_resume_pdf(session: Session = Depends(get_session)) -> Response:
    resume = _get_default_or_404(session)
    filename = f"{export_service.slugify_filename(resume.name)}.pdf"
    return Response(
        content=export_service.render_resume_pdf(resume),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/default/export.docx")
def export_default_resume_docx(session: Session = Depends(get_session)) -> Response:
    resume = _get_default_or_404(session)
    filename = f"{export_service.slugify_filename(resume.name)}.docx"
    return Response(
        content=export_service.render_resume_docx(resume),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
