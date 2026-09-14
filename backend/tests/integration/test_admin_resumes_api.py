"""Integration tests: admin resume routes through the real app/routing
stack (TestClient) against a real temp SQLite file, auth included."""

from app.schemas.resume import PersonalInfoInput, ResumeCreate, SkillInput


def _create_payload(name: str = "Backend-focused") -> dict:
    return ResumeCreate(
        name=name,
        summary="Backend engineer.",
        personal_info=PersonalInfoInput(full_name="Ada Lovelace", email="ada@example.com"),
        skills=[SkillInput(name="Python")],
    ).model_dump(mode="json")


def test_resume_routes_require_admin_auth(client):
    response = client.post("/api/admin/resumes", json=_create_payload())

    assert response.status_code == 401


def test_create_get_update_delete_flow(client, admin_headers):
    created = client.post("/api/admin/resumes", json=_create_payload(), headers=admin_headers)
    assert created.status_code == 201
    resume_id = created.json()["id"]
    assert created.json()["personal_info"]["full_name"] == "Ada Lovelace"

    fetched = client.get(f"/api/admin/resumes/{resume_id}", headers=admin_headers)
    assert fetched.status_code == 200
    assert fetched.json()["name"] == "Backend-focused"

    updated = client.patch(
        f"/api/admin/resumes/{resume_id}",
        json={"summary": "Updated summary."},
        headers=admin_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["summary"] == "Updated summary."

    deleted = client.delete(f"/api/admin/resumes/{resume_id}", headers=admin_headers)
    assert deleted.status_code == 204

    missing = client.get(f"/api/admin/resumes/{resume_id}", headers=admin_headers)
    assert missing.status_code == 404


def test_get_update_delete_missing_resume_is_404(client, admin_headers):
    assert client.get("/api/admin/resumes/999", headers=admin_headers).status_code == 404
    assert (
        client.patch(
            "/api/admin/resumes/999", json={"summary": "x"}, headers=admin_headers
        ).status_code
        == 404
    )
    assert client.delete("/api/admin/resumes/999", headers=admin_headers).status_code == 404


def test_list_resumes_returns_summaries_not_full_content(client, admin_headers):
    client.post("/api/admin/resumes", json=_create_payload("First"), headers=admin_headers)
    client.post("/api/admin/resumes", json=_create_payload("Second"), headers=admin_headers)

    response = client.get("/api/admin/resumes", headers=admin_headers)

    assert response.status_code == 200
    body = response.json()
    assert [r["name"] for r in body] == ["First", "Second"]
    assert "personal_info" not in body[0]


def test_clone_creates_an_independent_copy(client, admin_headers):
    created = client.post("/api/admin/resumes", json=_create_payload(), headers=admin_headers)
    resume_id = created.json()["id"]

    cloned = client.post(f"/api/admin/resumes/{resume_id}/clone", headers=admin_headers)

    assert cloned.status_code == 201
    clone_body = cloned.json()
    assert clone_body["id"] != resume_id
    assert clone_body["name"] == "Backend-focused (copy)"
    assert clone_body["is_default"] is False
    assert clone_body["skills"][0]["name"] == "Python"


def test_clone_missing_resume_is_404(client, admin_headers):
    response = client.post("/api/admin/resumes/999/clone", headers=admin_headers)

    assert response.status_code == 404


def test_set_default_swaps_atomically(client, admin_headers):
    first = client.post(
        "/api/admin/resumes", json=_create_payload("First"), headers=admin_headers
    ).json()
    second = client.post(
        "/api/admin/resumes", json=_create_payload("Second"), headers=admin_headers
    ).json()

    client.post(f"/api/admin/resumes/{first['id']}/set-default", headers=admin_headers)
    client.post(f"/api/admin/resumes/{second['id']}/set-default", headers=admin_headers)

    listing = {
        r["id"]: r["is_default"]
        for r in client.get("/api/admin/resumes", headers=admin_headers).json()
    }
    assert listing[first["id"]] is False
    assert listing[second["id"]] is True


def test_export_pdf_and_docx_return_the_right_content(client, admin_headers):
    resume_id = client.post(
        "/api/admin/resumes", json=_create_payload(), headers=admin_headers
    ).json()["id"]

    pdf = client.get(f"/api/admin/resumes/{resume_id}/export.pdf", headers=admin_headers)
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF")

    docx = client.get(f"/api/admin/resumes/{resume_id}/export.docx", headers=admin_headers)
    assert docx.status_code == 200
    assert docx.content[:2] == b"PK"  # docx is a zip archive


def test_export_missing_resume_is_404(client, admin_headers):
    pdf = client.get("/api/admin/resumes/999/export.pdf", headers=admin_headers)
    docx = client.get("/api/admin/resumes/999/export.docx", headers=admin_headers)

    assert pdf.status_code == 404
    assert docx.status_code == 404
