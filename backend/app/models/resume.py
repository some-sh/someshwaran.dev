"""Resume data model.

Per CLAUDE.md's architecture principle, resume content is modeled ONCE
here — personal_info, summary, skills, experience, projects, education,
certifications — and every output (public page, PDF/DOCX export, MCP
tool responses) renders from these tables rather than storing its own
copy of the content.

``Resume`` is one full resume version; ``is_default`` marks the version
served on the public site. Admin actions like clone and set-default are
built on top of this model in the API layer (phase 4) — this module only
defines the schema and relationships.

Note: this file deliberately does NOT use `from __future__ import
annotations`. SQLModel's relationship-target inference needs to see a
real generic-alias object (`list["Skill"]`, `Optional["PersonalInfo"]`)
to pull the target class out of it; with postponed evaluation the whole
annotation collapses to a plain string (e.g. "list[Skill]") and
SQLAlchemy rejects it as "a generic class as the argument to
relationship()". Forward references to classes defined later in this
file are quoted individually instead.
"""

from datetime import date, datetime
from typing import Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, Relationship, SQLModel


class Resume(SQLModel, table=True):
    __tablename__ = "resumes"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)  # internal label, e.g. "Backend-focused"
    is_default: bool = Field(default=False, index=True)
    summary: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    personal_info: Optional["PersonalInfo"] = Relationship(
        back_populates="resume",
        sa_relationship_kwargs={"cascade": "all, delete-orphan", "uselist": False},
    )
    skills: list["Skill"] = Relationship(
        back_populates="resume",
        sa_relationship_kwargs={"cascade": "all, delete-orphan", "order_by": "Skill.order_index"},
    )
    experience: list["Experience"] = Relationship(
        back_populates="resume",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
            "order_by": "Experience.order_index",
        },
    )
    projects: list["Project"] = Relationship(
        back_populates="resume",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
            "order_by": "Project.order_index",
        },
    )
    education: list["Education"] = Relationship(
        back_populates="resume",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
            "order_by": "Education.order_index",
        },
    )
    certifications: list["Certification"] = Relationship(
        back_populates="resume",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
            "order_by": "Certification.order_index",
        },
    )


class PersonalInfo(SQLModel, table=True):
    __tablename__ = "personal_info"

    id: int | None = Field(default=None, primary_key=True)
    resume_id: int = Field(foreign_key="resumes.id", unique=True)
    full_name: str
    email: str
    phone: str | None = None
    location: str | None = None
    website: str | None = None
    github: str | None = None
    linkedin: str | None = None

    resume: Resume = Relationship(back_populates="personal_info")


class Skill(SQLModel, table=True):
    __tablename__ = "skills"

    id: int | None = Field(default=None, primary_key=True)
    resume_id: int = Field(foreign_key="resumes.id")
    category: str | None = None  # e.g. "Languages", "Frameworks"
    name: str
    order_index: int = 0

    resume: Resume = Relationship(back_populates="skills")


class Experience(SQLModel, table=True):
    __tablename__ = "experience"

    id: int | None = Field(default=None, primary_key=True)
    resume_id: int = Field(foreign_key="resumes.id")
    company: str
    role: str
    location: str | None = None
    start_date: date
    end_date: date | None = None  # None == current position
    highlights: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    order_index: int = 0

    resume: Resume = Relationship(back_populates="experience")


class Project(SQLModel, table=True):
    __tablename__ = "projects"

    id: int | None = Field(default=None, primary_key=True)
    resume_id: int = Field(foreign_key="resumes.id")
    name: str
    description: str = ""
    url: str | None = None
    tech_stack: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    order_index: int = 0

    resume: Resume = Relationship(back_populates="projects")


class Education(SQLModel, table=True):
    __tablename__ = "education"

    id: int | None = Field(default=None, primary_key=True)
    resume_id: int = Field(foreign_key="resumes.id")
    institution: str
    degree: str
    field_of_study: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    order_index: int = 0

    resume: Resume = Relationship(back_populates="education")


class Certification(SQLModel, table=True):
    __tablename__ = "certifications"

    id: int | None = Field(default=None, primary_key=True)
    resume_id: int = Field(foreign_key="resumes.id")
    name: str
    issuer: str | None = None
    issued_date: date | None = None
    url: str | None = None
    order_index: int = 0

    resume: Resume = Relationship(back_populates="certifications")
