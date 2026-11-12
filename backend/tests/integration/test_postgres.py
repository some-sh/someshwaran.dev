"""Integration tests against a real Postgres.

Production runs on Postgres (SQLite on the container filesystem is wiped by
every deploy), but every other test uses SQLite, which has no timezone-aware
column type, no concurrency and a different DDL dialect. These close that
gap: the real migrations, the service layer, and concurrent startups.

Skipped unless APP_TEST_POSTGRES_URL points at a database (CI provides one
via a service container; locally, any throwaway database works). The fixture
wipes the `public` schema, so it refuses any database whose name does not
contain "test".
"""

import os
import threading
from collections.abc import Generator
from datetime import timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from app.core.config import get_settings, normalize_database_url
from app.db import get_engine
from app.main import _run_migrations
from app.schemas.resume import PersonalInfoInput, ResumeCreate, SkillInput
from app.services import resume_service

_URL = os.environ.get("APP_TEST_POSTGRES_URL")
pytestmark = pytest.mark.skipif(not _URL, reason="APP_TEST_POSTGRES_URL is not set")

BACKEND_DIR = Path(__file__).resolve().parents[2]


@pytest.fixture
def postgres_url(monkeypatch: pytest.MonkeyPatch) -> Generator[str, None, None]:
    assert _URL is not None
    url = normalize_database_url(_URL)
    if "test" not in (make_url(url).database or ""):
        pytest.fail("Refusing to wipe a database whose name does not contain 'test'")

    admin = create_engine(url, isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
    admin.dispose()

    monkeypatch.setenv("APP_DATABASE_URL", url)
    get_settings.cache_clear()
    get_engine.cache_clear()
    yield url
    get_engine.cache_clear()
    get_settings.cache_clear()


def _alembic_config() -> Config:
    return Config(str(BACKEND_DIR / "alembic.ini"))


def test_migrations_match_the_models_on_postgres(postgres_url: str) -> None:
    command.upgrade(_alembic_config(), "head")

    # Raises if the models and migrations disagree on Postgres (this is what
    # caught TIMESTAMP vs TIMESTAMPTZ, which SQLite cannot show).
    command.check(_alembic_config())


def test_timestamps_round_trip_as_utc_aware_values(postgres_url: str) -> None:
    command.upgrade(_alembic_config(), "head")

    with Session(get_engine()) as session:
        created = resume_service.create_resume(
            session,
            ResumeCreate(
                name="pg",
                personal_info=PersonalInfoInput(full_name="Ada", email="ada@example.com"),
                skills=[SkillInput(name="Python")],
            ),
        )
        assert created.id is not None
        session.expire_all()
        fetched = resume_service.get_resume(session, created.id)

        assert fetched is not None
        assert fetched.created_at.utcoffset() == timedelta(0)  # aware, in UTC
        assert fetched.personal_info is not None


def test_service_flow_works_on_postgres(postgres_url: str) -> None:
    command.upgrade(_alembic_config(), "head")

    with Session(get_engine()) as session:
        first = resume_service.create_resume(
            session,
            ResumeCreate(
                name="first",
                personal_info=PersonalInfoInput(full_name="Ada", email="ada@example.com"),
            ),
        )
        assert first.id is not None
        resume_service.set_default_resume(session, first.id)
        clone = resume_service.clone_resume(session, first.id)
        assert clone is not None and clone.id is not None
        resume_service.set_default_resume(session, clone.id)
        session.expire_all()

        default = resume_service.get_default_resume(session)
        refreshed_first = resume_service.get_resume(session, first.id)

    assert default is not None and default.id == clone.id
    assert refreshed_first is not None and refreshed_first.is_default is False


def test_concurrent_startups_migrate_a_fresh_database_exactly_once(postgres_url: str) -> None:
    """After a deploy, several instances start and migrate at once. Without the
    advisory lock in _run_migrations, two first-time CREATE TABLEs collide."""
    errors: list[BaseException] = []
    barrier = threading.Barrier(4)

    def start() -> None:
        try:
            barrier.wait()
            _run_migrations()
        except BaseException as error:  # noqa: BLE001 - surface any failure below
            errors.append(error)

    threads = [threading.Thread(target=start) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    with get_engine().connect() as connection:
        version = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    assert version == "c3e6a9d4f2b8"  # head


def _new_resume(name: str) -> ResumeCreate:
    return ResumeCreate(
        name=name,
        personal_info=PersonalInfoInput(full_name="Ada", email="ada@example.com"),
        skills=[SkillInput(name=n) for n in ("c", "a", "b")],
    )


def test_section_order_is_stored_and_returned_in_input_order(postgres_url: str) -> None:
    command.upgrade(_alembic_config(), "head")

    with Session(get_engine()) as session:
        created = resume_service.create_resume(session, _new_resume("ordered"))
        assert created.id is not None
        session.expire_all()
        fetched = resume_service.get_resume(session, created.id)

        assert fetched is not None
        assert [(s.name, s.order_index) for s in fetched.skills] == [("c", 0), ("a", 1), ("b", 2)]


def test_backfill_and_duplicate_default_repair_on_postgres(postgres_url: str) -> None:
    command.upgrade(_alembic_config(), "a1c4e7b2d9f0")
    engine = get_engine()
    with engine.begin() as conn:
        for name in ("one", "two"):
            conn.execute(
                text(
                    "INSERT INTO resumes (name, is_default, summary, created_at, updated_at) "
                    "VALUES (:n, true, '', now(), now())"
                ),
                {"n": name},
            )
        for resume_id in (1, 2):
            for skill in ("x", "y", "z"):
                conn.execute(
                    text("INSERT INTO skills (resume_id, name, order_index) VALUES (:r, :n, 0)"),
                    {"r": resume_id, "n": skill},
                )

    command.upgrade(_alembic_config(), "head")

    with engine.connect() as conn:
        positions = conn.execute(
            text(
                "SELECT resume_id, array_agg(order_index ORDER BY id) FROM skills "
                "GROUP BY resume_id ORDER BY resume_id"
            )
        ).all()
        defaults = conn.execute(text("SELECT name FROM resumes WHERE is_default")).all()
    assert [tuple(r) for r in positions] == [(1, [0, 1, 2]), (2, [0, 1, 2])]
    assert [r[0] for r in defaults] == ["one"]


def test_database_refuses_a_second_default(postgres_url: str) -> None:
    command.upgrade(_alembic_config(), "head")

    with Session(get_engine()) as session:
        first = resume_service.create_resume(session, _new_resume("one"))
        second = resume_service.create_resume(session, _new_resume("two"))
        assert first.id is not None
        resume_service.set_default_resume(session, first.id)

        second.is_default = True  # bypass the service on purpose
        session.add(second)
        with pytest.raises(IntegrityError):
            session.commit()


def test_concurrent_set_default_leaves_exactly_one_default(postgres_url: str) -> None:
    """Two requests (two app instances, or REST plus MCP) set different defaults at
    the same moment. Each must succeed, and exactly one default must remain."""
    command.upgrade(_alembic_config(), "head")
    with Session(get_engine()) as session:
        ids = []
        for name in ("a", "b", "c", "d"):
            created = resume_service.create_resume(session, _new_resume(name))
            assert created.id is not None
            ids.append(created.id)

    errors: list[BaseException] = []
    barrier = threading.Barrier(len(ids))

    def set_default(resume_id: int) -> None:
        try:
            with Session(get_engine()) as session:
                barrier.wait()
                resume_service.set_default_resume(session, resume_id)
        except BaseException as error:  # noqa: BLE001 - surfaced by the assertion below
            errors.append(error)

    threads = [threading.Thread(target=set_default, args=(i,)) for i in ids]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    with get_engine().connect() as conn:
        count = conn.execute(text("SELECT count(*) FROM resumes WHERE is_default")).scalar_one()
    assert count == 1
