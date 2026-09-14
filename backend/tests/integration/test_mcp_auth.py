"""Integration test: the MCP transport's auth gate, through the real
app/routing stack (not called directly — see tests/unit/test_security.py
for AdminBearerAuthMiddleware's own logic, and
tests/unit/test_mcp_server.py for the tools it's gating).
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.db import get_engine

_HEADERS = {"Accept": "application/json, text/event-stream"}


@pytest.fixture(autouse=True)
def _admin_api_key(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("APP_ADMIN_API_KEY", "test-admin-key")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_mcp_endpoint_without_a_key_is_unauthorized() -> None:
    from app.main import app

    response = TestClient(app).post(
        "/api/mcp/", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, headers=_HEADERS
    )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_mcp_endpoint_with_the_wrong_key_is_unauthorized() -> None:
    from app.main import app

    response = TestClient(app).post(
        "/api/mcp/",
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        headers={**_HEADERS, "Authorization": "Bearer wrong-key"},
    )

    assert response.status_code == 401


def test_mcp_endpoint_with_the_correct_key_reaches_the_real_mcp_transport(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Doesn't do a full MCP protocol handshake (that's covered at the tool
    level, in-memory, in tests/unit/test_mcp_server.py) — just proves the
    request gets past AdminBearerAuthMiddleware and reaches the real
    mcp_asgi_app mounted in app/main.py, rather than, say, a middleware
    bug that also blocks valid requests or a mount pointed at the wrong
    app entirely. A non-401, MCP-protocol-shaped response (JSON-RPC over
    the real transport, distinct from the plain JSON error body the 401
    tests above get) is proof enough of that; the response here is
    actually a *protocol*-level 400 (no session established yet — this
    single bare call skips the initialize handshake a real client would
    do first), not a 200, and that's fine — it demonstrates the call
    reached the real MCP server rather than being auth-rejected.
    """
    db_path = tmp_path / "app.db"
    monkeypatch.setenv("APP_DATABASE_URL", f"sqlite:///{db_path}")
    get_settings.cache_clear()
    get_engine.cache_clear()

    try:
        from app.main import app

        # `with` runs the app's lifespan, which starts the MCP session
        # manager (app/mcp_server.py) — required before the mounted
        # transport can handle any request past the auth gate.
        with TestClient(app) as client:
            response = client.post(
                "/api/mcp/",
                json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
                headers={**_HEADERS, "Authorization": "Bearer test-admin-key"},
            )
    finally:
        get_settings.cache_clear()
        get_engine.cache_clear()

    assert response.status_code != 401
    assert response.json()["jsonrpc"] == "2.0"
