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
    assert "B.E., MNM Jain — ECE\t2015 – 2019" in text  # dates sit after a right tab


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

    for heading in ("SKILLS", "EXPERIENCE", "PROJECTS", "EDUCATION", "CERTIFICATIONS"):
        assert heading in extracted


# --- ATS-plain template: structure of the generated documents ---


def _grouped_resume() -> Resume:
    return Resume(
        name="Senior SDET (Nov 2026)",
        headline="Senior SDET | Python, Playwright",
        summary="Builds test infrastructure.",
        personal_info=PersonalInfo(
            full_name="Ada Lovelace",
            email="ada@example.com",
            location="Chennai, India",
            linkedin="https://www.linkedin.com/in/ada",
            website="javascript:alert(1)",
        ),
        skills=[
            Skill(name="Python", category="Languages"),
            Skill(name="Playwright", category="Tools"),
        ],
        experience=[
            Experience(
                company="Acme Corp",
                role="Member Technical Staff",
                location="Chennai",
                start_date=date(2019, 5, 1),
                highlights=[
                    {"text": "Built the platform", "group": "Engineering platform"},
                    {"text": "Cut setup time", "group": "Engineering platform"},
                    {"text": "Validated releases", "group": "Release quality"},
                ],
            )
        ],
        education=[
            Education(
                institution="MNM Jain",
                degree="B.E.",
                start_date=date(2015, 1, 1),
                end_date=date(2019, 1, 1),
            )
        ],
    )


def _lines(text: str) -> list[str]:
    return [" ".join(line.split()) for line in text.splitlines() if line.strip()]


def _pdf_links(pdf_bytes: bytes) -> list[str]:
    uris: list[str] = []
    for page in PdfReader(io.BytesIO(pdf_bytes)).pages:
        for annotation in page.get("/Annots", []) or []:
            action = annotation.get_object().get("/A")
            if action is not None and "/URI" in action.get_object():
                uris.append(str(action.get_object()["/URI"]))
    return uris


def test_pdf_is_a_single_column_a4_document_with_metadata() -> None:
    reader = PdfReader(io.BytesIO(render_resume_pdf(_grouped_resume())))

    box = reader.pages[0].mediabox
    assert (round(float(box.width)), round(float(box.height))) == (595, 842)  # A4
    assert reader.metadata is not None
    assert reader.metadata.title == "Ada Lovelace — Resume"
    assert reader.metadata.author == "Ada Lovelace"
    assert reader.metadata.subject == "Senior SDET | Python, Playwright"


def test_pdf_sections_appear_in_conventional_order() -> None:
    text = _pdf_text(render_resume_pdf(_grouped_resume()))

    positions = [text.index(h) for h in ("SUMMARY", "SKILLS", "EXPERIENCE", "EDUCATION")]
    assert positions == sorted(positions)
    assert text.index("Ada Lovelace") < text.index("Senior SDET | Python, Playwright")


def test_pdf_keeps_each_role_next_to_its_dates_in_extracted_text() -> None:
    """Reading-order extractors (pypdf here) return the right-aligned dates as
    the text right after the role, never somewhere else in the document. A
    layout-aware one puts them on the same line — checked by hand with
    `pdftotext -layout`, which is not a test dependency."""
    lines = _lines(_pdf_text(render_resume_pdf(_grouped_resume())))

    role = next(i for i, line in enumerate(lines) if "Member Technical Staff" in line)
    assert any("May 2019 – Present" in line for line in lines[role : role + 2])
    education = next(i for i, line in enumerate(lines) if "MNM Jain" in line)
    assert any("2015 – 2019" in line for line in lines[education : education + 2])


def test_pdf_lists_grouped_bullets_under_their_sub_headings() -> None:
    lines = _lines(_pdf_text(render_resume_pdf(_grouped_resume())))

    order = [
        lines.index("Engineering platform"),
        next(i for i, line in enumerate(lines) if "Built the platform" in line),
        next(i for i, line in enumerate(lines) if "Cut setup time" in line),
        lines.index("Release quality"),
        next(i for i, line in enumerate(lines) if "Validated releases" in line),
    ]
    assert order == sorted(order)


