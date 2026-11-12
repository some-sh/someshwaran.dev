"""Backup export and import through the real admin routes."""

import json

import pytest
from sqlmodel import Session, select

from app.models.resume import Resume


def _resume(name: str, **extra) -> dict:
    payload = {
        "name": name,
        "headline": "Senior SDET",
        "summary": "Builds things.",
        "personal_info": {
            "full_name": "Ada Lovelace",
            "email": "ada@example.com",
            "linkedin": "linkedin.com/in/ada",
        },
        "skills": [{"name": "c", "category": "L"}, {"name": "a", "category": "L"}, {"name": "b"}],
        "experience": [
            {
                "company": "Acme",
                "role": "SDET",
                "location": "Chennai",
                "start_date": "2019-05-01",
                "highlights": [
                    {"text": "first", "group": "Platform"},
                    {"text": "second", "group": "Platform"},
                    {"text": "third", "group": None},
                ],
            }
        ],
        "projects": [
            {"name": "P", "description": "d", "url": "example.com/p", "tech_stack": ["x"]}
        ],
        "education": [{"institution": "U", "degree": "B.E.", "start_date": "2015-01-01"}],
        "certifications": [{"name": "Cert", "issuer": "Body", "issued_date": "2023-03-09"}],
    }
    payload.update(extra)
    return payload


def _create(client, headers, name: str, default: bool = False) -> int:
    resume_id = client.post("/api/admin/resumes", json=_resume(name), headers=headers).json()["id"]
    if default:
        client.post(f"/api/admin/resumes/{resume_id}/set-default", headers=headers)
    return resume_id


def _normalized(client, headers) -> list[dict]:
    """Every resume's content, without the ids/timestamps the database assigns."""
    out = []
    for summary in client.get("/api/admin/resumes", headers=headers).json():
        full = client.get(f"/api/admin/resumes/{summary['id']}", headers=headers).json()
        out.append(
            json.loads(
                json.dumps(full),
                object_hook=lambda d: {
                    k: v for k, v in d.items() if k not in ("id", "created_at", "updated_at")
                },
            )
        )
    return sorted(out, key=lambda r: r["name"])


def test_backup_routes_require_the_admin_key(client):
    assert client.get("/api/admin/export").status_code in (401, 403)
    assert client.post("/api/admin/import", json={"resumes": []}).status_code in (401, 403)


def test_export_is_a_downloadable_versioned_file_without_database_ids(client, admin_headers):
    _create(client, admin_headers, "One", default=True)

    response = client.get("/api/admin/export", headers=admin_headers)

    assert response.status_code == 200
    assert response.headers["content-disposition"].startswith(
        'attachment; filename="someshwaran-backup-'
    )
    body = response.json()
    assert (body["format"], body["version"]) == ("someshwaran.dev/resume-backup", 1)
    assert body["exported_at"]
    resume = body["resumes"][0]
    assert resume["is_default"] is True
    assert resume["experience"][0]["highlights"][0] == {"text": "first", "group": "Platform"}
    text = response.text
    assert '"id"' not in text and "created_at" not in text and "updated_at" not in text


def test_a_backup_restores_into_an_empty_database_exactly(client, admin_headers):
    _create(client, admin_headers, "One", default=True)
    _create(client, admin_headers, "Two")
    before = _normalized(client, admin_headers)
    backup = client.get("/api/admin/export", headers=admin_headers).json()
    for resume in client.get("/api/admin/resumes", headers=admin_headers).json():
        client.delete(f"/api/admin/resumes/{resume['id']}", headers=admin_headers)
    assert client.get("/api/resumes/default").status_code == 404  # the disaster

    result = client.post("/api/admin/import", json=backup, headers=admin_headers)

    assert result.status_code == 200
    assert len(result.json()["created"]) == 2 and result.json()["skipped"] == []
    assert _normalized(client, admin_headers) == before  # order, groups, headline, everything
    default = client.get("/api/resumes/default").json()
    assert default["name"] == "One" and result.json()["default_id"] == default["id"]


