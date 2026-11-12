"""Unit tests for the resume CRUD service, against a mocked (in-memory) DB."""

from app.schemas.resume import (
    CertificationInput,
    EducationInput,
    ExperienceInput,
    PersonalInfoInput,
    ProjectInput,
    ResumeCreate,
    ResumeUpdate,
    SkillInput,
)
from app.services import resume_service


def _sample_create(name: str = "Backend-focused") -> ResumeCreate:
    return ResumeCreate(
        name=name,
        summary="Backend engineer.",
        personal_info=PersonalInfoInput(full_name="Ada Lovelace", email="ada@example.com"),
        skills=[SkillInput(name="Python"), SkillInput(name="Go", category="Languages")],
        experience=[
            ExperienceInput(
                company="Acme",
                role="SDET",
                start_date="2022-01-01",
                highlights=["Built the test framework"],
            )
        ],
        projects=[ProjectInput(name="OpTools", description="Internal tooling")],
        education=[EducationInput(institution="State U", degree="BS")],
        certifications=[CertificationInput(name="AWS SAA")],
    )


def test_create_resume_persists_nested_content(session):
    resume = resume_service.create_resume(session, _sample_create())

    assert resume.id is not None
    assert resume.personal_info is not None
    assert resume.personal_info.full_name == "Ada Lovelace"
    assert [s.name for s in resume.skills] == ["Python", "Go"]
    assert resume.experience[0].company == "Acme"
    # Stored structured; plain strings are accepted on input.
    assert resume.experience[0].highlights == [{"text": "Built the test framework", "group": None}]
    assert resume.projects[0].name == "OpTools"
    assert resume.education[0].institution == "State U"
    assert resume.certifications[0].name == "AWS SAA"


def test_get_resume_returns_none_for_missing_id(session):
    assert resume_service.get_resume(session, 999) is None


def test_list_resumes_orders_by_created_at(session):
    first = resume_service.create_resume(session, _sample_create("First"))
    second = resume_service.create_resume(session, _sample_create("Second"))

    resumes = resume_service.list_resumes(session)

    assert [r.id for r in resumes] == [first.id, second.id]


def test_update_resume_patches_scalars_without_touching_omitted_fields(session):
    resume = resume_service.create_resume(session, _sample_create())

    updated = resume_service.update_resume(
        session, resume.id, ResumeUpdate(summary="Updated summary.")
    )

    assert updated is not None
    assert updated.name == resume.name  # untouched, not passed in the update
    assert updated.summary == "Updated summary."


def test_update_resume_replaces_nested_collection_wholesale(session):
    resume = resume_service.create_resume(session, _sample_create())

    updated = resume_service.update_resume(
        session,
        resume.id,
        ResumeUpdate(skills=[SkillInput(name="Rust")]),
    )

    assert updated is not None
    assert [s.name for s in updated.skills] == ["Rust"]


def test_update_resume_returns_none_for_missing_id(session):
    assert resume_service.update_resume(session, 999, ResumeUpdate(name="x")) is None


def test_delete_resume_removes_it_and_cascades_nested_rows(session):
    resume = resume_service.create_resume(session, _sample_create())
    resume_id = resume.id

    deleted = resume_service.delete_resume(session, resume_id)

    assert deleted is True
    assert resume_service.get_resume(session, resume_id) is None


def test_delete_resume_returns_false_for_missing_id(session):
    assert resume_service.delete_resume(session, 999) is False


def test_get_default_resume_returns_none_when_unset(session):
    resume_service.create_resume(session, _sample_create())

    assert resume_service.get_default_resume(session) is None


def test_set_default_resume_is_exclusive(session):
    first = resume_service.create_resume(session, _sample_create("First"))
    second = resume_service.create_resume(session, _sample_create("Second"))

    resume_service.set_default_resume(session, first.id)
    resume_service.set_default_resume(session, second.id)

    assert resume_service.get_resume(session, first.id).is_default is False
    assert resume_service.get_resume(session, second.id).is_default is True
    assert resume_service.get_default_resume(session).id == second.id


def test_set_default_resume_returns_none_for_missing_id(session):
    assert resume_service.set_default_resume(session, 999) is None


def test_clone_resume_copies_nested_content_independently(session):
    original = resume_service.create_resume(session, _sample_create())
    resume_service.set_default_resume(session, original.id)

    clone = resume_service.clone_resume(session, original.id)

    assert clone is not None
    assert clone.id != original.id
    assert clone.name == "Backend-focused (copy)"
    assert clone.is_default is False  # never inherits the source's default flag
    assert [s.name for s in clone.skills] == [s.name for s in original.skills]

    # Editing the clone doesn't touch the original's rows.
    clone.skills[0].name = "Rust"
    session.add(clone)
    session.commit()
    assert resume_service.get_resume(session, original.id).skills[0].name == "Python"


