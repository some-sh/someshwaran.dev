"""ATS-plain DOCX template — the same layout as ats_pdf.py in Word terms.

One column, Calibri, real Word styles (Title, Heading 2, List Bullet) so
parsers and screen readers see structure, A4, dates right-aligned with a tab
stop (not a table), and live hyperlinks. Like the PDF template it draws a
prepared ResumeDocument and never reformats data itself.
"""

from __future__ import annotations

import io
from typing import Any

from docx import Document
from docx.document import Document as DocxDocument
from docx.enum.section import WD_ORIENT
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Emu, Mm, Pt, RGBColor
from docx.text.paragraph import Paragraph
from docx.text.run import Run

from app.services.resume_document import Link, ResumeDocument

NAVY = RGBColor(0x1A, 0x33, 0x66)
INK = RGBColor(0x21, 0x21, 0x21)
MUTED = RGBColor(0x59, 0x59, 0x59)
FONT = "Calibri"

_MARGIN_X = Pt(42)
_MARGIN_Y = Pt(36)


def _set_font(style: Any, size: float, *, bold: bool = False, color: RGBColor = INK) -> None:
    """Font settings for a paragraph style (Normal, Title, ...)."""
    style.font.name = FONT
    style.font.size = Pt(size)
    style.font.bold = bold
    style.font.color.rgb = color
    # East-Asian font slot too, or Word falls back for some characters.
    r_fonts = style.element.get_or_add_rPr().rFonts
    if r_fonts is not None:
        r_fonts.set(qn("w:eastAsia"), FONT)


def _bottom_border(ppr: Any, color: str = "1A3366") -> None:
    """Thin rule under a paragraph style; ``ppr`` is its w:pPr element."""
    borders = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "6")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), color)
    borders.append(bottom)
    ppr.append(borders)


def _remove_borders(style: Any) -> None:
    ppr = style.element.pPr
    if ppr is not None:
        for borders in ppr.findall(qn("w:pBdr")):
            ppr.remove(borders)


def _prepare(document: DocxDocument) -> None:
    section = document.sections[0]
    section.orientation = WD_ORIENT.PORTRAIT
    section.page_width, section.page_height = Mm(210), Mm(297)  # A4
    section.left_margin = section.right_margin = _MARGIN_X
    section.top_margin = section.bottom_margin = _MARGIN_Y

    normal = document.styles["Normal"]
    _set_font(normal, 10)
    normal.paragraph_format.space_after = Pt(1.5)
    normal.paragraph_format.space_before = Pt(0)
    normal.paragraph_format.line_spacing = 1.0

    title = document.styles["Title"]
    _remove_borders(title)  # the default template draws a rule under the title
    _set_font(title, 20, bold=True, color=NAVY)
    title.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.paragraph_format.space_after = Pt(1)

    heading = document.styles["Heading 2"]
    _set_font(heading, 11, bold=True, color=NAVY)
    heading.paragraph_format.space_before = Pt(9)
    heading.paragraph_format.space_after = Pt(3)
    heading.paragraph_format.keep_with_next = True
    _bottom_border(heading.element.get_or_add_pPr())

    bullet = document.styles["List Bullet"]
    _set_font(bullet, 10)
    bullet.paragraph_format.space_after = Pt(1.5)

    if "Group" not in [style.name for style in document.styles]:
        group = document.styles.add_style("Group", WD_STYLE_TYPE.PARAGRAPH)
        group.base_style = document.styles["Normal"]
        _set_font(group, 10, bold=True, color=NAVY)
        group.paragraph_format.space_before = Pt(3)
        group.paragraph_format.keep_with_next = True


def _text_width() -> Emu:
    return Emu(Mm(210) - 2 * _MARGIN_X)


def _run(
    paragraph: Paragraph,
    text: str,
    *,
    bold: bool = False,
    italic: bool = False,
    color: RGBColor = INK,
    size: float = 10,
) -> Run:
    run = paragraph.add_run(text)
    run.bold, run.italic = bold, italic
    run.font.color.rgb = color
    run.font.size = Pt(size)
    return run


