"""Integration test: the auth dependency wired through the real app/routing
stack via TestClient, not called directly (see tests/unit/test_security.py
for the dependency's own logic)."""

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _admin_api_key(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("APP_ADMIN_API_KEY", "test-admin-key")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_whoami_without_a_key_is_unauthorized() -> None:
    response = client.get("/api/admin/whoami")

    assert response.status_code == 401


def test_whoami_with_the_wrong_key_is_unauthorized() -> None:
    response = client.get("/api/admin/whoami", headers={"Authorization": "Bearer wrong-key"})

    assert response.status_code == 401


def test_whoami_with_the_correct_key_succeeds() -> None:
    response = client.get("/api/admin/whoami", headers={"Authorization": "Bearer test-admin-key"})

    assert response.status_code == 200
    assert response.json() == {"authenticated": True}