def test_pdf_links_are_live_only_for_safe_urls() -> None:
    links = _pdf_links(render_resume_pdf(_grouped_resume()))

    assert "mailto:ada@example.com" in links
    assert "https://www.linkedin.com/in/ada" in links
    # The javascript: website is printed as text but is not a clickable link.
    assert not any("javascript" in link.lower() for link in links)
    assert "javascript:alert(1)" in _pdf_text(render_resume_pdf(_grouped_resume()))


def test_pdf_without_headline_or_groups_still_renders() -> None:
    resume = _grouped_resume()
    resume.headline = ""
    resume.experience[0].highlights = ["a plain old string bullet"]

    text = _pdf_text(render_resume_pdf(resume))

    assert "a plain old string bullet" in text
    assert "Engineering platform" not in text


def test_docx_is_a_structured_a4_document() -> None:
    document = Document(io.BytesIO(render_resume_docx(_grouped_resume())))

    section = document.sections[0]
    assert (round(section.page_width.mm), round(section.page_height.mm)) == (210, 297)
    styles = [p.style.name for p in document.paragraphs]
    assert styles[0] == "Title"  # the name is a real title, not just big text
    assert styles.count("Heading 2") == 4  # summary, skills, experience, education
    assert styles.count("List Bullet") == 3
    assert styles.count("Group") == 2
    assert document.core_properties.title == "Ada Lovelace — Resume"
    assert document.core_properties.author == "Ada Lovelace"


def test_docx_dates_are_right_aligned_with_a_tab_stop_not_a_table() -> None:
    document = Document(io.BytesIO(render_resume_docx(_grouped_resume())))

    role = next(p for p in document.paragraphs if p.text.startswith("Member Technical Staff"))
    assert role.text == "Member Technical Staff\tMay 2019 – Present"
    assert len(role.paragraph_format.tab_stops) == 1
    assert document.tables == []  # ATS parsers read tables unreliably


def test_docx_hyperlinks_are_live_only_for_safe_urls() -> None:
    document = Document(io.BytesIO(render_resume_docx(_grouped_resume())))

    targets = [
        rel.target_ref for rel in document.part.rels.values() if rel.reltype.endswith("/hyperlink")
    ]
    assert "mailto:ada@example.com" in targets
    assert "https://www.linkedin.com/in/ada" in targets
    assert not any("javascript" in target.lower() for target in targets)


def test_docx_escapes_nothing_and_prints_markup_characters_literally() -> None:
    resume = _resume_with_text("Wrote a <para tag & <b>bold</b>")

    document = Document(io.BytesIO(render_resume_docx(resume)))

    assert "Wrote a <para tag & <b>bold</b>" in "\n".join(p.text for p in document.paragraphs)


def _baselines(pdf_bytes: bytes, wanted: set[str]) -> dict[str, float]:
    """Baseline y of the first text run equal to each wanted string."""
    found: dict[str, float] = {}

    def visit(text, cm, tm, font_dict, font_size):  # noqa: ANN001 - pypdf visitor signature
        run = text.strip()
        if run in wanted and run not in found:
            found[run] = tm[5] * cm[3] + tm[4] * cm[1] + cm[5]

    PdfReader(io.BytesIO(pdf_bytes)).pages[0].extract_text(visitor_text=visit)
    return found


def test_pdf_dates_share_the_baseline_of_their_role_line() -> None:
    """Dates are drawn separately from the role text, so their baselines must be
    computed to match; they were once 3pt too high (measured on the live PDF)."""
    pdf = render_resume_pdf(_grouped_resume())

    y = _baselines(pdf, {"Member Technical Staff", "May 2019 – Present", "2015 – 2019", "B.E."})

    assert abs(y["Member Technical Staff"] - y["May 2019 – Present"]) < 0.1
    assert abs(y["B.E."] - y["2015 – 2019"]) < 0.1