def _hyperlink(paragraph: Paragraph, url: str, text: str) -> None:
    """A live external hyperlink run (python-docx has no public API for it)."""
    relationship = paragraph.part.relate_to(url, RT.HYPERLINK, is_external=True)
    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("r:id"), relationship)
    run = OxmlElement("w:r")
    properties = OxmlElement("w:rPr")
    colour = OxmlElement("w:color")
    colour.set(qn("w:val"), "1A3366")
    underline = OxmlElement("w:u")
    underline.set(qn("w:val"), "single")
    size = OxmlElement("w:sz")
    size.set(qn("w:val"), "19")  # half-points: 9.5pt
    properties.extend([colour, underline, size])
    run.append(properties)
    content = OxmlElement("w:t")
    content.text = text
    content.set(qn("xml:space"), "preserve")
    run.append(content)
    hyperlink.append(run)
    paragraph._p.append(hyperlink)


def _link_or_text(paragraph: Paragraph, link: Link, size: float = 9.5) -> None:
    if link.url:
        _hyperlink(paragraph, link.url, link.text)
    else:
        _run(paragraph, link.text, color=MUTED, size=size)


def _dated_line(
    document: DocxDocument, left_runs: list[tuple[str, dict[str, Any]]], dates: str
) -> Paragraph:
    """Left text, then dates against the right margin via a right tab stop."""
    paragraph: Paragraph = document.add_paragraph()
    paragraph.paragraph_format.tab_stops.add_tab_stop(_text_width(), WD_TAB_ALIGNMENT.RIGHT)
    paragraph.paragraph_format.keep_with_next = True
    for text, kwargs in left_runs:
        _run(paragraph, text, **kwargs)
    if dates:
        _run(paragraph, "\t", size=10)
        _run(paragraph, dates, color=MUTED, size=9.5)
    return paragraph


def render(resume_document: ResumeDocument) -> bytes:
    document = Document()
    _prepare(document)
    properties = document.core_properties
    properties.title = f"{resume_document.name} — Resume"
    properties.author = resume_document.name
    properties.subject = resume_document.headline
    properties.comments = ""

    document.add_paragraph(resume_document.name, style="Title")
    if resume_document.headline:
        line = document.add_paragraph()
        line.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _run(line, resume_document.headline, bold=True, size=10.5)
    if resume_document.contact:
        line = document.add_paragraph()
        line.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for index, link in enumerate(resume_document.contact):
            if index:
                _run(line, " • ", color=MUTED, size=9.5)
            _link_or_text(line, link)

    def heading(title: str) -> None:
        document.add_paragraph(title.upper(), style="Heading 2")

    if resume_document.summary:
        heading("Summary")
        document.add_paragraph(resume_document.summary)

    if resume_document.skills:
        heading("Skills")
        for skill in resume_document.skills:
            line = document.add_paragraph()
            _run(line, f"{skill.category}: ", bold=True)
            _run(line, ", ".join(skill.names))

    if resume_document.experience:
        heading("Experience")
        for entry in resume_document.experience:
            _dated_line(document, [(entry.role, {"bold": True})], entry.dates)
            company = ", ".join(part for part in (entry.company, entry.location) if part)
            if company:
                meta = document.add_paragraph()
                meta.paragraph_format.keep_with_next = bool(entry.groups)
                _run(meta, company, italic=True, color=MUTED, size=9.5)
            for group in entry.groups:
                if group.title:
                    document.add_paragraph(group.title, style="Group")
                for bullet in group.bullets:
                    document.add_paragraph(bullet, style="List Bullet")

    if resume_document.projects:
        heading("Projects")
        for project in resume_document.projects:
            line = document.add_paragraph()
            _run(line, project.name, bold=True)
            if project.tech:
                _run(line, f" — {project.tech}")
            if project.link:
                _run(line, " • ", color=MUTED, size=9.5)
                _link_or_text(line, project.link)
            if project.description:
                document.add_paragraph(project.description)

    if resume_document.education:
        heading("Education")
        for edu in resume_document.education:
            runs: list[tuple[str, dict[str, Any]]] = [
                (edu.degree, {"bold": True}),
                (f", {edu.institution}", {}),
            ]
            if edu.field_of_study:
                runs.append((f" — {edu.field_of_study}", {}))
            _dated_line(document, runs, edu.years).paragraph_format.keep_with_next = False

    if resume_document.certifications:
        heading("Certifications")
        for cert in resume_document.certifications:
            runs = [(cert.name, {})]
            if cert.issuer:
                runs.append((f", {cert.issuer}", {}))
            line = _dated_line(document, runs, cert.date)
            line.paragraph_format.keep_with_next = False
            if cert.link:
                _run(line, " • ", color=MUTED, size=9.5)
                _link_or_text(line, cert.link)

    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()
