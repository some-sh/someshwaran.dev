"""CRUD service for resumes, plus the admin actions (clone, set-default)
built on top of it. app/api/admin.py and app/api/public.py are the only
callers — no route in this app touches app.models.resume directly."""

from __future__ import annotations

from datetime import datetime

from sqlmodel import Session, col, select

from app.models.resume import (
    Certification,
    Education,
    Experience,
    PersonalInfo,
    Project,
    Resume,
    Skill,
)
from app.schemas.resume import ResumeCreate, ResumeUpdate


def create_resume(session: Session, data: ResumeCreate) -> Resume:
    resume = Resume(
        name=data.name,
        summary=data.summary,
        personal_info=PersonalInfo(**data.personal_info.model_dump()),
        skills=[Skill(**s.model_dump()) for s in data.skills],
        experience=[Experience(**e.model_dump()) for e in data.experience],
        projects=[Project(**p.model_dump()) for p in data.projects],
        education=[Education(**ed.model_dump()) for ed in data.education],
        certifications=[Certification(**c.model_dump()) for c in data.certifications],
    )
    session.add(resume)
    session.commit()
    session.refresh(resume)
    return resume


def get_resume(session: Session, resume_id: int) -> Resume | None:
    return session.get(Resume, resume_id)


def list_resumes(session: Session) -> list[Resume]:
    return list(session.exec(select(Resume).order_by(col(Resume.created_at))).all())


def update_resume(session: Session, resume_id: int, data: ResumeUpdate) -> Resume | None:
    resume = session.get(Resume, resume_id)
    if resume is None:
        return None

    if data.name is not None:
        resume.name = data.name
    if data.summary is not None:
        resume.summary = data.summary
    if data.personal_info is not None:
        info = data.personal_info.model_dump()
        if resume.personal_info is None:
            resume.personal_info = PersonalInfo(**info)
        else:
            for key, value in info.items():
                setattr(resume.personal_info, key, value)
    if data.skills is not None:
        resume.skills = [Skill(**s.model_dump()) for s in data.skills]
    if data.experience is not None:
        resume.experience = [Experience(**e.model_dump()) for e in data.experience]
    if data.projects is not None:
        resume.projects = [Project(**p.model_dump()) for p in data.projects]
    if data.education is not None:
        resume.education = [Education(**ed.model_dump()) for ed in data.education]
    if data.certifications is not None:
        resume.certifications = [Certification(**c.model_dump()) for c in data.certifications]

    resume.updated_at = datetime.utcnow()
    session.add(resume)
    session.commit()
    session.refresh(resume)
    return resume


def delete_resume(session: Session, resume_id: int) -> bool:
    resume = session.get(Resume, resume_id)
    if resume is None:
        return False
    session.delete(resume)
    session.commit()
    return True


def get_default_resume(session: Session) -> Resume | None:
    """The one resume the public site and its exports render. None until
    an admin explicitly calls set_default_resume."""
    return session.exec(select(Resume).where(col(Resume.is_default))).first()


def set_default_resume(session: Session, resume_id: int) -> Resume | None:
    """Marks resume_id as the one default resume, unsetting any previous
    default in the same transaction.

    SQLite has no partial-unique-index equivalent to enforce "at most one
    is_default=True" at the schema level, so the invariant lives here —
    this is the only code path allowed to set is_default=True.
    """
    resume = session.get(Resume, resume_id)
    if resume is None:
        return None

    for other in session.exec(select(Resume).where(col(Resume.is_default))).all():
        other.is_default = False
        session.add(other)

    resume.is_default = True
    session.add(resume)
    session.commit()
    session.refresh(resume)
    return resume


def clone_resume(session: Session, resume_id: int) -> Resume | None:
    """Deep-copies a resume's content (personal info + every nested
    collection) into a new row. The clone is never the default — even
    when cloning the current default — set-default is a separate, explicit
    action."""
    source = session.get(Resume, resume_id)
    if source is None:
        return None

    # Excluding id/resume_id is what makes this a *copy*: keeping either
    # would collide with or reparent the source's own rows instead of
    # creating independent ones.
    _omit = {"id", "resume_id"}
    clone = Resume(
        name=f"{source.name} (copy)",
        summary=source.summary,
        is_default=False,
        personal_info=(
            PersonalInfo(**source.personal_info.model_dump(exclude=_omit))
            if source.personal_info is not None
            else None
        ),
        skills=[Skill(**s.model_dump(exclude=_omit)) for s in source.skills],
        experience=[Experience(**e.model_dump(exclude=_omit)) for e in source.experience],
        projects=[Project(**p.model_dump(exclude=_omit)) for p in source.projects],
        education=[Education(**ed.model_dump(exclude=_omit)) for ed in source.education],
        certifications=[
            Certification(**c.model_dump(exclude=_omit)) for c in source.certifications
        ],
    )
    session.add(clone)
    session.commit()
    session.refresh(clone)
    return clone
