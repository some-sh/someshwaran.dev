"""Write-side limits and link checks (ResumeCreate / ResumeUpdate), and that
reads are NOT constrained, so anything already stored always loads."""

from datetime import date

import pytest
from pydantic import ValidationError

from app.schemas.resume import (
    ExperienceRead,
    PersonalInfoInput,
    ResumeCreate,
    ResumeUpdate,
)


def _create(**overrides) -> dict:
    data = {
        "name": "Resume",
        "personal_info": {"full_name": "Ada Lovelace", "email": "ada@example.com"},
    }
    data.update(overrides)
    return data


def test_a_normal_resume_is_accepted():
    ResumeCreate.model_validate(
        _create(
            headline="Senior SDET | Python",
            summary="Builds test infrastructure.",
            skills=[{"name": "Python", "category": "Languages"}],
            experience=[
                {
                    "company": "Acme",
                    "role": "SDET",
                    "start_date": "2020-01-01",
                    "highlights": ["plain", {"text": "grouped", "group": "G"}],
                }
            ],
        )
    )


@pytest.mark.parametrize(
    "overrides",
    [
        {"name": ""},  # a resume needs a name
        {"name": "x" * 201},
        {"headline": "x" * 301},
        {"summary": "x" * 4001},
        {"skills": [{"name": "s"}] * 201},
        {"experience": [{"company": "c", "role": "r", "start_date": "2020-01-01"}] * 51},
        {"projects": [{"name": "p"}] * 51},
        {"education": [{"institution": "i", "degree": "d"}] * 21},
        {"certifications": [{"name": "c"}] * 51},
    ],
)
def test_oversized_or_empty_top_level_values_are_rejected(overrides):
    with pytest.raises(ValidationError):
        ResumeCreate.model_validate(_create(**overrides))


@pytest.mark.parametrize(
    "info",
    [
        {"full_name": "", "email": "a@example.com"},
        {"full_name": "A", "email": "not-an-email"},
        {"full_name": "A", "email": "a@example.com", "phone": "1" * 51},
        {"full_name": "A", "email": "a@example.com", "location": "x" * 201},
    ],
)
def test_personal_info_limits_and_email_format(info):
    with pytest.raises(ValidationError):
        PersonalInfoInput.model_validate(info)


def test_nested_text_limits():
    too_long = [
        {"skills": [{"name": "x" * 101}]},
        {"experience": [{"company": "c" * 201, "role": "r", "start_date": "2020-01-01"}]},
        {
            "experience": [
                {
                    "company": "c",
                    "role": "r",
                    "start_date": "2020-01-01",
                    "highlights": ["x" * 1001],
                }
            ]
        },
        {
            "experience": [
                {
                    "company": "c",
                    "role": "r",
                    "start_date": "2020-01-01",
                    "highlights": [{"text": "t", "group": "g" * 201}],
                }
            ]
        },
        {
            "experience": [
                {
                    "company": "c",
                    "role": "r",
                    "start_date": "2020-01-01",
                    "highlights": ["b"] * 51,
                }
            ]
        },
        {"projects": [{"name": "p", "description": "d" * 3001}]},
        {"projects": [{"name": "p", "tech_stack": ["t"] * 51}]},
        {"projects": [{"name": "p", "tech_stack": ["t" * 61]}]},
    ]
    for overrides in too_long:
        with pytest.raises(ValidationError):
            ResumeCreate.model_validate(_create(**overrides))


@pytest.mark.parametrize(
    "link",
    [
        "javascript:alert(1)",
        "JAVASCRIPT:alert(1)",
        "data:text/html,<script>1</script>",
        "file:///etc/passwd",
        "ftp://example.com/x",
        "https://",
        "https://example.com/" + "a" * 2000,
    ],
)
def test_unsafe_or_oversized_links_are_rejected_everywhere_they_can_be_written(link):
    for personal in ("website", "github", "linkedin"):
        info = {"full_name": "A", "email": "a@example.com", personal: link}
        with pytest.raises(ValidationError):
            PersonalInfoInput.model_validate(info)
    with pytest.raises(ValidationError):
        ResumeCreate.model_validate(_create(projects=[{"name": "p", "url": link}]))
    with pytest.raises(ValidationError):
        ResumeCreate.model_validate(_create(certifications=[{"name": "c", "url": link}]))


@pytest.mark.parametrize(
    "link", ["https://example.com/a", "linkedin.com/in/someone", "example.com:8080/x"]
)
def test_http_links_and_bare_hosts_are_accepted(link):
    info = PersonalInfoInput.model_validate(
        {"full_name": "A", "email": "a@example.com", "linkedin": link}
    )

    assert info.linkedin == link


def test_blank_links_mean_none():
    info = PersonalInfoInput.model_validate(
        {"full_name": "A", "email": "a@example.com", "website": "   ", "github": ""}
    )

    assert info.website is None and info.github is None


def test_text_is_trimmed():
    data = ResumeCreate.model_validate(_create(name="  Padded  "))

    assert data.name == "Padded"


def test_update_applies_the_same_limits_when_a_field_is_present():
    ResumeUpdate.model_validate({})  # nothing set is fine
    with pytest.raises(ValidationError):
        ResumeUpdate.model_validate({"summary": "x" * 4001})
    with pytest.raises(ValidationError):
        ResumeUpdate.model_validate({"personal_info": {"full_name": "A", "email": "nope"}})


def test_reads_are_not_constrained_so_old_data_always_loads():
    """Limits apply to writes only: a row stored before a limit existed (or by
    a path that bypassed it) must still be servable."""
    read = ExperienceRead.model_validate(
        {
            "id": 1,
            "company": "c" * 500,
            "role": "r",
            "start_date": date(2020, 1, 1),
            "highlights": ["x" * 5000],
        }
    )

    assert len(read.company) == 500
    assert len(read.highlights[0].text) == 5000
