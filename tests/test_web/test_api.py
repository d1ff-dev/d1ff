"""Tests for the JSON API endpoints — GET /api/me, GET /api/installations, POST /api/settings."""

import datetime
import json
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from d1ff.config import get_settings
from d1ff.main import app
from d1ff.storage.models import Installation

REQUIRED_ENV = {
    "GITHUB_APP_ID": "12345",
    "GITHUB_PRIVATE_KEY": "fake-pem-key",
    "GITHUB_WEBHOOK_SECRET": "test-webhook-secret",
    "ENCRYPTION_KEY": "dGVzdC1rZXktMzItYnl0ZXMtZm9yLWZlcm5ldA==",
    "GITHUB_CLIENT_ID": "test-client-id",
    "GITHUB_CLIENT_SECRET": "test-client-secret",
    "SESSION_SECRET_KEY": "test-session-secret-key-32-bytes!!",
    "DATABASE_URL": "sqlite+aiosqlite:///./test_api.db",
}

FAKE_USER = {"login": "testuser", "github_id": 12345, "name": "Test User", "user_id": 1}

FAKE_INSTALLATION = Installation(
    installation_id=42,
    account_login="testorg",
    account_type="Organization",
    suspended=False,
    created_at=datetime.datetime(2024, 1, 1, tzinfo=datetime.UTC),
    updated_at=datetime.datetime(2024, 1, 1, tzinfo=datetime.UTC),
)


def make_session_cookie(user: dict, secret_key: str) -> str:
    """Craft a signed session cookie that Starlette's SessionMiddleware will accept."""
    import base64

    from itsdangerous import TimestampSigner

    signer = TimestampSigner(secret_key)
    data = base64.b64encode(json.dumps({"user": user}).encode("utf-8"))
    return signer.sign(data).decode("utf-8")


@pytest.fixture(autouse=True)
def setup_env(monkeypatch: pytest.MonkeyPatch) -> None:  # type: ignore[misc]
    get_settings.cache_clear()
    for key, value in REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)
    yield
    get_settings.cache_clear()


@pytest.fixture
def session_cookie() -> str:
    # Use the actual session secret the middleware was created with at import time.
    from d1ff.main import _session_secret
    return make_session_cookie(FAKE_USER, _session_secret)


# ---------------------------------------------------------------------------
# GET /api/me
# ---------------------------------------------------------------------------

async def test_get_me_unauthenticated() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/me")
    assert response.status_code == 401


async def test_get_me_authenticated(session_cookie: str) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        client.cookies.set("session", session_cookie)
        response = await client.get("/api/me")
    assert response.status_code == 200
    data = response.json()
    assert data["login"] == "testuser"
    assert data["github_id"] == 12345


# ---------------------------------------------------------------------------
# GET /api/installations
# ---------------------------------------------------------------------------

async def test_get_installations_unauthenticated() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/installations")
    assert response.status_code == 401


async def test_get_installations_returns_list(session_cookie: str) -> None:
    fake_config = {
        "provider": "openai",
        "model": "gpt-4o",
        "encrypted_key": "someencryptedvalue",
        "custom_endpoint": None,
    }
    with (
        patch(
            "d1ff.web.api.InstallationRepository.list_installations_for_user",
            new=AsyncMock(return_value=[FAKE_INSTALLATION]),
        ),
        patch(
            "d1ff.web.api.get_api_key_config",
            new=AsyncMock(return_value=fake_config),
        ),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            client.cookies.set("session", session_cookie)
            response = await client.get("/api/installations")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["installation"]["installation_id"] == 42
    assert data[0]["installation"]["account_login"] == "testorg"
    assert data[0]["config"]["provider"] == "openai"
    assert data[0]["config"]["has_key"] is True
    assert "encrypted_key" not in data[0]["config"]


# ---------------------------------------------------------------------------
# POST /api/settings
# ---------------------------------------------------------------------------

async def test_post_settings_unauthenticated() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/settings", json={
            "installation_id": 42, "provider": "openai", "model": "gpt-4o",
            "api_key": "sk-test", "custom_endpoint": "",
        })
    assert response.status_code == 401


