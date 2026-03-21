"""Tests for settings endpoint — custom LLM endpoint configuration (AC: 1, 3)."""

import datetime
import json
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from d1ff.config import get_settings
from d1ff.main import app
from d1ff.storage.models import Installation

# Minimal env vars required by AppSettings
REQUIRED_ENV = {
    "GITHUB_APP_ID": "12345",
    "GITHUB_PRIVATE_KEY": "fake-pem-key",
    "GITHUB_WEBHOOK_SECRET": "test-webhook-secret",
    "ENCRYPTION_KEY": "dGVzdC1rZXktMzItYnl0ZXMtZm9yLWZlcm5ldA==",
    "GITHUB_CLIENT_ID": "test-client-id",
    "GITHUB_CLIENT_SECRET": "test-client-secret",
    "SESSION_SECRET_KEY": "test-session-secret-key-32-bytes!!",
    "DATABASE_URL": "sqlite+aiosqlite:///./test_settings_endpoint.db",
}

FAKE_USER = {"login": "testuser", "github_id": 12345, "name": "Test User", "user_id": 1}

FAKE_INSTALLATION = Installation(
    installation_id=42,
    account_login="testuser",
    account_type="User",
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
    """Set required environment variables and clear settings cache."""
    get_settings.cache_clear()
    for key, value in REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)
    yield
    get_settings.cache_clear()


@pytest.fixture
def session_cookie() -> str:
    from d1ff.main import _session_secret

    return make_session_cookie(FAKE_USER, _session_secret)


async def test_post_settings_saves_custom_endpoint(session_cookie: str) -> None:
    """POST /settings with custom_endpoint → upsert called with endpoint, redirects 303."""
    mock_upsert = AsyncMock(return_value=1)

    with (
        patch(
            "d1ff.web.router.upsert_api_key_for_installation",
            new=mock_upsert,
        ),
        patch(
            "d1ff.web.router.InstallationRepository.list_installations_for_user",
            new=AsyncMock(return_value=[FAKE_INSTALLATION]),
        ),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            client.cookies.set("session", session_cookie)
            resp = await client.post(
                "/settings",
                data={
                    "installation_id": "42",
                    "provider": "openai",
                    "model": "gpt-4o",
                    "api_key": "sk-test",
                    "custom_endpoint": "https://my-azure.openai.azure.com",
                },
                follow_redirects=False,
            )

    assert resp.status_code == 303
    assert resp.headers["location"] == "/settings?saved=true"
    mock_upsert.assert_called_once_with(
        42, "openai", "gpt-4o", "sk-test", custom_endpoint="https://my-azure.openai.azure.com"
    )


async def test_post_settings_clears_custom_endpoint(session_cookie: str) -> None:
    """POST /settings with empty custom_endpoint → upsert called with custom_endpoint=None."""
    mock_upsert = AsyncMock(return_value=1)

    with (
        patch(
            "d1ff.web.router.upsert_api_key_for_installation",
            new=mock_upsert,
        ),
        patch(
            "d1ff.web.router.InstallationRepository.list_installations_for_user",
            new=AsyncMock(return_value=[FAKE_INSTALLATION]),
        ),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            client.cookies.set("session", session_cookie)
            resp = await client.post(
                "/settings",
                data={
                    "installation_id": "42",
                    "provider": "openai",
                    "model": "gpt-4o",
                    "api_key": "sk-test",
                    "custom_endpoint": "",
                },
                follow_redirects=False,
            )

    assert resp.status_code == 303
    mock_upsert.assert_called_once_with(42, "openai", "gpt-4o", "sk-test", custom_endpoint=None)


async def test_post_settings_invalid_endpoint_rejected(session_cookie: str) -> None:
    """POST with custom_endpoint without http/https prefix → 400, upsert NOT called."""
    mock_upsert = AsyncMock(return_value=1)

    with (
        patch(
            "d1ff.web.router.upsert_api_key_for_installation",
            new=mock_upsert,
        ),
        patch(
            "d1ff.web.router.InstallationRepository.list_installations_for_user",
            new=AsyncMock(return_value=[FAKE_INSTALLATION]),
        ),
        patch(
            "d1ff.web.router.get_api_key_config",
            new=AsyncMock(return_value=None),
        ),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            client.cookies.set("session", session_cookie)
            resp = await client.post(
                "/settings",
                data={
                    "installation_id": "42",
                    "provider": "openai",
                    "model": "gpt-4o",
                    "api_key": "sk-test",
                    "custom_endpoint": "not-a-url",
                },
                follow_redirects=False,
            )

    assert resp.status_code == 400
    mock_upsert.assert_not_called()
    assert "http" in resp.text.lower() or "endpoint" in resp.text.lower()


async def test_settings_page_shows_existing_endpoint(session_cookie: str) -> None:
    """GET /settings with saved custom_endpoint → endpoint URL pre-filled in form."""
    saved_config = {
        "provider": "openai",
        "model": "gpt-4o",
        "encrypted_key": "enc123",
        "custom_endpoint": "https://my-endpoint.com",
    }

    with (
        patch(
            "d1ff.web.router.InstallationRepository.list_installations_for_user",
            new=AsyncMock(return_value=[FAKE_INSTALLATION]),
        ),
        patch(
            "d1ff.web.router.get_api_key_config",
            new=AsyncMock(return_value=saved_config),
        ),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            client.cookies.set("session", session_cookie)
            resp = await client.get("/settings", follow_redirects=False)

    assert resp.status_code == 200
    assert "https://my-endpoint.com" in resp.text


async def test_settings_page_shows_empty_endpoint(session_cookie: str) -> None:
    """GET /settings with custom_endpoint=None → endpoint field has empty value."""
    saved_config = {
        "provider": "openai",
        "model": "gpt-4o",
        "encrypted_key": "enc123",
        "custom_endpoint": None,
    }

    with (
        patch(
            "d1ff.web.router.InstallationRepository.list_installations_for_user",
            new=AsyncMock(return_value=[FAKE_INSTALLATION]),
        ),
        patch(
            "d1ff.web.router.get_api_key_config",
            new=AsyncMock(return_value=saved_config),
        ),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            client.cookies.set("session", session_cookie)
            resp = await client.get("/settings", follow_redirects=False)

    assert resp.status_code == 200
    assert 'name="custom_endpoint"' in resp.text
    assert "https://my-endpoint.com" not in resp.text
