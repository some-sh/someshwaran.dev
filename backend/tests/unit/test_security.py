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
from starlette.requests import Request
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


def _request(headers: dict[str, str] | None = None, peer: str = "203.0.113.9") -> Request:
    """A bare request, enough for require_admin to read the client address."""
    return Request(
        {
            "type": "http",
            "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
            "client": (peer, 5000),
        }
    )


def test_require_admin_accepts_the_configured_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ADMIN_API_KEY", "correct-key")
    get_settings.cache_clear()

    require_admin(request=_request(), credentials=_credentials("correct-key"))  # should not raise


def test_require_admin_rejects_a_wrong_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ADMIN_API_KEY", "correct-key")
    get_settings.cache_clear()

    with pytest.raises(HTTPException) as exc_info:
        require_admin(request=_request(), credentials=_credentials("wrong-key"))
    assert exc_info.value.status_code == 401


def test_require_admin_fails_closed_when_no_key_is_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("APP_ADMIN_API_KEY", raising=False)
    get_settings.cache_clear()

    with pytest.raises(HTTPException) as exc_info:
        require_admin(request=_request(), credentials=_credentials("anything"))
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


# --- client address and the shared authenticate() decision ---


def test_client_identity_prefers_the_cdn_header_then_forwarded_for_then_the_socket():
    from app.core.security import client_identity

    both = {"cf-connecting-ip": "198.51.100.1", "x-forwarded-for": "198.51.100.2, 10.0.0.1"}
    assert client_identity(both, "10.9.9.9") == "198.51.100.1"
    assert client_identity({"x-forwarded-for": "198.51.100.2, 10.0.0.1"}, "10.9.9.9") == (
        "198.51.100.2"
    )
    assert client_identity({}, "10.9.9.9") == "10.9.9.9"
    assert client_identity({}, None) == "unknown"
    assert len(client_identity({"x-forwarded-for": "a" * 500}, None)) == 64


def test_authenticate_clears_failures_on_success_and_locks_out_after_the_limit(
    monkeypatch: pytest.MonkeyPatch,
):
    from app.core.security import authenticate

    monkeypatch.setenv("APP_ADMIN_API_KEY", "correct-key")
    monkeypatch.setenv("APP_ADMIN_AUTH_MAX_FAILURES", "3")
    get_settings.cache_clear()

    assert not authenticate("wrong", "1.1.1.1").ok
    assert not authenticate("wrong", "1.1.1.1").ok
    assert authenticate("correct-key", "1.1.1.1").ok  # success forgets the two failures
    for _ in range(3):
        assert authenticate("wrong", "1.1.1.1").retry_after is None
    locked = authenticate("correct-key", "1.1.1.1")

    # Locked out: even the right key is refused, or the lockout would reveal
    # when a guess is correct.
    assert not locked.ok and locked.retry_after is not None
    assert authenticate("correct-key", "2.2.2.2").ok  # another address is unaffected


# --- startup warning about a weak admin key ---


def test_a_short_key_is_warned_about_without_logging_the_key(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    from app.core.security import warn_if_admin_key_is_weak

    monkeypatch.setenv("APP_ADMIN_API_KEY", "short-secret-key")
    get_settings.cache_clear()

    with caplog.at_level("WARNING", logger="app.security"):
        warn_if_admin_key_is_weak()

    assert "only 16 characters" in caplog.text
    assert "short-secret-key" not in caplog.text  # never log the secret


def test_a_missing_key_is_warned_about(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    from app.core.security import warn_if_admin_key_is_weak

    monkeypatch.delenv("APP_ADMIN_API_KEY", raising=False)
    monkeypatch.setenv("APP_ADMIN_API_KEY", "")
    get_settings.cache_clear()

    with caplog.at_level("WARNING", logger="app.security"):
        warn_if_admin_key_is_weak()

    assert "not set" in caplog.text


def test_a_strong_key_produces_no_warning(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    import secrets

    from app.core.security import warn_if_admin_key_is_weak

    monkeypatch.setenv("APP_ADMIN_API_KEY", secrets.token_urlsafe(32))
    get_settings.cache_clear()

    with caplog.at_level("WARNING", logger="app.security"):
        warn_if_admin_key_is_weak()

    assert caplog.text == ""
