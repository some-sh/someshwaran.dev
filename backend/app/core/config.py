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

    # Shared secret for the one admin auth mechanism (see app/core/security.py).
    # None by default so a deployment with no key configured fails closed
    # instead of silently trusting any bearer token. Generate one with:
    #   python -c "import secrets; print(secrets.token_urlsafe(32))"
    admin_api_key: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
