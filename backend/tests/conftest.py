from collections.abc import Generator

import pytest
from sqlmodel import Session, SQLModel, create_engine

import app.models  # noqa: F401  ensures tables are registered on metadata


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
