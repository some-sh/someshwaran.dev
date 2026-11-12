from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlmodel import Session, SQLModel, create_engine

import app.models  # noqa: F401  ensures tables are registered on metadata
from app.core.config import get_settings
from app.core.security import get_auth_limiter
from app.db import get_session
from app.main import app
from app.services.response_cache import render_cache


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
    engine.dispose()  # Python 3.13+ warns about SQLite connections left unclosed


@pytest.fixture
def db_engine(tmp_path: Path) -> Generator[Engine, None, None]:
    """A real temporary SQLite file with the schema created from the models
    (Alembic is covered by tests/integration/test_resume_migrations.py)."""
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False}
    )
    SQLModel.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def client(db_engine: Engine) -> Generator[TestClient, None, None]:
    """FastAPI TestClient against the real app/routing stack, wired to a
    real temporary SQLite file per CLAUDE.md's integration-testing bar
    ("FastAPI TestClient against a real temp SQLite DB")."""

    def _override_get_session() -> Generator[Session, None, None]:
        with Session(db_engine) as db_session:
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


@pytest.fixture(autouse=True)
def _fresh_auth_limiter() -> Generator[None, None, None]:
    """The limiter is process-wide state: failures recorded by one test (many
    deliberately send wrong keys) must not lock out the next."""
    get_auth_limiter.cache_clear()
    yield
    get_auth_limiter.cache_clear()


@pytest.fixture(autouse=True)
def _empty_render_cache() -> Generator[None, None, None]:
    """Rendered responses are cached process-wide by resume version; tests reuse
    ids and create resumes in quick succession, so never let one test's cached
    bytes answer another's request."""
    render_cache.clear()
    yield
    render_cache.clear()
