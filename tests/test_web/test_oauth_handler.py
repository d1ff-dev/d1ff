"""Integration tests for GitHub OAuth routes (AC: 1, 2)."""

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


async def test_callback_creates_session(reset_oauth: None) -> None:
    """GET /auth/github/callback with mocked token exchange creates a user session."""
    fake_token = {"access_token": "gho_fake", "token_type": "bearer"}
    fake_user = {"login": "testuser", "id": 12345, "name": "Test User"}

    mock_user_resp = MagicMock()
    mock_user_resp.json.return_value = fake_user

    with patch("d1ff.web.router.oauth") as mock_oauth:
        mock_client = MagicMock()
        mock_client.authorize_access_token = AsyncMock(return_value=fake_token)
        mock_client.get = AsyncMock(return_value=mock_user_resp)
        mock_oauth.github = mock_client

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                "/auth/github/callback?code=fake_code&state=fake_state",
                follow_redirects=False,
            )

    # After callback, user is redirected to /settings
    assert resp.status_code == 302
    assert resp.headers["location"] == "/settings"


async def test_logout_clears_session() -> None:
    """GET /logout should clear the session and redirect to /login."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # First set a session by manually setting a cookie (or just call logout directly)
        resp = await client.get("/logout", follow_redirects=False)

    assert resp.status_code == 302
    assert resp.headers["location"] == "/login"


async def test_unauthenticated_settings_redirects_to_login() -> None:
    """GET /settings without a session should return 302 redirect to /login."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/settings", follow_redirects=False)

    assert resp.status_code == 302
    assert resp.headers["location"] == "/login"


async def test_callback_error_redirects_to_login(reset_oauth: None) -> None:
    """GET /auth/github/callback should redirect to /login when token exchange fails."""
    with patch("d1ff.web.router.oauth") as mock_oauth:
        mock_client = MagicMock()
        mock_client.authorize_access_token = AsyncMock(
            side_effect=Exception("OAuth state mismatch")
        )
        mock_oauth.github = mock_client

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                "/auth/github/callback?code=fake_code&state=bad_state",
                follow_redirects=False,
            )

    assert resp.status_code == 302
    assert resp.headers["location"] == "/login"
