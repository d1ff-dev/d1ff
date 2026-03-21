"""Tests for the settings page — API key and provider configuration UI (AC: 3, 5)."""

import datetime
import json
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from d1ff.config import get_settings
from d1ff.main import app
from d1ff.storage.models import Installation
from d1ff.web.router import GITHUB_APP_INSTALL_URL

# Minimal env vars required by AppSettings
REQUIRED_ENV = {
    "GITHUB_APP_ID": "12345",
    "GITHUB_PRIVATE_KEY": "fake-pem-key",
    "GITHUB_WEBHOOK_SECRET": "test-webhook-secret",
    "ENCRYPTION_KEY": "dGVzdC1rZXktMzItYnl0ZXMtZm9yLWZlcm5ldA==",
    "GITHUB_CLIENT_ID": "test-client-id",
    "GITHUB_CLIENT_SECRET": "test-client-secret",
    "SESSION_SECRET_KEY": "test-session-secret-key-32-bytes!!",
    "DATABASE_URL": "sqlite+aiosqlite:///./test_settings.db",
}

FAKE_USER = {"login": "testuser", "github_id": 12345, "name": "Test User", "user_id": 1}


def make_session_cookie(user: dict, secret_key: str) -> str:
    """Craft a signed session cookie that Starlette's SessionMiddleware will accept.

    Starlette uses itsdangerous.TimestampSigner with base64-encoded JSON payload.
    """
    import base64

    from itsdangerous import TimestampSigner

    signer = TimestampSigner(secret_key)
    data = base64.b64encode(json.dumps({"user": user}).encode("utf-8"))
    return signer.sign(data).decode("utf-8")


FAKE_INSTALLATION = Installation(
    installation_id=42,
    account_login="testuser",
    account_type="User",
    suspended=False,
    created_at=datetime.datetime(2024, 1, 1, tzinfo=datetime.UTC),
    updated_at=datetime.datetime(2024, 1, 1, tzinfo=datetime.UTC),
)


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
    # Use the actual session secret that the middleware was created with at import time.
    # This may come from .env or fall back to "dev-placeholder-not-for-production".
    from d1ff.main import _session_secret

    return make_session_cookie(FAKE_USER, _session_secret)


async def test_settings_page_unauthenticated_redirects_to_github_app() -> None:
    """GET /settings without session → 302 to GitHub App install URL."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/settings", follow_redirects=False)

    assert resp.status_code == 302
    assert resp.headers["location"] == GITHUB_APP_INSTALL_URL


async def test_settings_page_shows_installations(session_cookie: str) -> None:
    """Authenticated session, mock list_installations_for_user returns one installation; form renders."""
    with (
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
            resp = await client.get("/settings", follow_redirects=False)

    assert resp.status_code == 200
    assert "testuser" in resp.text
    assert 'name="installation_id"' in resp.text
    assert 'name="provider"' in resp.text
    assert 'name="api_key"' in resp.text


async def test_settings_page_shows_existing_config(session_cookie: str) -> None:
    """Authenticated session with saved config → form pre-fills provider and model (not the key)."""
    saved_config = {"provider": "anthropic", "model": "claude-opus-4-5", "encrypted_key": "enc123"}

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
    assert "selected" in resp.text
    assert "anthropic" in resp.text
    assert "claude-opus-4-5" in resp.text
    assert "enc123" not in resp.text
    assert "Key saved" in resp.text


async def test_post_settings_saves_config(session_cookie: str) -> None:
    """POST /settings with valid form data calls upsert_api_key_for_installation, redirects 303."""
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
                    "provider": "anthropic",
                    "model": "claude-opus-4-5",
                    "api_key": "sk-test",
                },
                follow_redirects=False,
            )

    assert resp.status_code == 303
    assert resp.headers["location"] == "/settings?saved=true"
    mock_upsert.assert_called_once_with(
        42, "anthropic", "claude-opus-4-5", "sk-test", custom_endpoint=None
    )


async def test_post_settings_unauthenticated_redirects() -> None:
    """POST /settings without session → 302 to GitHub App install URL."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/settings",
            data={
                "installation_id": "42",
                "provider": "anthropic",
                "model": "claude-opus-4-5",
                "api_key": "sk-test",
            },
            follow_redirects=False,
        )

    assert resp.status_code == 302
    assert resp.headers["location"] == GITHUB_APP_INSTALL_URL


async def test_post_settings_invalid_provider_rejected(session_cookie: str) -> None:
    """POST with invalid provider → does NOT call upsert, returns 400 error response."""
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
                    "provider": "invalid",
                    "model": "gpt-4o",
                    "api_key": "sk-test",
                },
                follow_redirects=False,
            )

    assert resp.status_code == 400
    mock_upsert.assert_not_called()
    assert "Invalid provider" in resp.text


async def test_post_settings_rejects_unowned_installation(session_cookie: str) -> None:
    """POST with installation_id not owned by user → 403 error."""
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
                    "installation_id": "99999",  # not owned by testuser
                    "provider": "openai",
                    "model": "gpt-4o",
                    "api_key": "sk-test",
                },
                follow_redirects=False,
            )

    assert resp.status_code == 403
    mock_upsert.assert_not_called()
    assert "not owned" in resp.text or "not found" in resp.text


async def test_settings_page_success_message(session_cookie: str) -> None:
    """GET /settings?saved=true → page shows success confirmation text."""
    with (
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
            resp = await client.get("/settings?saved=true", follow_redirects=False)

    assert resp.status_code == 200
    assert "Settings saved successfully" in resp.text
