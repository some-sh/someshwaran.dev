"""Export every resume to a backup document, and import one back.

Why this exists: a resume lives in exactly one database, and its content once
vanished with it. A backup is a plain file the owner can keep anywhere, restore
into an empty database in one request, or hand-edit and diff.

Import is all-or-nothing (one transaction) and deliberately conservative:

* A resume whose *name* already exists is skipped, not overwritten, so running
  the same import twice is harmless.
* It never takes the default away from the current default resume. A backup's
  default is applied only when the database has none (or after ``replace``).
* ``replace`` deletes every existing resume first, in the same transaction, so a
  failed import leaves everything exactly as it was.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlmodel import Session, select

from app.models.resume import Resume
from app.schemas.backup import BACKUP_FORMAT, BACKUP_VERSION, BackupFile, ImportResult
from app.schemas.resume import ResumeCreate, ResumeRead
from app.services import resume_service

# Keys the database assigns; not part of a backup (they would collide on restore).
_DB_ASSIGNED = {"id", "created_at", "updated_at"}


def _strip(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _strip(item) for key, item in value.items() if key not in _DB_ASSIGNED}
    if isinstance(value, list):
        return [_strip(item) for item in value]
    return value


def export_backup(session: Session) -> dict[str, Any]:
    resumes = session.exec(select(Resume).order_by(Resume.id)).all()  # type: ignore[arg-type]
    return {
        "format": BACKUP_FORMAT,
        "version": BACKUP_VERSION,
        "exported_at": datetime.now(UTC).isoformat(),
        "resumes": [
            _strip(ResumeRead.model_validate(resume).model_dump(mode="json")) for resume in resumes
        ],
    }


def import_backup(session: Session, backup: BackupFile, *, replace: bool) -> ImportResult:
    resume_service.lock_default_changes(session)

    if replace:
        for existing in session.exec(select(Resume)).all():
            session.delete(existing)
        session.flush()
        names: set[str] = set()
        had_default = False
    else:
        names = {name for name in session.exec(select(Resume.name)).all()}
        had_default = resume_service.get_default_stamp(session) is not None

    created: list[Resume] = []
    wants_default: Resume | None = None
    skipped: list[str] = []
    for item in backup.resumes:
        if item.name in names:
            skipped.append(item.name)
            continue
        names.add(item.name)
        resume = resume_service.build_resume(ResumeCreate.model_validate(item.model_dump()))
        session.add(resume)
        created.append(resume)
        if item.is_default and wants_default is None:
            wants_default = resume

    session.flush()  # assigns ids
    if wants_default is not None and not had_default:
        wants_default.is_default = True
    session.commit()

    default = resume_service.get_default_stamp(session)
    return ImportResult(
        created=[resume.id for resume in created if resume.id is not None],
        skipped=skipped,
        default_id=default.id if default else None,
    )
