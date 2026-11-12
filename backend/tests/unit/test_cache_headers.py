"""Static-file cache headers: hashed assets are immutable, HTML always revalidates."""

from pathlib import Path

from fastapi import FastAPI, Response
from fastapi.testclient import TestClient

from app.core.cache_headers import IMMUTABLE, REVALIDATE, StaticCacheHeadersMiddleware
from app.main import _mount_frontend_if_built


def _client(tmp_path: Path) -> TestClient:
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "index-abc123.js").write_text("console.log(1)")
    (tmp_path / "index.html").write_text("<html><body>hi</body></html>")
    app = FastAPI()

    @app.get("/api/thing")
    def thing() -> dict[str, str]:
        return {"a": "b"}

    @app.get("/api/page", response_class=Response)
    def html_from_api() -> Response:
        return Response("<html></html>", media_type="text/html")

    @app.get("/api/own")
    def own() -> Response:
        return Response("x", headers={"Cache-Control": "private, max-age=5"})

    _mount_frontend_if_built(app, tmp_path)
    app.add_middleware(StaticCacheHeadersMiddleware)
    return TestClient(app)


def test_hashed_assets_are_cached_for_a_year_and_never_revalidated(tmp_path):
    response = _client(tmp_path).get("/assets/index-abc123.js")

    assert response.status_code == 200
    assert response.headers["cache-control"] == IMMUTABLE
    assert "immutable" in IMMUTABLE and "max-age=31536000" in IMMUTABLE


def test_index_html_is_revalidated_on_every_load(tmp_path):
    client = _client(tmp_path)

    assert client.get("/", headers={"Accept": "text/html"}).headers["cache-control"] == REVALIDATE
    # A client-side route is the same HTML via the SPA fallback.
    spa = client.get("/admin/login", headers={"Accept": "text/html"})
    assert spa.headers["cache-control"] == REVALIDATE


def test_missing_assets_and_errors_are_not_cached(tmp_path):
    response = _client(tmp_path).get("/assets/missing.js")

    assert response.status_code == 404
    assert "cache-control" not in response.headers


def test_api_responses_are_left_alone(tmp_path):
    client = _client(tmp_path)

    assert "cache-control" not in client.get("/api/thing").headers
    assert "cache-control" not in client.get("/api/page").headers  # html from /api is not the SPA
    assert (
        client.get("/api/own").headers["cache-control"] == "private, max-age=5"
    )  # never overridden
