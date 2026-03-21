"""Tests for per-installation rate limiting middleware (AD-7)."""

import hashlib
import hmac
import json
from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from d1ff.config import get_settings
from d1ff.middleware import get_limiter, limiter
from d1ff.middleware.rate_limit import _get_installation_id
from d1ff.storage.database import get_db_connection, init_db

# ---------------------------------------------------------------------------
# Unit tests — limiter module
# ---------------------------------------------------------------------------


def test_rate_limiter_module_exports() -> None:
    """limiter and get_limiter must be importable from d1ff.middleware."""
    assert limiter is not None
    assert get_limiter() is limiter


def test_limiter_is_singleton() -> None:
    """get_limiter() must return the same object on every call."""
    first = get_limiter()
    second = get_limiter()
    assert first is second


def test_get_installation_id_from_request_state() -> None:
    """Key function returns installation_id from request.state when present."""
    request = MagicMock()
    request.state.installation_id = "12345"
    result = _get_installation_id(request)
    assert result == "12345"


def test_get_installation_id_falls_back_to_ip() -> None:
    """Key function returns a non-empty string (IP) when installation_id is absent."""
    request = MagicMock()
    # Ensure installation_id attribute does not exist on state
    del request.state.installation_id
    # Patch get_remote_address to return a predictable value
    with patch("d1ff.middleware.rate_limit.get_remote_address", return_value="1.2.3.4"):
        result = _get_installation_id(request)
    assert result == "1.2.3.4"
    assert len(result) > 0


# ---------------------------------------------------------------------------
# Integration test — 429 rate limiting
# ---------------------------------------------------------------------------

WEBHOOK_SECRET = "test-rate-limit-secret"


def _make_sig(payload: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode(), msg=payload, digestmod=hashlib.sha256).hexdigest()
    return f"sha256={digest}"


@pytest.fixture
def override_rate_limit_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Override settings with HOSTED_MODE=True and RATE_LIMIT_PER_MINUTE=2."""
    get_settings.cache_clear()
    monkeypatch.setenv("GITHUB_APP_ID", "12345")
    monkeypatch.setenv("GITHUB_PRIVATE_KEY", "fake-pem-key")
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", WEBHOOK_SECRET)
    monkeypatch.setenv("ENCRYPTION_KEY", "dGVzdC1rZXktMzItYnl0ZXMtZm9yLWZlcm5ldA==")
    monkeypatch.setenv("GITHUB_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("GITHUB_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("SESSION_SECRET_KEY", "test-session-secret-key-32-bytes!!")
    monkeypatch.setenv("HOSTED_MODE", "true")
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "2")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


async def test_rate_limit_returns_429_when_exceeded(
    override_rate_limit_settings: None,
    tmp_path: pytest.TempPathFactory,
) -> None:
    """Third request in HOSTED_MODE with RATE_LIMIT_PER_MINUTE=2 must return 429."""
    import aiosqlite

    from d1ff.main import app

    db_url = f"sqlite+aiosqlite:///{tmp_path}/test_rate_limit.db"
    await init_db(db_url)

    async def _get_db_override() -> aiosqlite.Connection:  # type: ignore[return]
        async with aiosqlite.connect(f"{tmp_path}/test_rate_limit.db") as conn:
            conn.row_factory = aiosqlite.Row
            yield conn

    app.dependency_overrides[get_db_connection] = _get_db_override

    payload = json.dumps({"action": "ping"}).encode()
    sig = _make_sig(payload, WEBHOOK_SECRET)
    headers = {
        "X-Hub-Signature-256": sig,
        "X-GitHub-Event": "push",
        "X-GitHub-Delivery": "test-delivery-rate-limit",
        "Content-Type": "application/json",
    }

    # Reset limiter storage to avoid bleed from other tests
    limiter._storage.reset()  # type: ignore[union-attr]

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp1 = await client.post("/webhook/github", content=payload, headers=headers)
            resp2 = await client.post("/webhook/github", content=payload, headers=headers)
            resp3 = await client.post("/webhook/github", content=payload, headers=headers)

        assert resp1.status_code in (202, 200), f"Expected 202/200, got {resp1.status_code}"
        assert resp2.status_code in (202, 200), f"Expected 202/200, got {resp2.status_code}"
        assert resp3.status_code == 429, f"Expected 429, got {resp3.status_code}"
    finally:
        app.dependency_overrides.clear()
