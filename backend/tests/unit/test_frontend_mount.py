"""Unit tests for the SPA-serving mount. Each test builds a fresh
FastAPI() instance rather than using the real app.main.app singleton, so
these don't depend on whether backend/frontend_dist/ happens to exist on
disk (it never does in CI — only scripts/deploy.sh creates it, right
before a deploy)."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import _mount_frontend_if_built


def test_serves_index_html_at_root_when_built(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<html><body>Hello</body></html>")
    app = FastAPI()
    _mount_frontend_if_built(app, tmp_path)

    response = TestClient(app).get("/")

    assert response.status_code == 200
    assert "Hello" in response.text


def test_falls_back_to_index_html_for_a_client_side_route(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<html><body>Hello</body></html>")
    app = FastAPI()
    _mount_frontend_if_built(app, tmp_path)

    # No file at this path — a client-side (TanStack Router) route. The
    # fallback only kicks in for requests that accept HTML (i.e. an
    # actual browser navigation, not an asset or API request), so this
    # has to declare that explicitly — TestClient's default Accept
    # header doesn't.
    response = TestClient(app).get("/admin/login", headers={"Accept": "text/html"})

    assert response.status_code == 200
    assert "Hello" in response.text


def test_never_shadows_a_real_route(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<html><body>Hello</body></html>")
    app = FastAPI()

    @app.get("/api/ping")
    def ping() -> dict[str, str]:
        return {"status": "ok"}

    _mount_frontend_if_built(app, tmp_path)

    response = TestClient(app).get("/api/ping")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_is_a_noop_when_the_directory_does_not_exist(tmp_path: Path) -> None:
    app = FastAPI()
    _mount_frontend_if_built(app, tmp_path / "does-not-exist")

    response = TestClient(app).get("/")

    assert response.status_code == 404


def test_root_is_404_on_the_real_app_when_frontend_is_not_built() -> None:
    """Guards the assumption every other test in this suite relies on:
    the real app never has a built frontend in this environment, so "/"
    genuinely exercises the no-frontend path, not a stray local build."""
    from app.main import app as real_app

    response = TestClient(real_app).get("/")

    assert response.status_code == 404
