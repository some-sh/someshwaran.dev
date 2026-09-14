"""Database engine and session management.

Schema is owned by Alembic migrations (see backend/migrations/). The
``create_db_and_tables`` helper here is a dev/test convenience only —
it is never called in production code paths.
"""

from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import Engine
from sqlmodel import Session, SQLModel, create_engine

from app.core.config import get_settings


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
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