async def test_post_settings_saves_config(session_cookie: str) -> None:
    mock_upsert = AsyncMock()
    with (
        patch(
            "d1ff.web.api.InstallationRepository.list_installations_for_user",
            new=AsyncMock(return_value=[FAKE_INSTALLATION]),
        ),
        patch("d1ff.web.api.upsert_api_key_for_installation", mock_upsert),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            client.cookies.set("session", session_cookie)
            response = await client.post("/api/settings", json={
                "installation_id": 42,
                "provider": "openai",
                "model": "gpt-4o",
                "api_key": "sk-test",
                "custom_endpoint": "",
            })

    assert response.status_code == 200
    assert response.json() == {"saved": True}
    mock_upsert.assert_called_once_with(42, "openai", "gpt-4o", "sk-test", custom_endpoint=None)


async def test_post_settings_invalid_provider(session_cookie: str) -> None:
    with patch(
        "d1ff.web.api.InstallationRepository.list_installations_for_user",
        new=AsyncMock(return_value=[FAKE_INSTALLATION]),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            client.cookies.set("session", session_cookie)
            response = await client.post("/api/settings", json={
                "installation_id": 42, "provider": "badprovider", "model": "m",
                "api_key": "k", "custom_endpoint": "",
            })
    assert response.status_code == 400


async def test_post_settings_unowned_installation(session_cookie: str) -> None:
    with patch(
        "d1ff.web.api.InstallationRepository.list_installations_for_user",
        new=AsyncMock(return_value=[FAKE_INSTALLATION]),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            client.cookies.set("session", session_cookie)
            response = await client.post("/api/settings", json={
                "installation_id": 999,  # not owned
                "provider": "openai", "model": "gpt-4o",
                "api_key": "sk-test", "custom_endpoint": "",
            })
    assert response.status_code == 403


async def test_post_settings_invalid_endpoint(session_cookie: str) -> None:
    with patch(
        "d1ff.web.api.InstallationRepository.list_installations_for_user",
        new=AsyncMock(return_value=[FAKE_INSTALLATION]),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            client.cookies.set("session", session_cookie)
            response = await client.post("/api/settings", json={
                "installation_id": 42, "provider": "openai", "model": "gpt-4o",
                "api_key": "sk-test", "custom_endpoint": "not-a-url",
            })
    assert response.status_code == 400


async def test_post_settings_saves_custom_endpoint(session_cookie: str) -> None:
    mock_upsert = AsyncMock()
    with (
        patch(
            "d1ff.web.api.InstallationRepository.list_installations_for_user",
            new=AsyncMock(return_value=[FAKE_INSTALLATION]),
        ),
        patch("d1ff.web.api.upsert_api_key_for_installation", mock_upsert),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            client.cookies.set("session", session_cookie)
            response = await client.post("/api/settings", json={
                "installation_id": 42, "provider": "openai", "model": "gpt-4o",
                "api_key": "sk-test",
                "custom_endpoint": "https://my-azure.openai.azure.com",
            })

    assert response.status_code == 200
    mock_upsert.assert_called_once_with(
        42, "openai", "gpt-4o", "sk-test",
        custom_endpoint="https://my-azure.openai.azure.com",
    )


async def test_post_settings_clears_empty_endpoint(session_cookie: str) -> None:
    """Empty string custom_endpoint is normalized to None."""
    mock_upsert = AsyncMock()
    with (
        patch(
            "d1ff.web.api.InstallationRepository.list_installations_for_user",
            new=AsyncMock(return_value=[FAKE_INSTALLATION]),
        ),
        patch("d1ff.web.api.upsert_api_key_for_installation", mock_upsert),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            client.cookies.set("session", session_cookie)
            response = await client.post("/api/settings", json={
                "installation_id": 42, "provider": "openai", "model": "gpt-4o",
                "api_key": "sk-test", "custom_endpoint": "   ",
            })

    assert response.status_code == 200
    mock_upsert.assert_called_once_with(42, "openai", "gpt-4o", "sk-test", custom_endpoint=None)
