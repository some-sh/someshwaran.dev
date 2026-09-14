"""Input schemas for the resume CRUD service.

These are plain Pydantic models (not SQLModel tables) describing the
shape of data the service accepts. Output is the ORM models themselves
(app.models.resume) — dedicated read/response schemas belong to the API
layer in phase 4, once there's a wire format to stabilize.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel


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
