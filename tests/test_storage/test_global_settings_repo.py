"""Tests for global settings repository."""

import aiosqlite
import pytest

from d1ff.storage.database import init_db
from d1ff.storage.global_settings_repo import GlobalSettingsRepository


@pytest.fixture
async def db() -> aiosqlite.Connection:
    conn = await aiosqlite.connect(":memory:")
    await conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = aiosqlite.Row
    await init_db("sqlite+aiosqlite:///:memory:", _conn_override=conn)
    # Insert a test user
    await conn.execute(
        "INSERT INTO users (github_id, login, encrypted_token, created_at, updated_at) "
        "VALUES (1, 'testuser', 'enc-token', '2024-01-01T00:00:00Z', '2024-01-01T00:00:00Z')"
    )
    await conn.commit()
    yield conn
    await conn.close()


async def test_get_returns_none_when_no_settings(db: aiosqlite.Connection) -> None:
    repo = GlobalSettingsRepository(db)
    result = await repo.get(user_id=1)
    assert result is None


async def test_upsert_and_get(db: aiosqlite.Connection) -> None:
    repo = GlobalSettingsRepository(db)
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


async def test_upsert_updates_existing(db: aiosqlite.Connection) -> None:
    repo = GlobalSettingsRepository(db)
    await repo.upsert(user_id=1, provider="openai", model="gpt-4o",
                       encrypted_api_key="key1", custom_endpoint=None)
    await repo.upsert(user_id=1, provider="anthropic", model="claude-opus-4-5",
                       encrypted_api_key="key2", custom_endpoint="https://custom.api")
    result = await repo.get(user_id=1)
    assert result["provider"] == "anthropic"
    assert result["model"] == "claude-opus-4-5"
    assert result["custom_endpoint"] == "https://custom.api"


async def test_has_settings(db: aiosqlite.Connection) -> None:
    repo = GlobalSettingsRepository(db)
    assert await repo.has_settings(user_id=1) is False
    await repo.upsert(user_id=1, provider="openai", model="gpt-4o",
                       encrypted_api_key="key1", custom_endpoint=None)
    assert await repo.has_settings(user_id=1) is True
