"""Tests for API key repository CRUD operations (PostgreSQL)."""

import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from d1ff.storage.api_key_repo import delete_api_key, get_api_key, upsert_api_key
from d1ff.storage.database import dispose_engine, init_engine, run_alembic_upgrade
from d1ff.storage.installation_repo import InstallationRepository


@pytest.fixture
async def conn(postgres_url: str):
    run_alembic_upgrade(postgres_url)
    engine = init_engine(postgres_url)
    async with engine.connect() as connection:
        trans = await connection.begin()
        yield connection
        await trans.rollback()
    await dispose_engine()


@pytest.fixture
def fernet_key() -> SecretStr:
    return SecretStr(Fernet.generate_key().decode())


@pytest.fixture
async def conn_with_installation(conn: AsyncConnection) -> AsyncConnection:
    repo = InstallationRepository(conn)
    await repo.upsert_installation(1, "testuser", "User")
    return conn


async def test_upsert_and_get_api_key(
    conn_with_installation: AsyncConnection, fernet_key: SecretStr
) -> None:
    plaintext = "sk-test-api-key-12345"
    await upsert_api_key(conn_with_installation, 1, "openai", "gpt-4o", plaintext, fernet_key)
    result = await get_api_key(conn_with_installation, 1, "openai", fernet_key)
    assert result == plaintext


async def test_stored_value_is_encrypted(
    conn_with_installation: AsyncConnection, fernet_key: SecretStr
) -> None:
    plaintext = "sk-test-api-key-12345"
    await upsert_api_key(conn_with_installation, 1, "openai", "gpt-4o", plaintext, fernet_key)
    result = await conn_with_installation.execute(
        text("SELECT encrypted_key FROM api_keys LIMIT 1")
    )
    row = result.fetchone()
    assert row is not None
    assert row[0] != plaintext


async def test_get_nonexistent_returns_none(conn: AsyncConnection, fernet_key: SecretStr) -> None:
    result = await get_api_key(conn, 99999, "openai", fernet_key)
    assert result is None


async def test_delete_api_key(
    conn_with_installation: AsyncConnection, fernet_key: SecretStr
) -> None:
    await upsert_api_key(conn_with_installation, 1, "openai", "gpt-4o", "sk-test", fernet_key)
    await delete_api_key(conn_with_installation, 1, "openai")
    result = await get_api_key(conn_with_installation, 1, "openai", fernet_key)
    assert result is None
