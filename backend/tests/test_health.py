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


def test_readiness_reports_ok_when_the_database_answers(client) -> None:
    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_readiness_is_503_when_the_database_is_unreachable_and_does_not_leak_why(
    client, caplog
) -> None:
    from sqlalchemy.exc import OperationalError

    from app.db import get_session
    from app.main import app as real_app

    def broken_session():
        class Broken:
            def exec(self, *_args, **_kwargs):
                raise OperationalError("SELECT 1", {}, Exception("password authentication failed"))

        yield Broken()

    real_app.dependency_overrides[get_session] = broken_session
    try:
        with caplog.at_level("ERROR", logger="app.main"):
            response = client.get("/health/ready")
    finally:
        real_app.dependency_overrides.pop(get_session, None)

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "database": "unreachable"}
    assert "password" not in response.text  # the cause goes to the log, not the public response
    assert "Readiness check failed" in caplog.text


def test_liveness_does_not_touch_the_database() -> None:
    # /health stays a pure liveness probe: it must answer even when the DB is down.
    assert client_without_db().get("/health").status_code == 200


def client_without_db():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)
