"""Tests for web UI authentication dependency and session handling (AC: 5, 7)."""

import pytest

from d1ff.config import get_settings
from d1ff.web.auth import require_login

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
    """require_login redirects to /login and saves return_to in session."""
    from starlette.requests import Request
    from starlette.responses import RedirectResponse

    session: dict[str, object] = {}
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/settings",
        "query_string": b"",
        "headers": [],
        "session": session,
        "server": ("testserver", 80),
        "scheme": "http",
    }
    request = Request(scope)

    result = await require_login(request)
    assert isinstance(result, RedirectResponse)
    assert result.headers["location"] == "/login"
    assert session["return_to"] == "http://testserver/settings"
