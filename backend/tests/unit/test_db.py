"""Unit tests for app.db's non-engine helpers."""

from pathlib import Path

from app.db import ensure_sqlite_directory_exists


def test_creates_missing_parent_directories(tmp_path: Path) -> None:
    db_path = tmp_path / "nested" / "deeper" / "app.db"

    ensure_sqlite_directory_exists(f"sqlite:///{db_path}")

    assert db_path.parent.is_dir()


def test_is_a_noop_for_in_memory_sqlite(tmp_path: Path) -> None:
    ensure_sqlite_directory_exists("sqlite://")  # must not raise
    ensure_sqlite_directory_exists("sqlite:///:memory:")  # must not raise


def test_is_a_noop_for_non_sqlite_urls() -> None:
    # No postgres driver is installed in this project yet; this must not
    # try to connect or import one — just recognize it isn't sqlite.
    ensure_sqlite_directory_exists("postgresql://user:pass@localhost/db")
