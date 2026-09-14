"""Integration tests: public resume routes (no auth) through the real
app/routing stack."""

from app.schemas.resume import PersonalInfoInput, ResumeCreate


def _create_payload(name: str = "Public resume") -> dict:
    return ResumeCreate(
        name=name,
        personal_info=PersonalInfoInput(full_name="Grace Hopper", email="grace@example.com"),
    ).model_dump(mode="json")


def _create_and_set_default(client, admin_headers, name: str = "Public resume") -> int:
    resume_id = client.post(
        "/api/admin/resumes", json=_create_payload(name), headers=admin_headers
    ).json()["id"]
    client.post(f"/api/admin/resumes/{resume_id}/set-default", headers=admin_headers)
    return resume_id


def test_no_default_resume_is_404(client):
    assert client.get("/api/resumes/default").status_code == 404
    assert client.get("/api/resumes/default/export.pdf").status_code == 404
    assert client.get("/api/resumes/default/export.docx").status_code == 404


def test_default_resume_is_served_once_set(client, admin_headers):
    _create_and_set_default(client, admin_headers)

    response = client.get("/api/resumes/default")

    assert response.status_code == 200
    assert response.json()["personal_info"]["full_name"] == "Grace Hopper"


def test_non_default_resume_is_not_exposed_publicly(client, admin_headers):
    _create_and_set_default(client, admin_headers, "First")
    client.post(
        "/api/admin/resumes", json=_create_payload("Second, not default"), headers=admin_headers
    )

    response = client.get("/api/resumes/default")

    assert response.json()["name"] == "First"


def test_default_resume_export_pdf_and_docx(client, admin_headers):
    _create_and_set_default(client, admin_headers)

    pdf = client.get("/api/resumes/default/export.pdf")
    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF")

    docx = client.get("/api/resumes/default/export.docx")
    assert docx.status_code == 200
    assert docx.content[:2] == b"PK"
