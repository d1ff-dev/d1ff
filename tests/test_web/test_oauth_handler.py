"""Integration tests for GitHub OAuth routes — unified onboarding flow (AC: 1, 2, 4, 6, 7, 10)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from d1ff.config import get_settings
from d1ff.main import app

# Minimal env vars required by AppSettings
REQUIRED_ENV = {
    "GITHUB_APP_ID": "12345",
    "GITHUB_PRIVATE_KEY": "fake-pem-key",
    "GITHUB_WEBHOOK_SECRET": "test-webhook-secret",
    "ENCRYPTION_KEY": "dGVzdC1rZXktMzItYnl0ZXMtZm9yLWZlcm5ldA==",
    "GITHUB_CLIENT_ID": "test-client-id",
    "GITHUB_CLIENT_SECRET": "test-client-secret",
    "SESSION_SECRET_KEY": "test-session-secret-key-32-bytes!!",
}


@pytest.fixture(autouse=True)
def setup_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set required environment variables and clear settings cache."""
    get_settings.cache_clear()
    for key, value in REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)
    yield  # type: ignore[misc]
    get_settings.cache_clear()


@pytest.fixture
def reset_oauth() -> None:  # type: ignore[misc]
    """Reset the oauth handler registration state between tests."""
    import d1ff.github.oauth_handler as handler

    original = handler._github_registered
    handler._github_registered = False
    yield
    handler._github_registered = original


async def test_login_redirects_unauthenticated_to_github(reset_oauth: None) -> None:
    """GET /auth/github/login should redirect to github.com OAuth authorize URL."""
    from starlette.responses import RedirectResponse

    fake_redirect = RedirectResponse(
        url="https://github.com/login/oauth/authorize?client_id=test&state=fake",
        status_code=302,
    )

    with patch("d1ff.web.router.oauth") as mock_oauth:
        mock_client = MagicMock()
        mock_client.authorize_redirect = AsyncMock(return_value=fake_redirect)
        mock_oauth.github = mock_client
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/auth/github/login", follow_redirects=False)

    assert resp.status_code == 302
    assert "github.com" in resp.headers["location"]


async def test_callback_creates_user_and_syncs_installations(reset_oauth: None) -> None:
    """GET /auth/github/callback creates user, syncs installations."""
    fake_token = {"access_token": "gho_fake", "token_type": "bearer"}
    fake_user = {
        "login": "testuser",
        "id": 12345,
        "name": "Test User",
        "email": "test@example.com",
        "avatar_url": "https://avatars.example.com/u/12345",
    }
    fake_installations = {"installations": [{"id": 42}, {"id": 43}]}

    mock_user_resp = MagicMock()
    mock_user_resp.status_code = 200
    mock_user_resp.json.return_value = fake_user

    mock_installations_resp = MagicMock()
    mock_installations_resp.status_code = 200
    mock_installations_resp.json.return_value = fake_installations

    async def mock_get(url: str, token: dict = None, params: dict = None) -> MagicMock:
        if url == "user":
            return mock_user_resp
        if url == "user/installations":
            return mock_installations_resp
        raise ValueError(f"Unexpected URL: {url}")

    mock_upsert_user = AsyncMock(return_value=1)
    mock_sync_installations = AsyncMock()

    with (
        patch("d1ff.web.router.oauth") as mock_oauth,
        patch("d1ff.web.router.encrypt_value", return_value="encrypted_token_value"),
        patch.object(
            __import__(
                "d1ff.storage.installation_repo",
                fromlist=["InstallationRepository"],
            ).InstallationRepository,
            "upsert_user",
            mock_upsert_user,
        ),
        patch.object(
            __import__(
                "d1ff.storage.installation_repo",
                fromlist=["InstallationRepository"],
            ).InstallationRepository,
            "sync_user_installations",
            mock_sync_installations,
        ),
    ):
        mock_client = MagicMock()
        mock_client.authorize_access_token = AsyncMock(return_value=fake_token)
        mock_client.get = AsyncMock(side_effect=mock_get)
        mock_oauth.github = mock_client

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                "/auth/github/callback?code=fake_code&state=fake_state",
                follow_redirects=False,
            )

    assert resp.status_code == 302
    assert resp.headers["location"] == "/repositories"
    mock_upsert_user.assert_called_once_with(
        github_id=12345,
        login="testuser",
        email="test@example.com",
        avatar_url="https://avatars.example.com/u/12345",
        encrypted_token="encrypted_token_value",
    )
    mock_sync_installations.assert_called_once_with(1, [42, 43])


async def test_callback_error_redirects_to_login(reset_oauth: None) -> None:
    """GET /auth/github/callback should redirect to /login when both token exchange methods fail."""
    with (
        patch("d1ff.web.router.oauth") as mock_oauth,
        patch("d1ff.web.router._exchange_code_for_token", new=AsyncMock(return_value=None)),
    ):
        mock_client = MagicMock()
        mock_client.authorize_access_token = AsyncMock(side_effect=KeyError("OAuth state mismatch"))
        mock_oauth.github = mock_client

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                "/auth/github/callback?code=fake_code&state=bad_state",
                follow_redirects=False,
            )

    assert resp.status_code == 302
    assert resp.headers["location"] == "/login"


async def test_callback_empty_installations(reset_oauth: None) -> None:
    """OAuth callback with no installations returned still creates user and redirects."""
    fake_token = {"access_token": "gho_fake", "token_type": "bearer"}
    fake_user = {"login": "newuser", "id": 99999, "name": "New User"}
    fake_installations = {"installations": []}

    mock_user_resp = MagicMock()
    mock_user_resp.status_code = 200
    mock_user_resp.json.return_value = fake_user

    mock_installations_resp = MagicMock()
    mock_installations_resp.status_code = 200
    mock_installations_resp.json.return_value = fake_installations

    async def mock_get(url: str, token: dict = None, params: dict = None) -> MagicMock:
        if url == "user":
            return mock_user_resp
        if url == "user/installations":
            return mock_installations_resp
        raise ValueError(f"Unexpected URL: {url}")

    mock_upsert_user = AsyncMock(return_value=5)
    mock_sync_installations = AsyncMock()

    with (
        patch("d1ff.web.router.oauth") as mock_oauth,
        patch("d1ff.web.router.encrypt_value", return_value="enc_tok"),
        patch.object(
            __import__(
                "d1ff.storage.installation_repo",
                fromlist=["InstallationRepository"],
            ).InstallationRepository,
            "upsert_user",
            mock_upsert_user,
        ),
        patch.object(
            __import__(
                "d1ff.storage.installation_repo",
                fromlist=["InstallationRepository"],
            ).InstallationRepository,
            "sync_user_installations",
            mock_sync_installations,
        ),
    ):
        mock_client = MagicMock()
        mock_client.authorize_access_token = AsyncMock(return_value=fake_token)
        mock_client.get = AsyncMock(side_effect=mock_get)
        mock_oauth.github = mock_client

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                "/auth/github/callback?code=fake_code&state=fake_state",
                follow_redirects=False,
            )

    assert resp.status_code == 302
    assert resp.headers["location"] == "/repositories"
    mock_upsert_user.assert_called_once()
    mock_sync_installations.assert_called_once_with(5, [])


async def test_logout_redirects_to_login() -> None:
    """GET /logout should clear the session and redirect to /login."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/logout", follow_redirects=False)

    assert resp.status_code == 302
    assert resp.headers["location"] == "/login"
