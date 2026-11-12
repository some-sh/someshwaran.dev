"""ATS-plain PDF template.

Built for applicant-tracking systems first and people second: one column,
standard fonts, real selectable text in reading order, conventional section
names, plain round bullets, no images or icons. Dates sit right-aligned on
the same baseline as the role (text drawn on one line, not a table). A4,
matching the paper size used where this resume is sent.

On extraction: layout-aware extractors (``pdftotext -layout``, pdfminer-style
parsers) return role and dates as one line. Reading-order extractors treat the
wide gap as a column break and return the dates as the next piece of text,
still directly after the role. Which kind a given ATS uses can't be known from
here; if dates must never be separated from the role, put them inline
("Role | May 2019 – Present") instead of right-aligning them.

All resume text reaches reportlab through ``escape`` — Paragraph parses its
input as inline markup, and resume content is data, not markup (see
tests/unit/test_export_service.py). Only tags built here are live.
"""

from __future__ import annotations

import io
from xml.sax.saxutils import escape, quoteattr

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.platypus import (
    Flowable,
    HRFlowable,
    KeepTogether,
    ListFlowable,
    ListItem,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)

from app.services.resume_document import BulletGroup, Link, ResumeDocument

NAVY = colors.HexColor("#1A3366")
INK = colors.HexColor("#212121")
MUTED = colors.HexColor("#595959")

_MARGIN_X = 42  # points, matches a typical Google Docs A4 resume
_MARGIN_Y = 36
_DATE_GAP = 12  # minimum points between the left text and right-aligned dates


def _styles() -> dict[str, ParagraphStyle]:
    base = ParagraphStyle("base", fontName="Helvetica", fontSize=10, leading=13, textColor=INK)
    return {
        "name": ParagraphStyle(
            "name",
            parent=base,
            fontName="Helvetica-Bold",
            fontSize=20,
            leading=24,
            alignment=TA_CENTER,
            textColor=NAVY,
        ),
        "headline": ParagraphStyle(
            "headline",
            parent=base,
            fontName="Helvetica-Bold",
            fontSize=10.5,
            leading=14,
            alignment=TA_CENTER,
        ),
        "contact": ParagraphStyle(
            "contact", parent=base, fontSize=9.5, leading=13, alignment=TA_CENTER, textColor=MUTED
        ),
        "section": ParagraphStyle(
            "section",
            parent=base,
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=NAVY,
            spaceBefore=9,
            spaceAfter=1,
            keepWithNext=1,
        ),
        "body": ParagraphStyle("body", parent=base, spaceAfter=1.5),
        "role": ParagraphStyle("role", parent=base, fontName="Helvetica-Bold"),
        "dates": ParagraphStyle(
            "dates", parent=base, fontSize=9.5, alignment=TA_RIGHT, textColor=MUTED
        ),
        "meta": ParagraphStyle(
            "meta", parent=base, fontName="Helvetica-Oblique", fontSize=9.5, textColor=MUTED
        ),
        "group": ParagraphStyle(
            "group",
            parent=base,
            fontName="Helvetica-Bold",
            textColor=NAVY,
            spaceBefore=3,
            spaceAfter=1,
            keepWithNext=1,
        ),
    }


def _link_markup(link: Link) -> str:
    """Text, wrapped in a live hyperlink only when the URL is a safe one."""
    text = escape(link.text)
    if link.url is None:
        return text
    return f'<a href={quoteattr(link.url)} color="#1A3366"><u>{text}</u></a>'


def _join(parts: list[str], separator: str = " • ") -> str:
    return separator.join(part for part in parts if part)


class _DatedLine(Flowable):  # type: ignore[misc]  # reportlab ships no type stubs
    """Left text with a date flush against the right margin, on the same
    baseline as the left text's first line.

    Deliberately not a table: extractors emit table cells as unrelated
    blocks, whereas text on one baseline is read as a line by layout-aware
    ones. The left text is a normal Paragraph, so it still wraps and still
    carries links; it just gets the width the date leaves free.
    """

    def __init__(self, left: Paragraph, dates: str, dates_style: ParagraphStyle) -> None:
        super().__init__()
        self._left = left
        self._dates = dates
        self._style = dates_style
        self._left_height = 0.0
        self.keepWithNext = 1

    def wrap(self, avail_width: float, avail_height: float) -> tuple[float, float]:
        self.width = avail_width
        date_width = (
            pdfmetrics.stringWidth(self._dates, self._style.fontName, self._style.fontSize)
            + _DATE_GAP
            if self._dates
            else 0
        )
        _, self._left_height = self._left.wrap(avail_width - date_width, avail_height)
        self.height = self._left_height
        return self.width, self.height

    def draw(self) -> None:
        self._left.drawOn(self.canv, 0, 0)
        if not self._dates:
            return
        style = self._style
        ascent, _ = pdfmetrics.getAscentDescent(style.fontName, style.fontSize)
        self.canv.setFont(style.fontName, style.fontSize)
        self.canv.setFillColor(style.textColor)
        self.canv.drawRightString(self.width, self._left_height - ascent, self._dates)


