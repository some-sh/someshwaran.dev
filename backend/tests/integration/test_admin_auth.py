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


# --- lockout after repeated wrong keys ---


def _with_limit(monkeypatch, max_failures: int = 3) -> None:
    monkeypatch.setenv("APP_ADMIN_API_KEY", "test-admin-key")
    monkeypatch.setenv("APP_ADMIN_AUTH_MAX_FAILURES", str(max_failures))
    get_settings.cache_clear()


def test_repeated_wrong_keys_lock_the_address_out_with_429_and_retry_after(client, monkeypatch):
    _with_limit(monkeypatch)
    wrong = {"Authorization": "Bearer wrong"}

    codes = [client.get("/api/admin/whoami", headers=wrong).status_code for _ in range(3)]
    locked = client.get("/api/admin/whoami", headers=wrong)

    assert codes == [401, 401, 401]
    assert locked.status_code == 429
    assert int(locked.headers["retry-after"]) > 0
    assert "too many" in locked.json()["detail"].lower()


def test_a_locked_address_is_refused_even_with_the_correct_key(client, monkeypatch):
    _with_limit(monkeypatch)
    for _ in range(3):
        client.get("/api/admin/whoami", headers={"Authorization": "Bearer wrong"})

    correct = client.get("/api/admin/whoami", headers={"Authorization": "Bearer test-admin-key"})

    assert correct.status_code == 429  # otherwise 429-vs-200 would tell a guesser they hit it


def test_lockout_is_per_address_and_does_not_lock_the_real_admin_out(client, monkeypatch):
    _with_limit(monkeypatch)
    attacker = {"Authorization": "Bearer wrong", "X-Forwarded-For": "203.0.113.50"}
    for _ in range(4):
        client.get("/api/admin/whoami", headers=attacker)

    admin = client.get(
        "/api/admin/whoami",
        headers={"Authorization": "Bearer test-admin-key", "X-Forwarded-For": "198.51.100.7"},
    )

    assert admin.status_code == 200


def test_successful_requests_do_not_count_toward_the_limit(client, monkeypatch):
    _with_limit(monkeypatch)
    good = {"Authorization": "Bearer test-admin-key"}

    statuses = {client.get("/api/admin/whoami", headers=good).status_code for _ in range(20)}

    assert statuses == {200}
