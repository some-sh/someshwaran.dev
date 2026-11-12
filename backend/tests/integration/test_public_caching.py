"""HTTP caching of the public resume endpoints, through the real routes:
ETag + revalidation, 304s, the cost of each kind of request in database
queries, and — most important — that an edit is visible immediately."""

import pytest
from sqlalchemy import event

from app.services import export_service
from app.services.response_cache import render_cache


def _payload(name: str = "Cached") -> dict:
    return {
        "name": name,
        "headline": "First headline",
        "personal_info": {"full_name": "Ada Lovelace", "email": "ada@example.com"},
        "skills": [{"name": "Python", "category": "Languages"}],
    }


@pytest.fixture
def published(client, admin_headers) -> int:
    resume_id = client.post("/api/admin/resumes", json=_payload(), headers=admin_headers).json()[
        "id"
    ]
    client.post(f"/api/admin/resumes/{resume_id}/set-default", headers=admin_headers)
    return resume_id


class QueryCounter:
    def __init__(self, engine) -> None:
        self.count = 0
        event.listen(engine, "before_cursor_execute", self._on)
        self._engine = engine

    def _on(self, *args) -> None:
        self.count += 1

    def reset(self) -> int:
        seen, self.count = self.count, 0
        return seen


@pytest.mark.parametrize(
    "path",
    ["/api/resumes/default", "/api/resumes/default/export.pdf", "/api/resumes/default/export.docx"],
)
def test_public_responses_carry_an_etag_and_must_revalidate(client, published, path):
    response = client.get(path)

    assert response.status_code == 200
    assert response.headers["etag"].startswith('"')
    assert response.headers["cache-control"] == "public, no-cache"


@pytest.mark.parametrize(
    "path",
    ["/api/resumes/default", "/api/resumes/default/export.pdf", "/api/resumes/default/export.docx"],
)
def test_a_matching_if_none_match_gets_a_304_with_no_body(client, published, path):
    etag = client.get(path).headers["etag"]

    again = client.get(path, headers={"If-None-Match": etag})

    assert again.status_code == 304
    assert again.content == b""
    assert again.headers["etag"] == etag
    assert again.headers["cache-control"] == "public, no-cache"


def test_the_json_body_is_identical_whether_cached_or_not(client, published):
    first = client.get("/api/resumes/default")
    render_cache.clear()
    uncached = client.get("/api/resumes/default")
    cached = client.get("/api/resumes/default")

    assert first.content == uncached.content == cached.content
    assert first.json()["headline"] == "First headline"


def test_an_edit_is_visible_on_the_very_next_request(client, admin_headers, published):
    before = client.get("/api/resumes/default")
    pdf_before = client.get("/api/resumes/default/export.pdf")

    client.patch(
        f"/api/admin/resumes/{published}",
        json={"headline": "Second headline"},
        headers=admin_headers,
    )

    after = client.get("/api/resumes/default", headers={"If-None-Match": before.headers["etag"]})
    pdf_after = client.get(
        "/api/resumes/default/export.pdf", headers={"If-None-Match": pdf_before.headers["etag"]}
    )
    # The old ETag no longer matches: a 200 with the new content, never a 304.
    assert after.status_code == 200
    assert after.json()["headline"] == "Second headline"
    assert after.headers["etag"] != before.headers["etag"]
    assert pdf_after.status_code == 200
    assert pdf_after.headers["etag"] != pdf_before.headers["etag"]
    assert pdf_after.content != pdf_before.content


def test_changing_which_resume_is_the_default_is_visible_immediately(
    client, admin_headers, published
):
    other = client.post("/api/admin/resumes", json=_payload("Other"), headers=admin_headers).json()[
        "id"
    ]
    etag = client.get("/api/resumes/default").headers["etag"]

    client.post(f"/api/admin/resumes/{other}/set-default", headers=admin_headers)

    response = client.get("/api/resumes/default", headers={"If-None-Match": etag})
    assert response.status_code == 200
    assert response.json()["id"] == other


def test_revalidating_costs_one_narrow_query_and_a_hit_skips_the_nested_loads(
    client, db_engine, published
):
    counter = QueryCounter(db_engine)
    client.get("/api/resumes/default")  # cold: stamp + resume + six sections
    cold = counter.reset()
    client.get("/api/resumes/default")  # warm: stamp only
    warm = counter.reset()
    etag = client.get("/api/resumes/default").headers["etag"]
    counter.reset()
    client.get("/api/resumes/default", headers={"If-None-Match": etag})  # revalidation
    revalidation = counter.reset()

    assert cold >= 7  # the nested sections load once...
    assert warm == 1  # ...and not again until the resume changes
    assert revalidation == 1


def test_a_cache_hit_does_not_render_again(client, published, monkeypatch):
    renders: list[int] = []
    real = export_service.render_resume_pdf

    def counting(resume, template="ats"):
        renders.append(1)
        return real(resume, template)

    monkeypatch.setattr(export_service, "render_resume_pdf", counting)

    for _ in range(3):
        assert client.get("/api/resumes/default/export.pdf").status_code == 200

    assert len(renders) == 1


def test_a_changed_template_version_invalidates_cached_output(client, published, monkeypatch):
    from app.services import response_cache

    first = client.get("/api/resumes/default/export.pdf").headers["etag"]
    monkeypatch.setattr(response_cache, "RENDER_FINGERPRINT", "deployed-a-new-template")

    assert client.get("/api/resumes/default/export.pdf").headers["etag"] != first


def test_no_default_is_still_404_and_unknown_templates_still_422(client):
    assert client.get("/api/resumes/default").status_code == 404
    assert client.get("/api/resumes/default/export.pdf").status_code == 404
    assert client.get("/api/resumes/default/export.pdf?template=nope").status_code in (404, 422)


def test_admin_exports_stay_no_store_and_are_not_given_validators(client, admin_headers, published):
    response = client.get(f"/api/admin/resumes/{published}/export.pdf", headers=admin_headers)

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert "etag" not in response.headers
    assert response.headers["content-disposition"].startswith('attachment; filename="cached.pdf"')
