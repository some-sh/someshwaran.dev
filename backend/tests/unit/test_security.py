"""Unit tests for the admin auth mechanism: the shared is_valid_admin_key
check, the FastAPI require_admin dependency built on it, and the ASGI
AdminBearerAuthMiddleware built on it for the MCP transport — each
exercised directly, or (for the middleware) against a trivial downstream
app, rather than through the real app/routing stack. See
tests/integration/test_admin_auth.py and test_mcp_auth.py for that."""

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from app.core.config import get_settings
from app.core.security import AdminBearerAuthMiddleware, is_valid_admin_key, require_admin


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


def test_is_valid_admin_key_accepts_the_configured_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ADMIN_API_KEY", "correct-key")
    get_settings.cache_clear()

    assert is_valid_admin_key("correct-key") is True


def test_is_valid_admin_key_rejects_a_wrong_or_missing_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ADMIN_API_KEY", "correct-key")
    get_settings.cache_clear()

    assert is_valid_admin_key("wrong-key") is False
    assert is_valid_admin_key(None) is False


def test_is_valid_admin_key_fails_closed_when_no_key_is_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("APP_ADMIN_API_KEY", raising=False)
    get_settings.cache_clear()

    assert is_valid_admin_key("anything") is False


def test_admin_bearer_auth_middleware_rejects_missing_or_wrong_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ADMIN_API_KEY", "correct-key")
    get_settings.cache_clear()

    async def _ok(_request):
        return PlainTextResponse("ok")

    app = Starlette(routes=[Route("/", _ok)])
    client = TestClient(AdminBearerAuthMiddleware(app))

    no_auth = client.get("/")
    assert no_auth.status_code == 401
    assert no_auth.headers["www-authenticate"] == "Bearer"

    wrong_key = client.get("/", headers={"Authorization": "Bearer wrong-key"})
    assert wrong_key.status_code == 401


def test_admin_bearer_auth_middleware_forwards_a_valid_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ADMIN_API_KEY", "correct-key")
    get_settings.cache_clear()

    async def _ok(_request):
        return PlainTextResponse("ok")

    app = Starlette(routes=[Route("/", _ok)])
    client = TestClient(AdminBearerAuthMiddleware(app))

    response = client.get("/", headers={"Authorization": "Bearer correct-key"})

    assert response.status_code == 200
    assert response.text == "ok"
