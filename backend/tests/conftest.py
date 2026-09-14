from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

import app.models  # noqa: F401  ensures tables are registered on metadata
from app.core.config import get_settings
from app.db import get_session
from app.main import app


@pytest.fixture
def session() -> Generator[Session, None, None]:
    """In-memory SQLite DB, schema created directly from current models.

    Fast and isolated — used for unit tests. It does not go through Alembic,
    so it doesn't verify migrations; see tests/integration for that.
    """
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as db_session:
        yield db_session


@pytest.fixture
def client(tmp_path: Path) -> Generator[TestClient, None, None]:
    """FastAPI TestClient against the real app/routing stack, wired to a
    real temporary SQLite file per CLAUDE.md's integration-testing bar
    ("FastAPI TestClient against a real temp SQLite DB"). Schema is
    created directly from current models rather than via Alembic — that
    path is already covered by tests/integration/test_resume_migrations.py.
    """
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)

    def _override_get_session() -> Generator[Session, None, None]:
        with Session(engine) as db_session:
            yield db_session

    app.dependency_overrides[get_session] = _override_get_session
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def admin_headers(monkeypatch: pytest.MonkeyPatch) -> Generator[dict[str, str], None, None]:
    """Authorization header for a valid admin API key, wired through the
    same settings app.core.security.require_admin reads."""
    monkeypatch.setenv("APP_ADMIN_API_KEY", "test-admin-key")
    get_settings.cache_clear()
    yield {"Authorization": "Bearer test-admin-key"}
    get_settings.cache_clear()
