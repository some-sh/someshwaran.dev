"""Unit tests for resume rendering. Rendering is a pure function of a
Resume object, so these build one directly rather than going through the
service/DB layer."""

import io
from datetime import date

from docx import Document

from app.models.resume import Experience, PersonalInfo, Resume, Skill
from app.services.export_service import render_resume_docx, render_resume_pdf, slugify_filename


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
