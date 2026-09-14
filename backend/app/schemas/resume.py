"""Schemas for the resume CRUD service and the resume API.

Input schemas (``*Input``, ``ResumeCreate``, ``ResumeUpdate``) are plain
Pydantic models describing what the service accepts. Read schemas
(``*Read``, ``ResumeSummary``) describe what the API returns — built with
``from_attributes=True`` so a route can hand a route handler an ORM object
straight out of app.models.resume and let FastAPI's response_model
conversion do the rest, without ever exposing the ORM models (or their
SQLAlchemy relationship machinery) over the wire directly.
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class PersonalInfoInput(BaseModel):
    full_name: str
    email: str
    phone: str | None = None
    location: str | None = None
    website: str | None = None
    github: str | None = None
    linkedin: str | None = None


class SkillInput(BaseModel):
    name: str
    category: str | None = None


class ExperienceInput(BaseModel):
    company: str
    role: str
    location: str | None = None
    start_date: date
    end_date: date | None = None
    highlights: list[str] = []


class ProjectInput(BaseModel):
    name: str
    description: str = ""
    url: str | None = None
    tech_stack: list[str] = []


class EducationInput(BaseModel):
    institution: str
    degree: str
    field_of_study: str | None = None
    start_date: date | None = None
    end_date: date | None = None


class CertificationInput(BaseModel):
    name: str
    issuer: str | None = None
    issued_date: date | None = None
    url: str | None = None


class ResumeCreate(BaseModel):
    name: str
    summary: str = ""
    personal_info: PersonalInfoInput
    skills: list[SkillInput] = []
    experience: list[ExperienceInput] = []
    projects: list[ProjectInput] = []
    education: list[EducationInput] = []
    certifications: list[CertificationInput] = []


class ResumeUpdate(BaseModel):
    """Partial update.

    Top-level scalar fields are patched individually when set. Each
    nested collection (skills, experience, ...), and personal_info, is
    replaced wholesale when provided — matching an editor that saves one
    section at a time — and left untouched when omitted (None).
    """

    name: str | None = None
    summary: str | None = None
    personal_info: PersonalInfoInput | None = None
    skills: list[SkillInput] | None = None
    experience: list[ExperienceInput] | None = None
    projects: list[ProjectInput] | None = None
    education: list[EducationInput] | None = None
    certifications: list[CertificationInput] | None = None


class PersonalInfoRead(PersonalInfoInput):
    id: int
    model_config = ConfigDict(from_attributes=True)


class SkillRead(SkillInput):
    id: int
    model_config = ConfigDict(from_attributes=True)


class ExperienceRead(ExperienceInput):
    id: int
    model_config = ConfigDict(from_attributes=True)


class ProjectRead(ProjectInput):
    id: int
    model_config = ConfigDict(from_attributes=True)


class EducationRead(EducationInput):
    id: int
    model_config = ConfigDict(from_attributes=True)


class CertificationRead(CertificationInput):
    id: int
    model_config = ConfigDict(from_attributes=True)


class ResumeRead(BaseModel):
    """Full resume, nested content and all — what admin detail routes and
    the public default-resume route return."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    is_default: bool
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
