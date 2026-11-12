"""App configuration.

A single settings object, read from environment variables (prefixed
``APP_``) or a local ``.env`` file. Alembic's env.py reads the same
settings so migrations always target the same database as the app.
"""

from functools import lru_cache

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def normalize_database_url(url: str) -> str:
    """Managed Postgres providers (Neon, Supabase, Heroku-style) hand out
    ``postgres://`` or ``postgresql://`` URLs, which SQLAlchemy would route
    to the legacy psycopg2 driver. This project ships psycopg 3, so point
    those at it explicitly. Anything else (sqlite, an already-qualified
    ``postgresql+psycopg://``) is returned unchanged."""
    for scheme in ("postgres://", "postgresql://"):
        if url.startswith(scheme):
            return "postgresql+psycopg://" + url[len(scheme) :]
    return url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APP_", env_file=".env", extra="ignore")

    # SQLite by default (local dev, tests). In production this is Postgres:
    # SQLite lives on the container's filesystem, which every deploy replaces,
    # so data written there is lost on the next deploy. The FastAPI Cloud <->
    # Neon integration injects the plain DATABASE_URL, so accept that name as
    # well as APP_DATABASE_URL (the explicit one wins when both are set).
    database_url: str = Field(
        default="sqlite:///./data/app.db",
        validation_alias=AliasChoices("APP_DATABASE_URL", "DATABASE_URL"),
    )
    db_echo: bool = False

    # Interactive API docs (/docs, /redoc, /openapi.json). Off by default: on a
    # public deployment they advertise every admin route. Set APP_ENABLE_DOCS=true
    # for local development.
    enable_docs: bool = False

    # Shared secret for the one admin auth mechanism (see app/core/security.py).
    # None by default so a deployment with no key configured fails closed
    # instead of silently trusting any bearer token. Generate one with:
    #   python -c "import secrets; print(secrets.token_urlsafe(32))"
    admin_api_key: str | None = None

    # Comma-separated, not a JSON list: keeps a plain env var usable
    # (APP_CORS_ALLOWED_ORIGINS="https://someshwaran.dev,http://localhost:5173")
    # instead of fighting pydantic-settings' JSON parsing for list fields.
    # Defaults to the Vite dev server so local frontend+backend work out of
    # the box; add the deployed frontend origin once phase 8 picks one.
    cors_allowed_origins: str = "http://localhost:5173"

    @field_validator("database_url")
    @classmethod
    def _normalize_database_url(cls, value: str) -> str:
        return normalize_database_url(value)

    @property
    def cors_allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
