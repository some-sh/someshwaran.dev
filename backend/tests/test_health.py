from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main as app_main
from app.main import app

client = TestClient(app)


def test_health_check_returns_ok() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    # frontend_dist/ is never built in CI/unit runs, so it reports unmounted.
    assert body["frontend_mounted"] is False
    assert body["frontend_dir"].endswith("frontend_dist")


def test_health_reports_frontend_mounted_when_built(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(app_main, "_FRONTEND_DIR", tmp_path)

    body = client.get("/health").json()

    assert body["frontend_mounted"] is True
    assert body["frontend_dir"] == str(tmp_path)
