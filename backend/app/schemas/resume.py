"""Schemas for the resume CRUD service and the resume API.

Three layers per section (personal info, skill, experience, ...):

* ``*Base`` — the plain shape, no limits. Read schemas build on it, so
  anything already stored can always be loaded and served, whatever limits
  were in force when it was written.
* ``*Input`` — what clients may *write* (REST and MCP): the same fields with
  length limits, list-size limits and link validation. This is what keeps a
  buggy or prompt-injected client from storing megabytes of text or a
  ``javascript:`` link.
* ``*Read`` / ``ResumeSummary`` — what the API returns, built with
  ``from_attributes=True`` so a route can hand over an ORM object and let
  FastAPI's response_model conversion do the rest, without exposing the ORM
  models (or their SQLAlchemy relationship machinery) over the wire.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime
from typing import Annotated, Any

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
)

from app.core.urls import safe_url

# --- limits (writes only). Generous for a real resume, small enough that one
# resume can never grow into a storage or rendering problem. ---

_MAX_URL = 2000


def _text(max_length: int, *, min_length: int = 0) -> Any:
    return Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=min_length, max_length=max_length)
    ]


def _check_link(value: str | None) -> str | None:
    """Blank means "none". Otherwise it must be something a renderer may link:
    http(s), mailto, or a bare host such as 'linkedin.com/in/someone'."""
    if value is None or not value.strip():
        return None
    value = value.strip()
    if len(value) > _MAX_URL:
        raise ValueError(f"must be at most {_MAX_URL} characters")
    if safe_url(value) is None:
        raise ValueError("must be an http(s) link or a bare host such as example.com")
    return value


_Link = Annotated[str | None, AfterValidator(_check_link)]


# --- personal info ---


class PersonalInfoBase(BaseModel):
    full_name: str
    email: str
    phone: str | None = None
    location: str | None = None
    website: str | None = None
    github: str | None = None
    linkedin: str | None = None


class PersonalInfoInput(PersonalInfoBase):
    full_name: _text(200, min_length=1)  # type: ignore[valid-type]
    email: EmailStr
    phone: _text(50) | None = None  # type: ignore[valid-type]
    location: _text(200) | None = None  # type: ignore[valid-type]
    website: _Link = None
    github: _Link = None
    linkedin: _Link = None


# --- skills ---


class SkillBase(BaseModel):
    name: str
    category: str | None = None


class SkillInput(SkillBase):
    name: _text(100)  # type: ignore[valid-type]
    category: _text(100) | None = None  # type: ignore[valid-type]


# --- experience (with grouped highlights) ---


class Highlight(BaseModel):
    """One bullet under an experience entry. ``group`` is an optional
    sub-heading the bullet sits under (e.g. "Release and installation
    quality"); consecutive bullets with the same group render together under
    it, and bullets with no group render as a plain list."""

    text: str
    group: str | None = None


class HighlightInput(Highlight):
    text: _text(1000)  # type: ignore[valid-type]
    group: _text(200) | None = None  # type: ignore[valid-type]


def _highlight_dicts(raw: Iterable[Any] | None) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in raw or []:
        if isinstance(item, str):
            result.append({"text": item})
        elif isinstance(item, BaseModel):
            result.append(item.model_dump())
        else:
            result.append(item)
    return result


def normalize_highlights(raw: Iterable[Any] | None) -> list[Highlight]:
    """Accepts the shapes highlights have been stored and sent in: plain
    strings (the original format, still in existing rows and still accepted
    from API/MCP clients), ``{"text", "group"}`` dicts, or Highlight objects.
    The one place that coercion lives, used for input validation and by the
    renderers when they read straight from the ORM."""
    return [Highlight.model_validate(item) for item in _highlight_dicts(raw)]


# Coerces on every Experience schema (create/update input and read), so a row
# still holding plain strings is served as structured highlights.
_Highlights = Annotated[list[Highlight], BeforeValidator(_highlight_dicts)]
_HighlightInputs = Annotated[
    list[HighlightInput], BeforeValidator(_highlight_dicts), Field(max_length=50)
]


class ExperienceBase(BaseModel):
    company: str
    role: str
    location: str | None = None
    start_date: date
    end_date: date | None = None
    highlights: _Highlights = []


class ExperienceInput(ExperienceBase):
    company: _text(200)  # type: ignore[valid-type]
    role: _text(200)  # type: ignore[valid-type]
    location: _text(200) | None = None  # type: ignore[valid-type]
    # list is invariant, so mypy sees HighlightInput items as a different type
    # from the base's Highlight items; they are subclasses and behave the same.
    highlights: _HighlightInputs = []  # type: ignore[assignment]


# --- projects, education, certifications ---


class ProjectBase(BaseModel):
    name: str
    description: str = ""
    url: str | None = None
    tech_stack: list[str] = []


class ProjectInput(ProjectBase):
    name: _text(200)  # type: ignore[valid-type]
    description: _text(3000) = ""  # type: ignore[valid-type]
    url: _Link = None
    tech_stack: Annotated[list[_text(60)], Field(max_length=50)] = []  # type: ignore[valid-type]


class EducationBase(BaseModel):
    institution: str
    degree: str
    field_of_study: str | None = None
    start_date: date | None = None
    end_date: date | None = None


class EducationInput(EducationBase):
    institution: _text(200)  # type: ignore[valid-type]
    degree: _text(200)  # type: ignore[valid-type]
    field_of_study: _text(200) | None = None  # type: ignore[valid-type]


class CertificationBase(BaseModel):
    name: str
    issuer: str | None = None
    issued_date: date | None = None
    url: str | None = None


class CertificationInput(CertificationBase):
    name: _text(200)  # type: ignore[valid-type]
    issuer: _text(200) | None = None  # type: ignore[valid-type]
    url: _Link = None


# --- the resume ---


class ResumeCreate(BaseModel):
    name: _text(200, min_length=1)  # type: ignore[valid-type]
    # One-line professional headline shown under the name, e.g.
    # "Senior SDET | Test Automation & Infrastructure | Python, Playwright".
    headline: _text(300) = ""  # type: ignore[valid-type]
    summary: _text(4000) = ""  # type: ignore[valid-type]
    personal_info: PersonalInfoInput
    skills: Annotated[list[SkillInput], Field(max_length=200)] = []
    experience: Annotated[list[ExperienceInput], Field(max_length=50)] = []
    projects: Annotated[list[ProjectInput], Field(max_length=50)] = []
    education: Annotated[list[EducationInput], Field(max_length=20)] = []
    certifications: Annotated[list[CertificationInput], Field(max_length=50)] = []


class ResumeUpdate(BaseModel):
    """Partial update.

    Top-level scalar fields are patched individually when set. Each
    nested collection (skills, experience, ...), and personal_info, is
    replaced wholesale when provided — matching an editor that saves one
    section at a time — and left untouched when omitted (None).
    """

    name: _text(200, min_length=1) | None = None  # type: ignore[valid-type]
    headline: _text(300) | None = None  # type: ignore[valid-type]
    summary: _text(4000) | None = None  # type: ignore[valid-type]
    personal_info: PersonalInfoInput | None = None
    skills: Annotated[list[SkillInput], Field(max_length=200)] | None = None
    experience: Annotated[list[ExperienceInput], Field(max_length=50)] | None = None
    projects: Annotated[list[ProjectInput], Field(max_length=50)] | None = None
    education: Annotated[list[EducationInput], Field(max_length=20)] | None = None
    certifications: Annotated[list[CertificationInput], Field(max_length=50)] | None = None


# --- reads ---


class PersonalInfoRead(PersonalInfoBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class SkillRead(SkillBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class ExperienceRead(ExperienceBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class ProjectRead(ProjectBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class EducationRead(EducationBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class CertificationRead(CertificationBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class ResumeRead(BaseModel):
    """Full resume, nested content and all — what admin detail routes and
    the public default-resume route return."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    is_default: bool
    headline: str
    summary: str
    created_at: datetime
    updated_at: datetime
    personal_info: PersonalInfoRead | None
    skills: list[SkillRead]
    experience: list[ExperienceRead]
    projects: list[ProjectRead]
    education: list[EducationRead]
    certifications: list[CertificationRead]


class ResumeSummary(BaseModel):
    """One row of the admin resume list — enough to pick a resume to open,
    clone, or set as default without paying for the nested content."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    is_default: bool
    created_at: datetime
    updated_at: datetime
