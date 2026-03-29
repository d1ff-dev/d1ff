"""Tests for d1ff.observability.health_checker."""

from unittest.mock import AsyncMock, patch

import pytest

from d1ff.config import AppSettings
from d1ff.observability.health_checker import (
    SubsystemHealth,
    _health_cache,
    check_database,
    run_health_check,
)
from d1ff.storage.database import dispose_engine, init_engine, run_alembic_upgrade


@pytest.fixture
def app_settings(postgres_url: str) -> AppSettings:
    """Return AppSettings pointing to the test PostgreSQL DB."""
    return AppSettings(
        GITHUB_APP_ID=1,
        GITHUB_PRIVATE_KEY="dummy",
        GITHUB_WEBHOOK_SECRET="secret",  # type: ignore[arg-type]
        ENCRYPTION_KEY="dGVzdGtleXRlc3RrZXl0ZXN0a2V5dGVzdGs=",  # type: ignore[arg-type]
        DATABASE_URL=postgres_url,
        GITHUB_CLIENT_ID="test-client-id",
        GITHUB_CLIENT_SECRET="test-client-secret",  # type: ignore[arg-type]
        SESSION_SECRET_KEY="test-session-secret-key-32-bytes!!",  # type: ignore[arg-type]
    )


async def test_database_check_ok(postgres_url: str) -> None:
    run_alembic_upgrade(postgres_url)
    init_engine(postgres_url)
    try:
        result = await check_database()
        assert result.status == "ok"
        assert result.detail is None
    finally:
        await dispose_engine()


async def test_database_check_error() -> None:
    # Ensure no engine is initialized so check_database() raises
    await dispose_engine()
    result = await check_database()
    assert result.status == "error"
    assert result.detail is not None


async def test_run_health_check_all_ok(app_settings: AppSettings) -> None:
    run_alembic_upgrade(app_settings.DATABASE_URL)
    init_engine(app_settings.DATABASE_URL)
    ok = SubsystemHealth(status="ok")

    # Clear cache so fresh checks run
    _health_cache.clear()

    with (
        patch(
            "d1ff.observability.health_checker.check_llm_provider",
            new_callable=AsyncMock,
            return_value=ok,
        ),
        patch(
            "d1ff.observability.health_checker.check_github_api",
            new_callable=AsyncMock,
            return_value=ok,
        ),
    ):
        response, status_code = await run_health_check(app_settings)

    assert status_code == 200
    assert response.service.status == "ok"
    assert response.database.status == "ok"
    assert response.llm_provider.status == "ok"
    assert response.github_api.status == "ok"

    await dispose_engine()


async def test_run_health_check_503_on_failure(app_settings: AppSettings) -> None:
    run_alembic_upgrade(app_settings.DATABASE_URL)
    init_engine(app_settings.DATABASE_URL)
    ok = SubsystemHealth(status="ok")
    error = SubsystemHealth(status="error", detail="Connection refused")

    _health_cache.clear()

    with (
        patch(
            "d1ff.observability.health_checker.check_llm_provider",
            new_callable=AsyncMock,
            return_value=error,
        ),
        patch(
            "d1ff.observability.health_checker.check_github_api",
            new_callable=AsyncMock,
            return_value=ok,
        ),
    ):
        response, status_code = await run_health_check(app_settings)

    assert status_code == 503
    assert response.llm_provider.status == "error"

    await dispose_engine()


async def test_llm_provider_cache(app_settings: AppSettings) -> None:
    """Verify that check_llm_provider is only called once within the 30s TTL."""
    run_alembic_upgrade(app_settings.DATABASE_URL)
    init_engine(app_settings.DATABASE_URL)
    ok = SubsystemHealth(status="ok")

    _health_cache.clear()

    mock_llm = AsyncMock(return_value=ok)
    mock_github = AsyncMock(return_value=ok)

    with (
        patch("d1ff.observability.health_checker.check_llm_provider", mock_llm),
        patch("d1ff.observability.health_checker.check_github_api", mock_github),
    ):
        # First call — should invoke the real checks
        await run_health_check(app_settings)
        # Second call within TTL — llm_provider and github_api should use cache
        await run_health_check(app_settings)

    # Each mock should be called exactly once (second call uses cache)
    assert mock_llm.call_count == 1
    assert mock_github.call_count == 1

    await dispose_engine()
