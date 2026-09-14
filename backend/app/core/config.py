"""App configuration.

A single settings object, read from environment variables (prefixed
``APP_``) or a local ``.env`` file. Alembic's env.py reads the same
settings so migrations always target the same database as the app.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APP_", env_file=".env", extra="ignore")

    # SQLite today; CLAUDE.md flags a possible future move to Postgres,
    # so nothing here should assume SQLite beyond this URL.
    database_url: str = "sqlite:///./data/app.db"
    db_echo: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
