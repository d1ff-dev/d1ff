"""Tests for the GET /health FastAPI route."""

from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from d1ff.config import AppSettings, get_settings
from d1ff.main import app
from d1ff.observability.health_checker import HealthResponse, SubsystemHealth

# Minimal valid settings for tests
_TEST_SETTINGS = AppSettings(
    GITHUB_APP_ID=1,
    GITHUB_PRIVATE_KEY="dummy",
    GITHUB_WEBHOOK_SECRET="secret",  # type: ignore[arg-type]
    ENCRYPTION_KEY="dGVzdGtleXRlc3RrZXl0ZXN0a2V5dGVzdGs=",  # type: ignore[arg-type]
    DATABASE_URL="sqlite+aiosqlite:///./test_health.db",
    GITHUB_CLIENT_ID="test-client-id",
    GITHUB_CLIENT_SECRET="test-client-secret",  # type: ignore[arg-type]
    SESSION_SECRET_KEY="test-session-secret-key-32-bytes!!",  # type: ignore[arg-type]
)


@pytest.fixture(autouse=True)
def override_settings() -> pytest.FixtureRequest:
    """Override get_settings dependency so routes don't need real env vars."""
    app.dependency_overrides[get_settings] = lambda: _TEST_SETTINGS
    yield
    app.dependency_overrides.clear()


def _ok_response() -> tuple[HealthResponse, int]:
    ok = SubsystemHealth(status="ok")
    return HealthResponse(service=ok, sqlite=ok, llm_provider=ok, github_api=ok), 200


def _error_response() -> tuple[HealthResponse, int]:
    ok = SubsystemHealth(status="ok")
    error = SubsystemHealth(status="error", detail="unreachable")
    return HealthResponse(service=ok, sqlite=ok, llm_provider=error, github_api=ok), 503


async def test_health_returns_200_when_healthy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "d1ff.observability.router.run_health_check",
        AsyncMock(return_value=_ok_response()),
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["service"]["status"] == "ok"


async def test_health_returns_503_when_degraded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "d1ff.observability.router.run_health_check",
        AsyncMock(return_value=_error_response()),
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 503
    assert resp.json()["llm_provider"]["status"] == "error"


async def test_health_response_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "d1ff.observability.router.run_health_check",
        AsyncMock(return_value=_ok_response()),
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/health")
    body = resp.json()
    assert "service" in body
    assert "sqlite" in body
    assert "llm_provider" in body
    assert "github_api" in body
