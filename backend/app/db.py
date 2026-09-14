"""Database engine and session management.

Schema is owned by Alembic migrations (see backend/migrations/). The
``create_db_and_tables`` helper here is a dev/test convenience only —
it is never called in production code paths.
"""

from collections.abc import Generator
from functools import lru_cache
from pathlib import Path

from sqlalchemy import Engine
from sqlalchemy.engine import make_url
from sqlmodel import Session, SQLModel, create_engine

from app.core.config import get_settings


def ensure_sqlite_directory_exists(database_url: str) -> None:
    """SQLite auto-creates the database *file* on first connect but never
    a missing parent directory — so the default ``./data/app.db`` (``data/``
    is gitignored, never committed, so a fresh checkout or deploy doesn't
    have it) fails with "unable to open database file" until something
    creates that directory first.

    Called before any connection is opened, both from get_engine() below
    and from migrations/env.py, so this holds regardless of whether the
    app or an `alembic` invocation connects first.
    """
    url = make_url(database_url)
    if url.get_backend_name() != "sqlite" or url.database in (None, ":memory:"):
        return
    Path(url.database).parent.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    ensure_sqlite_directory_exists(settings.database_url)
    # SQLite + FastAPI's threaded test client need check_same_thread=False;
    # harmless (and ignored) for other dialects.
    connect_args = (
        {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
    )
    return create_engine(settings.database_url, echo=settings.db_echo, connect_args=connect_args)


def create_db_and_tables() -> None:
    """Create all tables from current models. Dev/test only — production
    schema changes always go through an Alembic migration instead."""
    SQLModel.metadata.create_all(get_engine())


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a request-scoped session."""
    with Session(get_engine()) as session:
        yield session