def _entry_header(
    left: str, dates: str, styles: dict[str, ParagraphStyle], left_style: str = "body"
) -> _DatedLine:
    return _DatedLine(Paragraph(left, styles[left_style]), dates, styles["dates"])


def _bullets(group: BulletGroup, styles: dict[str, ParagraphStyle]) -> ListFlowable:
    return ListFlowable(
        [ListItem(Paragraph(escape(text), styles["body"])) for text in group.bullets],
        bulletType="bullet",
        start="•",
        bulletFontName="Helvetica",
        bulletFontSize=8,
        leftIndent=11,
    )


def _section(title: str, styles: dict[str, ParagraphStyle]) -> list[object]:
    return [
        Paragraph(escape(title.upper()), styles["section"]),
        HRFlowable(width="100%", thickness=0.6, color=NAVY, spaceBefore=0, spaceAfter=4),
    ]


def render(document: ResumeDocument) -> bytes:
    styles = _styles()
    buffer = io.BytesIO()
    pdf = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=_MARGIN_X,
        rightMargin=_MARGIN_X,
        topMargin=_MARGIN_Y,
        bottomMargin=_MARGIN_Y,
        title=f"{document.name} — Resume",
        author=document.name,
        subject=document.headline,
        creator="someshwaran.dev",
    )

    story: list[object] = [Paragraph(escape(document.name), styles["name"])]
    if document.headline:
        story.append(Paragraph(escape(document.headline), styles["headline"]))
    if document.contact:
        story.append(
            Paragraph(_join([_link_markup(link) for link in document.contact]), styles["contact"])
        )
    if document.summary:
        story += _section("Summary", styles)
        story.append(Paragraph(escape(document.summary), styles["body"]))

    if document.skills:
        story += _section("Skills", styles)
        for line in document.skills:
            story.append(
                Paragraph(
                    f"<b>{escape(line.category)}:</b> {escape(', '.join(line.names))}",
                    styles["body"],
                )
            )

    if document.experience:
        story += _section("Experience", styles)
        for entry in document.experience:
            head: list[object] = [
                _entry_header(escape(entry.role), entry.dates, styles, left_style="role")
            ]
            company = _join([escape(entry.company), escape(entry.location)], ", ")
            if company:
                head.append(Paragraph(company, styles["meta"]))
            for index, group in enumerate(entry.groups):
                block: list[object] = []
                if group.title:
                    block.append(Paragraph(escape(group.title), styles["group"]))
                block.append(_bullets(group, styles))
                if index == 0:
                    # Never strand a role header at the bottom of a page.
                    story.append(KeepTogether([*head, *block[:1]]))
                    story += block[1:]
                else:
                    story += block
            if not entry.groups:
                story.append(KeepTogether(head))
            story.append(Spacer(1, 4))

    if document.projects:
        story += _section("Projects", styles)
        for project in document.projects:
            title = f"<b>{escape(project.name)}</b>"
            if project.tech:
                title += f" — {escape(project.tech)}"
            if project.link:
                title += f" • {_link_markup(project.link)}"
            story.append(Paragraph(title, styles["body"]))
            if project.description:
                story.append(Paragraph(escape(project.description), styles["body"]))

    if document.education:
        story += _section("Education", styles)
        for edu in document.education:
            left = f"<b>{escape(edu.degree)}</b>, {escape(edu.institution)}"
            if edu.field_of_study:
                left += f" — {escape(edu.field_of_study)}"
            story.append(_entry_header(left, edu.years, styles))
            story.append(Spacer(1, 2))

    if document.certifications:
        story += _section("Certifications", styles)
        for cert in document.certifications:
            left = escape(cert.name)
            if cert.issuer:
                left += f", {escape(cert.issuer)}"
            if cert.link:
                left += f" • {_link_markup(cert.link)}"
            story.append(_entry_header(left, cert.date, styles))
            story.append(Spacer(1, 2))

    pdf.build(story)
    return buffer.getvalue()
