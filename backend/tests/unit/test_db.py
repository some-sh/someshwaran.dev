"""Unit tests for app.db's non-engine helpers."""

from pathlib import Path

import pytest

from app.core.config import get_settings
from app.db import dispose_engine, ensure_sqlite_directory_exists, get_engine


def test_creates_missing_parent_directories(tmp_path: Path) -> None:
    db_path = tmp_path / "nested" / "deeper" / "app.db"

    ensure_sqlite_directory_exists(f"sqlite:///{db_path}")

    assert db_path.parent.is_dir()


def test_is_a_noop_for_in_memory_sqlite(tmp_path: Path) -> None:
    ensure_sqlite_directory_exists("sqlite://")  # must not raise
    ensure_sqlite_directory_exists("sqlite:///:memory:")  # must not raise


def test_is_a_noop_for_non_sqlite_urls() -> None:
    # Must not try to connect — just recognize it isn't sqlite.
    ensure_sqlite_directory_exists("postgresql://user:pass@localhost/db")


def test_postgres_engine_pre_pings_and_recycles_for_serverless_databases(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Neon closes idle connections and scales to zero; without pre-ping a
    # pooled connection can be dead when a request picks it up. create_engine
    # is lazy, so this does not connect anywhere.
    monkeypatch.setenv("APP_DATABASE_URL", "postgres://u:p@localhost/db")
    get_settings.cache_clear()
    dispose_engine()
    try:
        engine = get_engine()

        assert engine.dialect.name == "postgresql"
        assert engine.pool._pre_ping is True  # type: ignore[attr-defined]
        assert engine.pool._recycle == 300  # type: ignore[attr-defined]
    finally:
        get_settings.cache_clear()
        dispose_engine()
