"""Security headers, and that API docs are off unless explicitly enabled."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.security_headers import CONTENT_SECURITY_POLICY, SecurityHeadersMiddleware
from app.main import app as real_app


def _app() -> FastAPI:
    app = FastAPI()

    @app.get("/page")
    def page() -> dict[str, str]:
        return {"ok": "yes"}

    @app.get("/api/admin/thing")
    def admin_thing() -> dict[str, str]:
        return {"secret": "data"}

    @app.get("/docs")
    def docs() -> dict[str, str]:
        return {"docs": "page"}

    @app.get("/already")
    def already() -> dict[str, str]:  # sets its own Cache-Control
        from fastapi import Response

        return Response(headers={"Cache-Control": "public, max-age=60"})  # type: ignore[return-value]

    app.add_middleware(SecurityHeadersMiddleware)
    return app


def test_every_response_gets_the_baseline_headers():
    response = TestClient(_app()).get("/page")

    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert "camera=()" in response.headers["permissions-policy"]
    assert response.headers["cross-origin-opener-policy"] == "same-origin"
    assert response.headers["content-security-policy"] == CONTENT_SECURITY_POLICY


def test_the_csp_blocks_framing_plugins_and_third_party_scripts():
    csp = CONTENT_SECURITY_POLICY

    assert "default-src 'self'" in csp
    assert "script-src 'self'" in csp  # no 'unsafe-inline', no 'unsafe-eval', no CDNs
    assert "frame-ancestors 'none'" in csp
    assert "object-src 'none'" in csp
    assert "base-uri 'none'" in csp
    assert "unsafe" not in csp


def test_hsts_is_sent_only_over_https():
    client = TestClient(_app())

    assert "strict-transport-security" not in client.get("/page").headers
    forwarded = client.get("/page", headers={"X-Forwarded-Proto": "https"})
    assert forwarded.headers["strict-transport-security"] == "max-age=15552000"
    secure = TestClient(_app(), base_url="https://testserver").get("/page")
    assert "strict-transport-security" in secure.headers


def test_admin_responses_are_never_cached():
    client = TestClient(_app())

    assert client.get("/api/admin/thing").headers["cache-control"] == "no-store"
    assert "cache-control" not in client.get("/page").headers


def test_a_handlers_own_header_is_not_overridden():
    response = TestClient(_app()).get("/already")

    assert response.headers["cache-control"] == "public, max-age=60"


def test_the_docs_paths_get_no_csp_so_swagger_can_load_when_enabled():
    response = TestClient(_app()).get("/docs")

    assert "content-security-policy" not in response.headers
    assert response.headers["x-content-type-options"] == "nosniff"  # the rest still applies


def test_the_real_app_sends_the_headers_and_hides_its_docs_by_default():
    client = TestClient(real_app)

    health = client.get("/health")
    assert health.headers["content-security-policy"] == CONTENT_SECURITY_POLICY
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 404


def test_the_headers_are_on_error_responses_too():
    response = TestClient(real_app).get("/api/admin/whoami")  # no key: 401/403

    assert response.status_code in (401, 403)
    assert response.headers["content-security-policy"] == CONTENT_SECURITY_POLICY
    assert response.headers["cache-control"] == "no-store"
