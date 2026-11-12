"""Integration test: real Alembic migrations against a real temp SQLite file,
then the CRUD service exercised against that migrated database.

Unlike tests/unit (in-memory DB, schema created straight from models), this
proves the migration files in migrations/versions/ actually produce a schema
the service can read and write.
"""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlmodel import Session, create_engine

from app.core.config import get_settings
from app.schemas.resume import PersonalInfoInput, ResumeCreate, SkillInput
from app.services import resume_service

BACKEND_DIR = Path(__file__).resolve().parents[2]


def test_migrations_produce_a_schema_the_service_can_use(tmp_path, monkeypatch):
    db_path = tmp_path / "integration.db"
    database_url = f"sqlite:///{db_path}"
    monkeypatch.setenv("APP_DATABASE_URL", database_url)
    get_settings.cache_clear()

    try:
        alembic_cfg = Config(str(BACKEND_DIR / "alembic.ini"))
        command.upgrade(alembic_cfg, "head")

        engine = create_engine(database_url, connect_args={"check_same_thread": False})
        with Session(engine) as session:
            resume = resume_service.create_resume(
                session,
                ResumeCreate(
                    name="Integration test resume",
                    personal_info=PersonalInfoInput(
                        full_name="Ada Lovelace", email="ada@example.com"
                    ),
                    skills=[SkillInput(name="Python")],
                ),
            )
            assert resume.id is not None

            fetched = resume_service.get_resume(session, resume.id)

            assert fetched is not None
            assert fetched.personal_info is not None
            assert fetched.personal_info.full_name == "Ada Lovelace"
            assert [s.name for s in fetched.skills] == ["Python"]
    finally:
        get_settings.cache_clear()


# --- data migrations: section positions and the single-default index ---

_INSERT_RESUME = (
    "INSERT INTO resumes (name, is_default, summary, created_at, updated_at) "
    "VALUES (:name, :is_default, '', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
)


def _migrate(url: str, monkeypatch, revision: str) -> None:
    monkeypatch.setenv("APP_DATABASE_URL", url)
    get_settings.cache_clear()
    command.upgrade(Config(str(BACKEND_DIR / "alembic.ini")), revision)


def test_backfill_gives_existing_rows_explicit_positions(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'backfill.db'}"
    try:
        _migrate(url, monkeypatch, "a1c4e7b2d9f0")  # state of production before the fix
        engine = create_engine(url)
        with engine.begin() as conn:
            for name in ("one", "two"):
                conn.execute(text(_INSERT_RESUME), {"name": name, "is_default": False})
            for resume_id in (1, 2):
                for skill in ("x", "y", "z"):
                    conn.execute(
                        text(
                            "INSERT INTO skills (resume_id, name, order_index) VALUES (:r, :n, 0)"
                        ),
                        {"r": resume_id, "n": f"{resume_id}{skill}"},
                    )

        _migrate(url, monkeypatch, "b2d5f8c3e1a7")

        with engine.connect() as conn:
            rows = conn.execute(
                text("SELECT resume_id, name, order_index FROM skills ORDER BY id")
            ).all()
        # Positions restart at 0 per resume and follow the existing (id) order.
        assert [tuple(r) for r in rows] == [
            (1, "1x", 0), (1, "1y", 1), (1, "1z", 2),
            (2, "2x", 0), (2, "2y", 1), (2, "2z", 2),
        ]  # fmt: skip
    finally:
        get_settings.cache_clear()


def test_duplicate_defaults_are_resolved_before_the_unique_index(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'dupes.db'}"
    try:
        _migrate(url, monkeypatch, "b2d5f8c3e1a7")
        engine = create_engine(url)
        with engine.begin() as conn:
            for name in ("one", "two", "three"):
                conn.execute(text(_INSERT_RESUME), {"name": name, "is_default": True})

        _migrate(url, monkeypatch, "head")

        with engine.connect() as conn:
            defaults = conn.execute(text("SELECT name FROM resumes WHERE is_default")).all()
        assert [r[0] for r in defaults] == ["one"]  # lowest id wins
    finally:
        get_settings.cache_clear()
