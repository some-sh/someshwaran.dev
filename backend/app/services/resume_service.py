"""CRUD service for resumes.

Phase 2 scope: create/read/update/delete against the data model. Clone
and set-default are admin actions that compose these primitives and
belong to the API layer (phase 4) per CLAUDE.md's phase plan.
"""

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
