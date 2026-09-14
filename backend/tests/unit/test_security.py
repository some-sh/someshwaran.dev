"""Unit tests for the admin auth dependency, exercised directly against a
configured Settings object rather than through the app/routing stack."""

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.core.config import get_settings
from app.core.security import require_admin


@pytest.fixture(autouse=True)
def _clear_settings_cache(monkeypatch: pytest.MonkeyPatch):
    """Every test sets its own APP_ADMIN_API_KEY; make sure the lru_cache
    on get_settings() doesn't leak a value between tests."""
    yield
    get_settings.cache_clear()


def _credentials(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def test_require_admin_accepts_the_configured_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ADMIN_API_KEY", "correct-key")
    get_settings.cache_clear()

    require_admin(_credentials("correct-key"))  # should not raise


def test_require_admin_rejects_a_wrong_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ADMIN_API_KEY", "correct-key")
    get_settings.cache_clear()

    with pytest.raises(HTTPException) as exc_info:
        require_admin(_credentials("wrong-key"))
    assert exc_info.value.status_code == 401


def test_require_admin_fails_closed_when_no_key_is_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("APP_ADMIN_API_KEY", raising=False)
    get_settings.cache_clear()

    with pytest.raises(HTTPException) as exc_info:
        require_admin(_credentials("anything"))
    assert exc_info.value.status_code == 401
