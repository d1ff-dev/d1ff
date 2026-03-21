"""Tests for API key repository — custom endpoint persistence (AC: 1)."""

import datetime as dt
from pathlib import Path
from unittest.mock import MagicMock

import aiosqlite
import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr

from d1ff.storage.api_key_repo import get_api_key_config, upsert_api_key_for_installation
from d1ff.storage.database import get_db_path, init_db
from d1ff.storage.encryption import encrypt_value
from d1ff.storage.installation_repo import upsert_installation
from d1ff.storage.models import Installation


@pytest.fixture
def db_url(tmp_path: Path) -> str:
    return f"sqlite+aiosqlite:///{tmp_path}/test_endpoint.db"


@pytest.fixture
def test_fernet_key() -> SecretStr:
    return SecretStr(Fernet.generate_key().decode())


def make_mock_settings(db_url: str, fernet_key: SecretStr) -> MagicMock:
    mock = MagicMock()
    mock.DATABASE_URL = db_url
    mock.ENCRYPTION_KEY = fernet_key
    return mock


async def setup_installation(db_url: str, installation_id: int = 1) -> None:
    now = dt.datetime.now(dt.UTC)
    inst = Installation(
        installation_id=installation_id,
        account_login="testuser",
        account_type="User",
        created_at=now,
        updated_at=now,
    )
    await upsert_installation(db_url, inst)


async def test_upsert_api_key_with_custom_endpoint(
    db_url: str, test_fernet_key: SecretStr
) -> None:
    """upsert_api_key_for_installation stores custom_endpoint correctly in SQLite row."""
    await init_db(db_url)
    await setup_installation(db_url)

    mock_settings = make_mock_settings(db_url, test_fernet_key)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("d1ff.storage.api_key_repo.get_settings", lambda: mock_settings)
        await upsert_api_key_for_installation(
            1, "openai", "gpt-4o", "sk-test", custom_endpoint="https://my-proxy.com"
        )

    db_path = get_db_path(db_url)
    async with aiosqlite.connect(db_path) as conn, conn.execute(
        "SELECT custom_endpoint FROM api_keys WHERE installation_id = 1"
    ) as cursor:
        row = await cursor.fetchone()
        assert row is not None
        assert row[0] == "https://my-proxy.com"


async def test_upsert_api_key_clears_custom_endpoint(
    db_url: str, test_fernet_key: SecretStr
) -> None:
    """upsert_api_key_for_installation with custom_endpoint=None stores NULL in SQLite."""
    await init_db(db_url)
    await setup_installation(db_url)

    mock_settings = make_mock_settings(db_url, test_fernet_key)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("d1ff.storage.api_key_repo.get_settings", lambda: mock_settings)
        await upsert_api_key_for_installation(
            1, "openai", "gpt-4o", "sk-test", custom_endpoint=None
        )

    db_path = get_db_path(db_url)
    async with aiosqlite.connect(db_path) as conn, conn.execute(
        "SELECT custom_endpoint FROM api_keys WHERE installation_id = 1"
    ) as cursor:
        row = await cursor.fetchone()
        assert row is not None
        assert row[0] is None


async def test_get_api_key_config_returns_custom_endpoint(
    db_url: str, test_fernet_key: SecretStr
) -> None:
    """get_api_key_config returns dict with custom_endpoint key after upsert with endpoint."""
    await init_db(db_url)
    await setup_installation(db_url)

    mock_settings = make_mock_settings(db_url, test_fernet_key)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("d1ff.storage.api_key_repo.get_settings", lambda: mock_settings)
        await upsert_api_key_for_installation(
            1, "openai", "gpt-4o", "sk-test", custom_endpoint="https://my-proxy.com"
        )
        config = await get_api_key_config(1)

    assert config is not None
    assert "custom_endpoint" in config
    assert config["custom_endpoint"] == "https://my-proxy.com"


async def test_get_api_key_config_endpoint_migration(
    db_url: str, test_fernet_key: SecretStr
) -> None:
    """Existing rows without custom_endpoint column return custom_endpoint=None (compat)."""
    await init_db(db_url)
    await setup_installation(db_url)

    # Insert a row directly without custom_endpoint column (simulate pre-migration state)
    db_path = get_db_path(db_url)
    now = dt.datetime.now(dt.UTC).isoformat()
    encrypted = encrypt_value("sk-test", test_fernet_key)

    async with aiosqlite.connect(db_path) as conn:
        # Drop and recreate api_keys without custom_endpoint to simulate old schema
        await conn.execute("DROP TABLE IF EXISTS api_keys_old")
        await conn.execute("ALTER TABLE api_keys RENAME TO api_keys_old")
        await conn.execute(
            """
            CREATE TABLE api_keys (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                installation_id INTEGER NOT NULL,
                provider        TEXT NOT NULL,
                model           TEXT NOT NULL,
                encrypted_key   TEXT NOT NULL,
                created_at      TEXT NOT NULL,
                updated_at      TEXT NOT NULL,
                FOREIGN KEY (installation_id) REFERENCES installations(installation_id),
                UNIQUE (installation_id, provider)
            )
            """
        )
        await conn.execute(
            "INSERT INTO api_keys"
            " (installation_id, provider, model, encrypted_key, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (1, "openai", "gpt-4o", encrypted, now, now),
        )
        await conn.commit()

    # get_api_key_config should run the migration and return custom_endpoint=None
    mock_settings = make_mock_settings(db_url, test_fernet_key)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("d1ff.storage.api_key_repo.get_settings", lambda: mock_settings)
        config = await get_api_key_config(1)

    assert config is not None
    assert "custom_endpoint" in config
    assert config["custom_endpoint"] is None
