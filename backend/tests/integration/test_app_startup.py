"""Integration test: the app boots against its own configured database
(not the dependency-overridden tests/conftest.py `client` fixture) and
can immediately serve a DB-backed route.

Regression test for a real production bug: the default
``sqlite:///./data/app.db`` points at a directory that doesn't exist on a
fresh checkout or deploy (``data/`` is gitignored, nothing ever created
it), and SQLite doesn't create missing parent directories on its own —
every DB-backed route 500'd with "unable to open database file" until
app.db.ensure_sqlite_directory_exists and the startup migration
(app/main.py's lifespan) were added.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.db import get_engine


def test_app_serves_a_db_backed_route_on_a_fresh_nested_db_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "nested" / "app.db"
    assert not db_path.parent.exists()  # the exact scenario that broke in production

    monkeypatch.setenv("APP_DATABASE_URL", f"sqlite:///{db_path}")
    get_settings.cache_clear()
    get_engine.cache_clear()

    try:
        from app.main import app

        # `with` is required: it's what actually runs the app's lifespan
        # (and therefore the startup migration) — a plain TestClient(app)
        # does not, which is exactly why this bug wasn't caught by any of
        # the other tests, all of which use the plain form.
        with TestClient(app) as client:
            response = client.get("/api/resumes/default")

        # 404 (no default resume set yet), not 500 (couldn't open the DB).
        assert response.status_code == 404
        assert db_path.exists()
    finally:
        get_settings.cache_clear()
        get_engine.cache_clear()
