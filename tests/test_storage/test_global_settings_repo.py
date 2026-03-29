"""Tests for global settings repository (PostgreSQL)."""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from d1ff.storage.database import dispose_engine, init_engine, run_alembic_upgrade
from d1ff.storage.global_settings_repo import GlobalSettingsRepository


@pytest.fixture
async def conn(postgres_url: str):
    run_alembic_upgrade(postgres_url)
    engine = init_engine(postgres_url)
    async with engine.connect() as connection:
        # Clean slate: remove settings then user, re-insert user with explicit id
        await connection.execute(text("DELETE FROM user_global_settings"))
        await connection.execute(text("DELETE FROM user_installations"))
        await connection.execute(text("DELETE FROM users"))
        # Reset sequence so id=1 is predictable
        await connection.execute(text("ALTER SEQUENCE users_id_seq RESTART WITH 1"))
        await connection.execute(
            text(
                "INSERT INTO users (github_id, login, encrypted_token, created_at, updated_at) "
                "VALUES (1, 'testuser', 'enc-token', now(), now())"
            )
        )
        await connection.commit()
        yield connection
    await dispose_engine()


async def test_get_returns_none(conn: AsyncConnection) -> None:
    repo = GlobalSettingsRepository(conn)
    assert await repo.get(user_id=1) is None


async def test_upsert_and_get(conn: AsyncConnection) -> None:
    repo = GlobalSettingsRepository(conn)
    await repo.upsert(
        user_id=1,
        provider="openai",
        model="gpt-4o",
        encrypted_api_key="encrypted-key-value",
        custom_endpoint=None,
    )
    result = await repo.get(user_id=1)
    assert result is not None
    assert result["provider"] == "openai"
    assert result["model"] == "gpt-4o"
    assert result["encrypted_api_key"] == "encrypted-key-value"
    assert result["custom_endpoint"] is None


async def test_upsert_updates_existing(conn: AsyncConnection) -> None:
    repo = GlobalSettingsRepository(conn)
    await repo.upsert(
        user_id=1, provider="openai", model="gpt-4o", encrypted_api_key="key1", custom_endpoint=None
    )
    await repo.upsert(
        user_id=1,
        provider="anthropic",
        model="claude-opus-4-5",
        encrypted_api_key="key2",
        custom_endpoint="https://custom.api",
    )
    result = await repo.get(user_id=1)
    assert result["provider"] == "anthropic"
    assert result["custom_endpoint"] == "https://custom.api"


async def test_has_settings(conn: AsyncConnection) -> None:
    repo = GlobalSettingsRepository(conn)
    assert await repo.has_settings(user_id=1) is False
    await repo.upsert(
        user_id=1, provider="openai", model="gpt-4o", encrypted_api_key="key1", custom_endpoint=None
    )
    assert await repo.has_settings(user_id=1) is True
