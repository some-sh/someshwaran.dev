"""A resume prepared for printing: the display model every export template
draws from.

The database models hold raw data (full dates, unvalidated URLs, bullets that
may be old plain strings). Turning that into what a reader should see — "May
2019 – Present", "linkedin.com/in/…" as a link, bullets gathered under their
sub-headings — is done here, once, so the PDF and DOCX templates (and any
future ones) are dumb drawing code that cannot drift apart on formatting.

Everything here is plain text. Escaping for a particular output format (the
PDF template's inline markup, for one) is the template's job, at the point it
builds that format.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from urllib.parse import urlparse

from app.models.resume import Education, Experience, Resume
from app.schemas.resume import normalize_highlights

# Fixed English month names rather than strftime("%b"), which depends on the
# server's locale and would make output differ between environments.
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

_LINKABLE_SCHEMES = {"http", "https", "mailto"}
_HAS_SCHEME = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.\-]*:")
_HOST_AND_PORT = re.compile(r"^[^/:\s]+:\d+(/|$)")


@dataclass(frozen=True)
class Link:
    """Text to show, and where it points (None = not a link)."""

    text: str
    url: str | None = None


@dataclass(frozen=True)
class BulletGroup:
    """Bullets under an optional sub-heading (``title`` None = no heading)."""

    title: str | None
    bullets: tuple[str, ...]


@dataclass(frozen=True)
class SkillLine:
    category: str
    names: tuple[str, ...]


@dataclass(frozen=True)
class ExperienceEntry:
    role: str
    company: str
    location: str  # "" when unknown
    dates: str
    groups: tuple[BulletGroup, ...]


@dataclass(frozen=True)
class ProjectEntry:
    name: str
    tech: str  # "" when none
    description: str
    link: Link | None


@dataclass(frozen=True)
class EducationEntry:
    degree: str
    institution: str
    field_of_study: str  # "" when unknown
    years: str  # "" when unknown


@dataclass(frozen=True)
class CertificationEntry:
    name: str
    issuer: str  # "" when unknown
    date: str  # "" when unknown
    link: Link | None


@dataclass(frozen=True)
class ResumeDocument:
    name: str
    headline: str
    contact: tuple[Link, ...]
    summary: str
    skills: tuple[SkillLine, ...]
    experience: tuple[ExperienceEntry, ...]
    projects: tuple[ProjectEntry, ...]
    education: tuple[EducationEntry, ...]
    certifications: tuple[CertificationEntry, ...]


def month_year(value: date) -> str:
    return f"{_MONTHS[value.month - 1]} {value.year}"


def experience_dates(exp: Experience) -> str:
    end = month_year(exp.end_date) if exp.end_date else "Present"
    return f"{month_year(exp.start_date)} – {end}"


def education_years(edu: Education) -> str:
    """Years only: the stored value is a full date because the column needs
    one, so showing 'Jan 2019' would present a made-up month as fact."""
    start = str(edu.start_date.year) if edu.start_date else ""
    end = str(edu.end_date.year) if edu.end_date else ""
    if start and end and start != end:
        return f"{start} – {end}"
    return end or start


def safe_url(value: str | None) -> str | None:
    """The URL if it is safe to emit as a link (http, https or mailto), else
    None. A bare host ("linkedin.com/in/x", "example.com:8080") gets https://.
    Anything that starts with some other scheme — javascript:, data:, file: —
    is shown as text and never linked; note "javascript:alert(1)" has no "//",
    so "has a scheme" is decided by the leading ``name:``, not by "://"."""
    if not value or not value.strip():
        return None
    candidate = value.strip()
    if not _HAS_SCHEME.match(candidate) or _HOST_AND_PORT.match(candidate):
        candidate = f"https://{candidate}"
    parsed = urlparse(candidate)
    scheme = parsed.scheme.lower()
    if scheme not in _LINKABLE_SCHEMES:
        return None
    if scheme == "mailto":
        return candidate if parsed.path else None
    return candidate if parsed.netloc else None


def display_url(value: str) -> str:
    """'https://www.linkedin.com/in/x/' -> 'linkedin.com/in/x'."""
    shown = value.strip()
    for prefix in ("https://", "http://", "mailto:"):
        if shown.lower().startswith(prefix):
            shown = shown[len(prefix) :]
    if shown.lower().startswith("www."):
        shown = shown[4:]
    return shown.rstrip("/")


def _web_link(value: str | None) -> Link | None:
    if not value or not value.strip():
        return None
    return Link(display_url(value), safe_url(value))


def _contact(resume: Resume) -> tuple[Link, ...]:
    info = resume.personal_info
    if info is None:
        return ()
    items: list[Link | None] = [
        Link(info.email, f"mailto:{info.email}") if info.email else None,
        Link(info.phone) if info.phone else None,
        Link(info.location) if info.location else None,
        _web_link(info.website),
        _web_link(info.github),
        _web_link(info.linkedin),
    ]
    return tuple(item for item in items if item is not None)


def _groups(exp: Experience) -> tuple[BulletGroup, ...]:
    """Consecutive bullets with the same sub-heading become one group."""
    groups: list[BulletGroup] = []
    for highlight in normalize_highlights(exp.highlights):
        text = highlight.text.strip()
        if not text:
            continue
        title = highlight.group.strip() if highlight.group and highlight.group.strip() else None
        if groups and groups[-1].title == title:
            groups[-1] = BulletGroup(title, (*groups[-1].bullets, text))
        else:
            groups.append(BulletGroup(title, (text,)))
    return tuple(groups)


def build_document(resume: Resume) -> ResumeDocument:
    skills: dict[str, list[str]] = {}
    for skill in resume.skills:
        skills.setdefault(skill.category or "General", []).append(skill.name)

    return ResumeDocument(
        name=resume.personal_info.full_name if resume.personal_info else resume.name,
        headline=resume.headline.strip(),
        contact=_contact(resume),
        summary=resume.summary.strip(),
        skills=tuple(SkillLine(category, tuple(names)) for category, names in skills.items()),
        experience=tuple(
            ExperienceEntry(
                role=exp.role,
                company=exp.company,
                location=(exp.location or "").strip(),
                dates=experience_dates(exp),
                groups=_groups(exp),
            )
            for exp in resume.experience
        ),
        projects=tuple(
            ProjectEntry(
                name=project.name,
                tech=", ".join(project.tech_stack),
                description=project.description.strip(),
                link=_web_link(project.url),
            )
            for project in resume.projects
        ),
        education=tuple(
            EducationEntry(
                degree=edu.degree,
                institution=edu.institution,
                field_of_study=(edu.field_of_study or "").strip(),
                years=education_years(edu),
            )
            for edu in resume.education
        ),
        certifications=tuple(
            CertificationEntry(
                name=cert.name,
                issuer=(cert.issuer or "").strip(),
                date=month_year(cert.issued_date) if cert.issued_date else "",
                link=_web_link(cert.url),
            )
            for cert in resume.certifications
        ),
    )
