"""Unit tests for Settings' non-trivial fields."""

import pytest

from app.core.config import Settings, normalize_database_url


def test_cors_allowed_origins_list_splits_and_strips() -> None:
    settings = Settings(cors_allowed_origins="https://a.example, https://b.example ,,")

    assert settings.cors_allowed_origins_list == ["https://a.example", "https://b.example"]


def test_cors_allowed_origins_list_defaults_to_the_vite_dev_server() -> None:
    settings = Settings()

    assert settings.cors_allowed_origins_list == ["http://localhost:5173"]


def test_normalize_database_url_points_postgres_urls_at_psycopg_3() -> None:
    # Neon/Supabase/Heroku-style URLs: SQLAlchemy would otherwise pick psycopg2.
    assert (
        normalize_database_url("postgres://u:p@host/db?sslmode=require")
        == "postgresql+psycopg://u:p@host/db?sslmode=require"
    )
    assert normalize_database_url("postgresql://u@host/db") == "postgresql+psycopg://u@host/db"


def test_normalize_database_url_leaves_other_urls_alone() -> None:
    assert normalize_database_url("sqlite:///./data/app.db") == "sqlite:///./data/app.db"
    assert (
        normalize_database_url("postgresql+psycopg://u@host/db") == "postgresql+psycopg://u@host/db"
    )


def test_database_url_accepts_the_unprefixed_name_the_neon_integration_injects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("APP_DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgres://u@host/db")

    assert Settings().database_url == "postgresql+psycopg://u@host/db"


def test_prefixed_database_url_wins_over_the_unprefixed_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgres://u@host/from-integration")
    monkeypatch.setenv("APP_DATABASE_URL", "sqlite:///./explicit.db")

    assert Settings().database_url == "sqlite:///./explicit.db"
