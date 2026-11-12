"""Unit tests for resume rendering. Rendering is a pure function of a
Resume object, so these build one directly rather than going through the
service/DB layer."""

import io
from datetime import date

import pytest
from docx import Document
from pypdf import PdfReader

from app.models.resume import (
    Certification,
    Education,
    Experience,
    PersonalInfo,
    Project,
    Resume,
    Skill,
)
from app.services.export_service import (
    _education_years,
    _experience_dates,
    render_resume_docx,
    render_resume_pdf,
    slugify_filename,
)


def _sample_resume() -> Resume:
    return Resume(
        name="Backend-focused",
        summary="Backend engineer.",
        personal_info=PersonalInfo(full_name="Ada Lovelace", email="ada@example.com"),
        skills=[Skill(name="Python", category="Languages")],
        experience=[
            Experience(
                company="Acme",
                role="SDET",
                start_date=date(2022, 1, 1),
                highlights=["Built the test framework"],
            )
        ],
    )


def test_slugify_filename_normalizes_to_a_url_safe_stem():
    assert slugify_filename("Backend-focused (copy)") == "backend-focused-copy"


def test_slugify_filename_falls_back_when_nothing_survives():
    assert slugify_filename("!!!") == "resume"


def test_render_resume_pdf_produces_a_pdf():
    pdf_bytes = render_resume_pdf(_sample_resume())

    assert pdf_bytes.startswith(b"%PDF")


def test_render_resume_pdf_handles_a_resume_with_no_optional_sections():
    minimal = Resume(name="Bare", personal_info=PersonalInfo(full_name="X", email="x@example.com"))

    assert render_resume_pdf(minimal).startswith(b"%PDF")


def test_render_resume_docx_contains_the_resume_content():
    docx_bytes = render_resume_docx(_sample_resume())

    document = Document(io.BytesIO(docx_bytes))
    text = "\n".join(p.text for p in document.paragraphs)
    assert "Ada Lovelace" in text
    assert "Built the test framework" in text
    assert "Acme" in text


def test_experience_dates_use_month_and_year_not_iso():
    exp = Experience(
        company="Acme", role="SDET", start_date=date(2019, 5, 1), end_date=date(2021, 12, 31)
    )

    assert _experience_dates(exp) == "May 2019 – Dec 2021"


def test_experience_dates_show_present_for_a_current_role():
    exp = Experience(company="Acme", role="SDET", start_date=date(2019, 5, 1))

    assert _experience_dates(exp) == "May 2019 – Present"


def test_education_years_show_years_only():
    edu = Education(
        institution="MNM Jain",
        degree="B.E.",
        start_date=date(2015, 1, 1),
        end_date=date(2019, 1, 1),
    )

    assert _education_years(edu) == "2015 – 2019"


def test_education_years_handle_missing_and_equal_years():
    assert _education_years(Education(institution="X", degree="Y")) == ""
    assert (
        _education_years(Education(institution="X", degree="Y", end_date=date(2019, 6, 1)))
        == "2019"
    )
    same = Education(
        institution="X", degree="Y", start_date=date(2019, 1, 1), end_date=date(2019, 12, 1)
    )
    assert _education_years(same) == "2019"


def test_docx_renders_formatted_dates_and_education_years():
    resume = _sample_resume()
    resume.experience[0].start_date = date(2019, 5, 1)
    resume.education = [
        Education(
            institution="MNM Jain",
            degree="B.E.",
            field_of_study="ECE",
            start_date=date(2015, 1, 1),
            end_date=date(2019, 1, 1),
        )
    ]

    document = Document(io.BytesIO(render_resume_docx(resume)))
    text = "\n".join(p.text for p in document.paragraphs)

    assert "May 2019 – Present" in text
    assert "2019-05-01" not in text
    assert "B.E., MNM Jain — ECE (2015 – 2019)" in text


def _pdf_text(pdf_bytes: bytes) -> str:
    return "\n".join(page.extract_text() for page in PdfReader(io.BytesIO(pdf_bytes)).pages)


def _resume_with_text(text: str) -> Resume:
    """A resume whose every free-text field is ``text``, so one test covers
    every place the PDF renderer interpolates user content."""
    return Resume(
        name="x",
        summary=text,
        personal_info=PersonalInfo(full_name=text, email="a@example.com", location=text),
        skills=[Skill(name=text, category=text)],
        experience=[
            Experience(
                company=text,
                role=text,
                start_date=date(2020, 1, 1),
                highlights=[text],
            )
        ],
        projects=[Project(name=text, description=text, tech_stack=[text])],
        education=[Education(institution=text, degree=text, field_of_study=text)],
        certifications=[Certification(name=text, issuer=text)],
    )


@pytest.mark.parametrize(
    "text",
    [
        "Wrote a <para tag",  # unbalanced markup used to crash the export
        "Used <b>bold</b> and <i>italics",
        "Reduced latency from <200ms> to <50ms>",
        "R&D, QA & release",
        "<script>alert(1)</script>",
    ],
)
def test_pdf_prints_user_text_literally_instead_of_parsing_it_as_markup(text: str) -> None:
    extracted = _pdf_text(render_resume_pdf(_resume_with_text(text)))

    # The raw characters survive (whitespace is normalized by extraction).
    assert " ".join(text.split()) in " ".join(extracted.split())


def test_pdf_does_not_embed_files_named_in_user_text(tmp_path) -> None:
    from PIL import Image

    image = tmp_path / "secret.png"
    Image.new("RGB", (8, 8), "red").save(image)

    pdf = render_resume_pdf(_resume_with_text(f'<img src="{image}" width="40" height="40"/>'))

    # Before escaping, <img src=local-path> pulled the file into the PDF.
    assert not any(page.images for page in PdfReader(io.BytesIO(pdf)).pages)
    assert "<img" in _pdf_text(pdf)


def test_pdf_renders_every_section() -> None:
    extracted = _pdf_text(render_resume_pdf(_resume_with_text("Same")))

    for heading in ("Skills", "Experience", "Projects", "Education", "Certifications"):
        assert heading in extracted