def test_clone_resume_returns_none_for_missing_id(session):
    assert resume_service.clone_resume(session, 999) is None


# --- section order is stored explicitly (order_index), never left to the DB ---


def test_create_assigns_positions_in_input_order(session):
    data = _sample_create()
    data.skills = [SkillInput(name=n) for n in ("c", "a", "b")]

    resume = resume_service.create_resume(session, data)

    # Not alphabetical, not all 0: the position is the input position.
    assert [(s.name, s.order_index) for s in resume.skills] == [("c", 0), ("a", 1), ("b", 2)]


def test_update_reassigns_positions_for_a_replaced_section(session):
    resume = resume_service.create_resume(session, _sample_create())

    updated = resume_service.update_resume(
        session,
        resume.id,
        ResumeUpdate(skills=[SkillInput(name="z"), SkillInput(name="y")]),
    )

    assert updated is not None
    assert [(s.name, s.order_index) for s in updated.skills] == [("z", 0), ("y", 1)]


def test_clone_preserves_section_order(session):
    data = _sample_create()
    data.skills = [SkillInput(name=n) for n in ("c", "a", "b")]
    source = resume_service.create_resume(session, data)

    clone = resume_service.clone_resume(session, source.id)

    assert clone is not None
    assert [(s.name, s.order_index) for s in clone.skills] == [("c", 0), ("a", 1), ("b", 2)]


def test_ties_in_order_index_still_sort_by_id(session):
    """Rows created before positions were recorded all have order_index 0."""
    from app.models.resume import Skill

    resume = resume_service.create_resume(session, _sample_create())
    for skill in list(resume.skills):
        skill.order_index = 0
        session.add(skill)
    session.commit()
    session.refresh(resume)

    assert [s.name for s in resume.skills] == ["Python", "Go"]
    assert isinstance(resume.skills[0], Skill)


# --- "at most one default" ---


def test_a_second_default_is_rejected_by_the_database(session):
    import pytest
    from sqlalchemy.exc import IntegrityError

    first = resume_service.create_resume(session, _sample_create("one"))
    second = resume_service.create_resume(session, _sample_create("two"))
    resume_service.set_default_resume(session, first.id)

    second.is_default = True  # bypasses set_default_resume on purpose
    session.add(second)
    with pytest.raises(IntegrityError):
        session.commit()


def test_set_default_moves_the_default_without_tripping_the_index(session):
    first = resume_service.create_resume(session, _sample_create("one"))
    second = resume_service.create_resume(session, _sample_create("two"))

    resume_service.set_default_resume(session, first.id)
    resume_service.set_default_resume(session, second.id)
    resume_service.set_default_resume(session, second.id)  # idempotent

    defaults = [r for r in resume_service.list_resumes(session) if r.is_default]
    assert [r.name for r in defaults] == ["two"]


# --- headline and grouped highlights ---


def test_headline_is_stored_updated_and_cloned(session):
    data = _sample_create()
    data.headline = "Senior SDET | Python, Playwright"
    resume = resume_service.create_resume(session, data)
    assert resume.headline == "Senior SDET | Python, Playwright"

    updated = resume_service.update_resume(session, resume.id, ResumeUpdate(headline="New"))
    assert updated is not None and updated.headline == "New"

    unchanged = resume_service.update_resume(session, resume.id, ResumeUpdate(summary="s"))
    assert unchanged is not None and unchanged.headline == "New"  # omitted = untouched

    clone = resume_service.clone_resume(session, resume.id)
    assert clone is not None and clone.headline == "New"


def test_highlights_keep_their_group_and_accept_plain_strings(session):
    data = _sample_create()
    data.experience = [
        ExperienceInput(
            company="Acme",
            role="SDET",
            start_date="2022-01-01",
            highlights=[
                "plain string, as older clients send it",
                {"text": "grouped", "group": "Platform"},
            ],
        )
    ]

    resume = resume_service.create_resume(session, data)

    assert resume.experience[0].highlights == [
        {"text": "plain string, as older clients send it", "group": None},
        {"text": "grouped", "group": "Platform"},
    ]


def test_normalize_highlights_reads_every_stored_shape():
    from app.schemas.resume import Highlight, normalize_highlights

    result = normalize_highlights(
        ["old row", {"text": "new row", "group": "G"}, Highlight(text="obj")]
    )

    assert [(h.text, h.group) for h in result] == [
        ("old row", None),
        ("new row", "G"),
        ("obj", None),
    ]
    assert normalize_highlights(None) == []
