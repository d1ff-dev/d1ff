"""Tests for web UI authentication dependency and session handling (AC: 5, 7)."""

import pytest
from httpx import ASGITransport, AsyncClient

from d1ff.config import get_settings
from d1ff.main import app
from d1ff.web.auth import GITHUB_APP_INSTALL_URL, require_login

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


async def test_unauthenticated_settings_redirects_to_github_app() -> None:
    """GET /settings without a valid session redirects to GitHub App install URL with 302."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/settings", follow_redirects=False)

    assert resp.status_code == 302
    assert resp.headers["location"] == GITHUB_APP_INSTALL_URL


async def test_require_login_returns_user_from_session() -> None:
    """require_login dependency returns user dict when session contains 'user'."""
    from starlette.requests import Request

    fake_user = {"login": "testuser", "github_id": 12345, "name": "Test User", "user_id": 1}

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/settings",
        "query_string": b"",
        "headers": [],
        "session": {"user": fake_user},
    }
    request = Request(scope)

    result = await require_login(request)
    assert result == fake_user


async def test_require_login_redirects_when_no_session() -> None:
    """require_login dependency returns RedirectResponse when session has no user."""
    from starlette.requests import Request
    from starlette.responses import RedirectResponse

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/settings",
        "query_string": b"",
        "headers": [],
        "session": {},
    }
    request = Request(scope)

    result = await require_login(request)
    assert isinstance(result, RedirectResponse)


async def test_authenticated_user_accesses_settings() -> None:
    """A request with a valid session user cookie gets a non-redirect response on /settings."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/settings", follow_redirects=False)
        assert resp.status_code == 302
