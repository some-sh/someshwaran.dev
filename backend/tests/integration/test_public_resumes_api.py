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


def test_export_accepts_the_ats_template_and_rejects_unknown_ones(client, admin_headers):
    _create_and_set_default(client, admin_headers)

    assert client.get("/api/resumes/default/export.pdf?template=ats").status_code == 200
    assert client.get("/api/resumes/default/export.docx?template=ats").status_code == 200
    # An unknown template is a client error, not a crash.
    assert client.get("/api/resumes/default/export.pdf?template=nope").status_code == 422
    assert client.get("/api/resumes/default/export.docx?template=nope").status_code == 422


def test_headline_and_grouped_highlights_reach_the_public_page_data(client, admin_headers):
    payload = _create_payload("With extras") | {
        "headline": "Senior SDET | Python",
        "experience": [
            {
                "company": "Acme",
                "role": "SDET",
                "start_date": "2020-01-01",
                "highlights": [
                    "plain string from an older client",
                    {"text": "grouped bullet", "group": "Platform"},
                ],
            }
        ],
    }
    resume_id = client.post("/api/admin/resumes", json=payload, headers=admin_headers).json()["id"]
    client.post(f"/api/admin/resumes/{resume_id}/set-default", headers=admin_headers)

    body = client.get("/api/resumes/default").json()

    assert body["headline"] == "Senior SDET | Python"
    assert body["experience"][0]["highlights"] == [
        {"text": "plain string from an older client", "group": None},
        {"text": "grouped bullet", "group": "Platform"},
    ]
