"""Integration test: real Alembic migrations against a real temp SQLite file,
then the CRUD service exercised against that migrated database.

Unlike tests/unit (in-memory DB, schema created straight from models), this
proves the migration files in migrations/versions/ actually produce a schema
the service can read and write.
"""

from pathlib import Path

from alembic import command
from alembic.config import Config
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
