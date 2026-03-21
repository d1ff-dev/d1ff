"""Tests for API key repository CRUD operations."""

import datetime
from pathlib import Path
from unittest.mock import MagicMock

import aiosqlite
import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr

from d1ff.storage.api_key_repo import (
    delete_api_key,
    get_api_key,
    get_api_key_config,
    upsert_api_key,
    upsert_api_key_for_installation,
)
from d1ff.storage.database import get_db_path, init_db
from d1ff.storage.installation_repo import upsert_installation
from d1ff.storage.models import Installation


@pytest.fixture
def db_url(tmp_path: Path) -> str:
    return f"sqlite+aiosqlite:///{tmp_path}/test.db"


@pytest.fixture
def test_fernet_key() -> SecretStr:
    return SecretStr(Fernet.generate_key().decode())


async def setup_installation(db_url: str, installation_id: int = 1) -> None:
    now = datetime.datetime.now(datetime.UTC)
    inst = Installation(
        installation_id=installation_id,
        account_login="testuser",
        account_type="User",
        created_at=now,
        updated_at=now,
    )
    await upsert_installation(db_url, inst)


async def test_upsert_and_get_api_key(db_url: str, test_fernet_key: SecretStr) -> None:
    await init_db(db_url)
    await setup_installation(db_url)

    plaintext = "sk-test-api-key-12345"
    await upsert_api_key(db_url, 1, "openai", "gpt-4o", plaintext, test_fernet_key)

    result = await get_api_key(db_url, 1, "openai", test_fernet_key)
    assert result == plaintext


async def test_stored_value_is_encrypted(db_url: str, test_fernet_key: SecretStr) -> None:
    await init_db(db_url)
    await setup_installation(db_url)

    plaintext = "sk-test-api-key-12345"
    await upsert_api_key(db_url, 1, "openai", "gpt-4o", plaintext, test_fernet_key)

    db_path = get_db_path(db_url)
    async with aiosqlite.connect(db_path) as conn, conn.execute(
        "SELECT encrypted_key FROM api_keys LIMIT 1"
    ) as cursor:
        row = await cursor.fetchone()
        assert row is not None
        stored_value = row[0]

    assert stored_value != plaintext


async def test_get_nonexistent_returns_none(db_url: str, test_fernet_key: SecretStr) -> None:
    await init_db(db_url)

    result = await get_api_key(db_url, 99999, "openai", test_fernet_key)
    assert result is None


async def test_delete_api_key(db_url: str, test_fernet_key: SecretStr) -> None:
    await init_db(db_url)
    await setup_installation(db_url)

    plaintext = "sk-test-api-key-12345"
    await upsert_api_key(db_url, 1, "openai", "gpt-4o", plaintext, test_fernet_key)
    await delete_api_key(db_url, 1, "openai")

    result = await get_api_key(db_url, 1, "openai", test_fernet_key)
    assert result is None


# ---------------------------------------------------------------------------
# Tests for the web-layer wrappers: upsert_api_key_for_installation and
# get_api_key_config — these read DATABASE_URL and ENCRYPTION_KEY from settings.
# ---------------------------------------------------------------------------


def make_mock_settings(db_url: str, fernet_key: SecretStr) -> MagicMock:
    """Build a mock AppSettings object pointing at the given temp DB."""
    mock = MagicMock()
    mock.DATABASE_URL = db_url
    mock.ENCRYPTION_KEY = fernet_key
    return mock


async def test_upsert_api_key_creates_new_record(
    db_url: str, test_fernet_key: SecretStr
) -> None:
    """upsert_api_key_for_installation inserts a row with encrypted key, provider, model."""
    await init_db(db_url)
    await setup_installation(db_url)

    mock_settings = make_mock_settings(db_url, test_fernet_key)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("d1ff.storage.api_key_repo.get_settings", lambda: mock_settings)
        row_id = await upsert_api_key_for_installation(1, "openai", "gpt-4o", "sk-test")

    assert isinstance(row_id, int)
    assert row_id > 0

    # Verify stored data via direct get_api_key
    result = await get_api_key(db_url, 1, "openai", test_fernet_key)
    assert result == "sk-test"


async def test_upsert_api_key_updates_existing_record(
    db_url: str, test_fernet_key: SecretStr
) -> None:
    """Calling upsert twice for same installation_id+provider: only one row, second call updates."""
    await init_db(db_url)
    await setup_installation(db_url)

    mock_settings = make_mock_settings(db_url, test_fernet_key)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("d1ff.storage.api_key_repo.get_settings", lambda: mock_settings)
        await upsert_api_key_for_installation(1, "openai", "gpt-4o", "sk-first")
        await upsert_api_key_for_installation(1, "openai", "gpt-4o", "sk-second")

    # Verify only one row remains
    db_path = get_db_path(db_url)
    async with aiosqlite.connect(db_path) as conn, conn.execute(
        "SELECT COUNT(*) FROM api_keys WHERE installation_id = 1 AND provider = 'openai'"
    ) as cursor:
        row = await cursor.fetchone()
        assert row is not None
        assert row[0] == 1

    # Value should be the second key
    result = await get_api_key(db_url, 1, "openai", test_fernet_key)
    assert result == "sk-second"


async def test_get_api_key_config_returns_config(
    db_url: str, test_fernet_key: SecretStr
) -> None:
    """After upsert, get_api_key_config returns provider, model, and encrypted_key not decrypted."""
    await init_db(db_url)
    await setup_installation(db_url)

    mock_settings = make_mock_settings(db_url, test_fernet_key)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("d1ff.storage.api_key_repo.get_settings", lambda: mock_settings)
        await upsert_api_key_for_installation(1, "openai", "gpt-4o", "sk-test")
        config = await get_api_key_config(1)

    assert config is not None
    assert config["provider"] == "openai"
    assert config["model"] == "gpt-4o"
    # encrypted_key must not be the plaintext
    assert "encrypted_key" in config
    assert config["encrypted_key"] != "sk-test"
    assert len(config["encrypted_key"]) > 0


async def test_get_api_key_config_returns_none_when_missing(
    db_url: str, test_fernet_key: SecretStr
) -> None:
    """get_api_key_config returns None when no row exists for the given installation_id."""
    await init_db(db_url)

    mock_settings = make_mock_settings(db_url, test_fernet_key)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("d1ff.storage.api_key_repo.get_settings", lambda: mock_settings)
        config = await get_api_key_config(99999)

    assert config is None
