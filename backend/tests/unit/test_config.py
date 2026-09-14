"""Unit tests for Settings' non-trivial fields."""

from app.core.config import Settings


def test_cors_allowed_origins_list_splits_and_strips() -> None:
    settings = Settings(cors_allowed_origins="https://a.example, https://b.example ,,")

    assert settings.cors_allowed_origins_list == ["https://a.example", "https://b.example"]


def test_cors_allowed_origins_list_defaults_to_the_vite_dev_server() -> None:
    settings = Settings()

    assert settings.cors_allowed_origins_list == ["http://localhost:5173"]
