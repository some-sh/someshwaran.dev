"""Unit tests for the display model every export template draws from."""

from datetime import date

import pytest

from app.models.resume import (
    Certification,
    Education,
    Experience,
    PersonalInfo,
    Project,
    Resume,
    Skill,
)
from app.services.resume_document import (
    build_document,
    display_url,
    education_years,
    experience_dates,
    month_year,
    safe_url,
)

# --- dates ---


def test_month_year_uses_fixed_english_names():
    assert month_year(date(2019, 5, 1)) == "May 2019"
    assert month_year(date(2021, 12, 31)) == "Dec 2021"


def test_experience_dates_use_month_and_year_not_iso():
    exp = Experience(
        company="Acme", role="SDET", start_date=date(2019, 5, 1), end_date=date(2021, 12, 31)
    )

    assert experience_dates(exp) == "May 2019 – Dec 2021"


def test_experience_dates_show_present_for_a_current_role():
    exp = Experience(company="Acme", role="SDET", start_date=date(2019, 5, 1))

    assert experience_dates(exp) == "May 2019 – Present"


def test_education_years_show_years_only():
    edu = Education(
        institution="MNM Jain",
        degree="B.E.",
        start_date=date(2015, 1, 1),
        end_date=date(2019, 1, 1),
    )

    assert education_years(edu) == "2015 – 2019"


def test_education_years_handle_missing_and_equal_years():
    assert education_years(Education(institution="X", degree="Y")) == ""
    assert education_years(Education(institution="X", degree="Y", end_date=date(2019, 6, 1))) == (
        "2019"
    )
    same = Education(
        institution="X", degree="Y", start_date=date(2019, 1, 1), end_date=date(2019, 12, 1)
    )
    assert education_years(same) == "2019"


# --- links ---


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("https://example.com/a", "https://example.com/a"),
        ("http://example.com", "http://example.com"),
        ("linkedin.com/in/someone", "https://linkedin.com/in/someone"),  # bare host gets https
        ("mailto:a@example.com", "mailto:a@example.com"),
        ("javascript:alert(1)", None),
        ("JAVASCRIPT:alert(1)", None),
        ("data:text/html,<script>1</script>", None),
        ("file:///etc/passwd", None),
        ("ftp://example.com/x", None),
        ("https://", None),  # no host
        ("example.com:8080/x", "https://example.com:8080/x"),  # host:port is a host, not a scheme
        ("", None),
        ("   ", None),
        (None, None),
    ],
)
def test_safe_url_only_allows_http_https_and_mailto(value, expected):
    assert safe_url(value) == expected


def test_display_url_drops_scheme_www_and_trailing_slash():
    assert display_url("https://www.linkedin.com/in/someone/") == "linkedin.com/in/someone"
    assert display_url("http://example.com") == "example.com"
    assert display_url("someshwaran.dev") == "someshwaran.dev"


def _resume(**overrides) -> Resume:
    values = {
        "name": "internal label",
        "personal_info": PersonalInfo(
            full_name="Ada Lovelace",
            email="ada@example.com",
            phone="+1 555 0100",
            location="London",
            website="https://www.ada.example/",
            github="github.com/ada",
            linkedin="https://www.linkedin.com/in/ada",
        ),
    }
    values.update(overrides)
    return Resume(**values)


def test_contact_items_are_ordered_and_linked_where_safe():
    contact = build_document(_resume()).contact

    assert [c.text for c in contact] == [
        "ada@example.com",
        "+1 555 0100",
        "London",
        "ada.example",
        "github.com/ada",
        "linkedin.com/in/ada",
    ]
    assert [c.url for c in contact] == [
        "mailto:ada@example.com",
        None,
        None,
        "https://www.ada.example/",
        "https://github.com/ada",
        "https://www.linkedin.com/in/ada",
    ]


def test_an_unsafe_url_is_shown_as_text_and_never_linked():
    info = PersonalInfo(full_name="A", email="a@example.com", website="javascript:alert(1)")

    contact = build_document(_resume(personal_info=info)).contact

    website = contact[-1]
    assert website.text == "javascript:alert(1)"
    assert website.url is None


def test_name_falls_back_to_the_internal_label_without_personal_info():
    document = build_document(Resume(name="Fallback label"))

    assert document.name == "Fallback label"
    assert document.contact == ()


# --- bullets and groups ---


def _experience(highlights) -> Experience:
    return Experience(
        company="Acme", role="SDET", start_date=date(2020, 1, 1), highlights=highlights
    )


def test_consecutive_bullets_with_the_same_group_are_gathered_under_it():
    resume = _resume(
        experience=[
            _experience(
                [
                    {"text": "a", "group": "Platform"},
                    {"text": "b", "group": "Platform"},
                    {"text": "c", "group": "Quality"},
                    {"text": "d", "group": "Platform"},  # not adjacent: a new group
                ]
            )
        ]
    )

    groups = build_document(resume).experience[0].groups

    assert [(g.title, g.bullets) for g in groups] == [
        ("Platform", ("a", "b")),
        ("Quality", ("c",)),
        ("Platform", ("d",)),
    ]


def test_ungrouped_and_legacy_string_bullets_form_one_untitled_group():
    resume = _resume(experience=[_experience(["old string", {"text": "new", "group": None}])])

    groups = build_document(resume).experience[0].groups

    assert [(g.title, g.bullets) for g in groups] == [(None, ("old string", "new"))]


def test_blank_bullets_and_blank_group_names_are_ignored():
    resume = _resume(
        experience=[
            _experience([{"text": "  ", "group": "G"}, {"text": " keep ", "group": "   "}, "  "])
        ]
    )

    groups = build_document(resume).experience[0].groups

    assert [(g.title, g.bullets) for g in groups] == [(None, ("keep",))]


# --- the rest of the document ---


def test_skills_are_gathered_by_category_with_a_general_fallback():
    resume = _resume(
        skills=[
            Skill(name="Python", category="Languages"),
            Skill(name="Go", category="Languages"),
            Skill(name="Docker"),
        ]
    )

    skills = build_document(resume).skills

    assert [(s.category, s.names) for s in skills] == [
        ("Languages", ("Python", "Go")),
        ("General", ("Docker",)),
    ]


def test_projects_and_certifications_get_formatted_text_and_safe_links():
    resume = _resume(
        projects=[
            Project(name="P", description=" desc ", tech_stack=["A", "B"], url="example.com/p")
        ],
        certifications=[
            Certification(
                name="Cert",
                issuer="Body",
                issued_date=date(2023, 3, 9),
                url="javascript:alert(1)",
            )
        ],
    )

    document = build_document(resume)

    project = document.projects[0]
    assert (project.tech, project.description) == ("A, B", "desc")
    assert project.link is not None
    assert (project.link.text, project.link.url) == ("example.com/p", "https://example.com/p")
    cert = document.certifications[0]
    assert (cert.issuer, cert.date) == ("Body", "Mar 2023")
    assert cert.link is not None and cert.link.url is None  # unsafe: text only


def test_headline_and_summary_are_trimmed():
    document = build_document(_resume(headline="  Senior SDET  ", summary="\n summary \n"))

    assert (document.headline, document.summary) == ("Senior SDET", "summary")
