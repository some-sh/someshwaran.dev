"""Admin routes: resume CRUD, clone, set-default, and per-resume export.

Every route on this router sits behind require_admin (applied once, at
the router level, in the ``dependencies=`` below) — there is no route
here that skips it. Public access to resume data (the current default
only) lives in app/api/public.py instead.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from sqlmodel import Session

from app.api import exports
from app.core.security import require_admin
from app.db import get_session
from app.models.resume import Resume
from app.schemas.backup import BackupFile, ImportResult
from app.schemas.resume import ResumeCreate, ResumeRead, ResumeSummary, ResumeUpdate
from app.services import backup_service, export_service, resume_service

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/whoami")
def whoami() -> dict[str, bool]:
    """Trivial authenticated route: reaching this handler means the caller
    presented a valid admin API key."""
    return {"authenticated": True}


@router.post("/resumes", response_model=ResumeRead, status_code=status.HTTP_201_CREATED)
def create_resume(data: ResumeCreate, session: Session = Depends(get_session)) -> Resume:
    return resume_service.create_resume(session, data)


@router.get("/resumes", response_model=list[ResumeSummary])
def list_resumes(session: Session = Depends(get_session)) -> list[Resume]:
    return resume_service.list_resumes(session)


@router.get("/resumes/{resume_id}", response_model=ResumeRead)
def get_resume(resume_id: int, session: Session = Depends(get_session)) -> Resume:
    resume = resume_service.get_resume(session, resume_id)
    if resume is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Resume not found")
    return resume


@router.patch("/resumes/{resume_id}", response_model=ResumeRead)
def update_resume(
    resume_id: int, data: ResumeUpdate, session: Session = Depends(get_session)
) -> Resume:
    resume = resume_service.update_resume(session, resume_id, data)
    if resume is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Resume not found")
    return resume


@router.delete("/resumes/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_resume(resume_id: int, session: Session = Depends(get_session)) -> None:
    if not resume_service.delete_resume(session, resume_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Resume not found")


@router.post(
    "/resumes/{resume_id}/clone", response_model=ResumeRead, status_code=status.HTTP_201_CREATED
)
def clone_resume(resume_id: int, session: Session = Depends(get_session)) -> Resume:
    clone = resume_service.clone_resume(session, resume_id)
    if clone is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Resume not found")
    return clone


@router.post("/resumes/{resume_id}/set-default", response_model=ResumeRead)
def set_default_resume(resume_id: int, session: Session = Depends(get_session)) -> Resume:
    resume = resume_service.set_default_resume(session, resume_id)
    if resume is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Resume not found")
    return resume


def _stamp_or_404(session: Session, resume_id: int) -> resume_service.ResumeStamp:
    stamp = resume_service.get_stamp(session, resume_id)
    if stamp is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Resume not found")
    return stamp


@router.get("/resumes/{resume_id}/export.pdf")
def export_resume_pdf(
    resume_id: int,
    request: Request,
    template: export_service.Template = export_service.DEFAULT_TEMPLATE,
    session: Session = Depends(get_session),
) -> Response:
    stamp = _stamp_or_404(session, resume_id)
    return exports.export_response(request, session, stamp, "pdf", template, public=False)


@router.get("/resumes/{resume_id}/export.docx")
def export_resume_docx(
    resume_id: int,
    request: Request,
    template: export_service.Template = export_service.DEFAULT_TEMPLATE,
    session: Session = Depends(get_session),
) -> Response:
    stamp = _stamp_or_404(session, resume_id)
    return exports.export_response(request, session, stamp, "docx", template, public=False)


@router.get("/export")
def export_backup(session: Session = Depends(get_session)) -> JSONResponse:
    """Every resume version in one downloadable JSON backup file."""
    filename = f"someshwaran-backup-{datetime.now(UTC):%Y-%m-%d}.json"
    return JSONResponse(
        backup_service.export_backup(session),
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/import", response_model=ImportResult)
def import_backup(
    backup: BackupFile, replace: bool = False, session: Session = Depends(get_session)
) -> ImportResult:
    """Restore resumes from a backup file, all or nothing.

    Resumes whose name already exists are skipped (so re-running is harmless) and
    the current default is never taken away. ``replace=true`` deletes every
    existing resume first, in the same transaction."""
    return backup_service.import_backup(session, backup, replace=replace)
