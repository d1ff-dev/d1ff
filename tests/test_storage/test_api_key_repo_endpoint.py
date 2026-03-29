"""Tests for API key repository — custom endpoint persistence (PostgreSQL)."""

from unittest.mock import MagicMock

import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncConnection

from d1ff.storage.api_key_repo import get_api_key_config, upsert_api_key_for_installation
from d1ff.storage.database import dispose_engine, init_engine, run_alembic_upgrade
from d1ff.storage.installation_repo import InstallationRepository


@pytest.fixture
async def conn(postgres_url: str):
    run_alembic_upgrade(postgres_url)
    engine = init_engine(postgres_url)
    async with engine.connect() as connection:
        trans = await connection.begin()
        repo = InstallationRepository(connection)
        await repo.upsert_installation(1, "testuser", "User")
        yield connection
        await trans.rollback()
    await dispose_engine()


@pytest.fixture
def fernet_key() -> SecretStr:
    return SecretStr(Fernet.generate_key().decode())


def make_mock_settings(postgres_url: str, fernet_key: SecretStr) -> MagicMock:
    mock = MagicMock()
    mock.DATABASE_URL = postgres_url
    mock.ENCRYPTION_KEY = fernet_key
    return mock


async def test_upsert_with_custom_endpoint(
    conn: AsyncConnection, postgres_url: str, fernet_key: SecretStr
) -> None:
    mock_settings = make_mock_settings(postgres_url, fernet_key)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("d1ff.storage.api_key_repo.get_settings", lambda: mock_settings)
        await upsert_api_key_for_installation(
            1, "openai", "gpt-4o", "sk-test", custom_endpoint="https://my-proxy.com"
        )
        config = await get_api_key_config(1)

    assert config is not None
    assert config["custom_endpoint"] == "https://my-proxy.com"


async def test_upsert_without_custom_endpoint(
    conn: AsyncConnection, postgres_url: str, fernet_key: SecretStr
) -> None:
    mock_settings = make_mock_settings(postgres_url, fernet_key)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("d1ff.storage.api_key_repo.get_settings", lambda: mock_settings)
        await upsert_api_key_for_installation(
            1, "openai", "gpt-4o", "sk-test", custom_endpoint=None
        )
        config = await get_api_key_config(1)

    assert config is not None
    assert config["custom_endpoint"] is None
