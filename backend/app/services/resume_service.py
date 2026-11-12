"""CRUD service for resumes, plus the admin actions (clone, set-default)
built on top of it. app/api/admin.py and app/api/public.py are the only
callers — no route in this app touches app.models.resume directly."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TypeVar

from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, col, select

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

_M = TypeVar("_M", bound=SQLModel)


def _positioned(model: type[_M], items: Sequence[BaseModel]) -> list[_M]:
    """Builds ``model`` rows from input items, recording each one's position.

    Every list section is rendered in ``order_index`` order, so the position
    has to be written down: left at its default every row ties at 0 and the
    order is then whatever the database happens to return (insertion order on
    SQLite, but not something Postgres promises)."""
    return [model(**item.model_dump(), order_index=index) for index, item in enumerate(items)]


def build_resume(data: ResumeCreate) -> Resume:
    """A new Resume (with every section, positioned) from validated input, not
    yet added to a session. Shared by create_resume and backup import, so a
    restored resume is built by exactly the code that builds a created one."""
    return Resume(
        name=data.name,
        headline=data.headline,
        summary=data.summary,
        personal_info=PersonalInfo(**data.personal_info.model_dump()),
        skills=_positioned(Skill, data.skills),
        experience=_positioned(Experience, data.experience),
        projects=_positioned(Project, data.projects),
        education=_positioned(Education, data.education),
        certifications=_positioned(Certification, data.certifications),
    )


def create_resume(session: Session, data: ResumeCreate) -> Resume:
    resume = build_resume(data)
    session.add(resume)
    session.commit()
    session.refresh(resume)
    return resume


@dataclass(frozen=True)
class ResumeStamp:
    """What identifies one *version* of a resume's content: its id and the time
    it was last updated (every content edit sets updated_at). Cheap to fetch
    (one narrow query, no nested sections), so a request can learn whether
    anything changed — for an ETag, a cache lookup — without loading the whole
    resume. ``name`` rides along because exports use it for the filename."""

    id: int
    name: str
    updated_at: datetime


def get_stamp(session: Session, resume_id: int) -> ResumeStamp | None:
    row = session.exec(
        select(Resume.id, Resume.name, Resume.updated_at).where(Resume.id == resume_id)
    ).first()
    return ResumeStamp(*row) if row else None


def get_default_stamp(session: Session) -> ResumeStamp | None:
    row = session.exec(
        select(Resume.id, Resume.name, Resume.updated_at)
        .where(col(Resume.is_default))
        .order_by(col(Resume.id))
    ).first()
    return ResumeStamp(*row) if row else None


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
    if data.headline is not None:
        resume.headline = data.headline
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
        resume.skills = _positioned(Skill, data.skills)
    if data.experience is not None:
        resume.experience = _positioned(Experience, data.experience)
    if data.projects is not None:
        resume.projects = _positioned(Project, data.projects)
    if data.education is not None:
        resume.education = _positioned(Education, data.education)
    if data.certifications is not None:
        resume.certifications = _positioned(Certification, data.certifications)

    resume.updated_at = datetime.now(UTC)
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
    return session.exec(
        select(Resume).where(col(Resume.is_default)).order_by(col(Resume.id))
    ).first()


# Arbitrary constant identifying "changing the default resume" to Postgres.
_SET_DEFAULT_LOCK_KEY = 7_283_002


def set_default_resume(session: Session, resume_id: int) -> Resume | None:
    """Marks resume_id as the one default resume, unsetting any previous
    default in the same transaction.

    Three layers keep "at most one default" true even when requests race (the
    app can run as several instances, and the MCP server is a second writer):

    1. On Postgres a transaction-scoped advisory lock makes concurrent calls
       take turns, so they do not collide at all (SQLite serializes writers on
       its own).
    2. The partial unique index ``uq_resumes_single_default`` makes the
       database refuse a second default no matter what.
    3. A collision that still reaches the index is rolled back and retried
       once, by which point the other writer has committed.

    This is the only code path allowed to set is_default=True.
    """
    for attempt in range(2):
        try:
            return _set_default(session, resume_id)
        except IntegrityError:
            session.rollback()
            if attempt == 1:
                raise
    raise AssertionError("unreachable")  # pragma: no cover


def lock_default_changes(session: Session) -> None:
    """Make concurrent changes to "which resume is the default" take turns, for
    the rest of this transaction (Postgres; SQLite serializes writers itself)."""
    if session.get_bind().dialect.name == "postgresql":
        # Released automatically at commit/rollback.
        session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": _SET_DEFAULT_LOCK_KEY})


def _set_default(session: Session, resume_id: int) -> Resume | None:
    lock_default_changes(session)

    resume = session.get(Resume, resume_id)
    if resume is None:
        return None

    for other in session.exec(select(Resume).where(col(Resume.is_default))).all():
        if other.id != resume_id:
            other.is_default = False
            session.add(other)
    # Unset before set, in separate statements: the unique index would reject
    # a moment with two defaults.
    session.flush()

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
        headline=source.headline,
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