def test_importing_the_same_backup_twice_changes_nothing_the_second_time(client, admin_headers):
    _create(client, admin_headers, "One", default=True)
    backup = client.get("/api/admin/export", headers=admin_headers).json()

    again = client.post("/api/admin/import", json=backup, headers=admin_headers).json()

    assert again["created"] == [] and again["skipped"] == ["One"]
    assert len(client.get("/api/admin/resumes", headers=admin_headers).json()) == 1


def test_import_never_takes_the_default_from_the_current_default(client, admin_headers):
    _create(client, admin_headers, "Mine", default=True)
    backup = {"resumes": [_resume("Imported") | {"is_default": True}]}

    result = client.post("/api/admin/import", json=backup, headers=admin_headers).json()

    assert len(result["created"]) == 1
    assert client.get("/api/resumes/default").json()["name"] == "Mine"


def test_import_sets_the_backups_default_only_when_there_is_none(client, admin_headers):
    _create(client, admin_headers, "Existing")  # not the default
    backup = {"resumes": [_resume("A") | {"is_default": True}, _resume("B") | {"is_default": True}]}

    client.post("/api/admin/import", json=backup, headers=admin_headers)

    assert client.get("/api/resumes/default").json()["name"] == "A"  # first default wins, one only
    defaults = [
        r for r in client.get("/api/admin/resumes", headers=admin_headers).json() if r["is_default"]
    ]
    assert len(defaults) == 1


def test_replace_wipes_existing_resumes_first(client, admin_headers):
    _create(client, admin_headers, "Old", default=True)
    backup = {"resumes": [_resume("New") | {"is_default": True}]}

    result = client.post(
        "/api/admin/import?replace=true", json=backup, headers=admin_headers
    ).json()

    names = [r["name"] for r in client.get("/api/admin/resumes", headers=admin_headers).json()]
    assert names == ["New"] and result["skipped"] == []
    assert client.get("/api/resumes/default").json()["name"] == "New"


def test_without_replace_existing_resumes_are_kept(client, admin_headers):
    _create(client, admin_headers, "Old")

    client.post("/api/admin/import", json={"resumes": [_resume("New")]}, headers=admin_headers)

    names = sorted(
        r["name"] for r in client.get("/api/admin/resumes", headers=admin_headers).json()
    )
    assert names == ["New", "Old"]


@pytest.mark.parametrize(
    "bad_file",
    [
        {
            "resumes": [
                _resume("ok"),
                _resume("bad", personal_info={"full_name": "A", "email": "nope"}),
            ]
        },
        {"resumes": [_resume("bad", summary="x" * 4001)]},
        {
            "resumes": [
                _resume("bad")
                | {
                    "personal_info": {
                        "full_name": "A",
                        "email": "a@b.co",
                        "website": "javascript:alert(1)",
                    }
                }
            ]
        },
        {"format": "something-else", "resumes": []},
        {"version": 2, "resumes": []},
        {},
    ],
)
def test_an_invalid_backup_is_rejected_whole_and_changes_nothing(client, admin_headers, bad_file):
    _create(client, admin_headers, "Keep", default=True)

    response = client.post("/api/admin/import?replace=true", json=bad_file, headers=admin_headers)

    assert response.status_code == 422
    # Even with replace=true, a rejected file must not have deleted anything.
    names = [r["name"] for r in client.get("/api/admin/resumes", headers=admin_headers).json()]
    assert names == ["Keep"]


def test_a_failure_part_way_through_rolls_everything_back(
    client, admin_headers, db_engine, monkeypatch
):
    from app.services import resume_service

    _create(client, admin_headers, "Keep", default=True)
    real = resume_service.build_resume
    calls = {"n": 0}

    def flaky(data):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("boom")
        return real(data)

    monkeypatch.setattr(resume_service, "build_resume", flaky)
    backup = {"resumes": [_resume("One"), _resume("Two"), _resume("Three")]}

    with pytest.raises(RuntimeError):
        client.post("/api/admin/import?replace=true", json=backup, headers=admin_headers)

    with Session(db_engine) as session:
        assert [r.name for r in session.exec(select(Resume)).all()] == ["Keep"]  # untouched
