"""CRUD operations for the api_keys table with encryption."""

import contextlib
import datetime

import aiosqlite
from pydantic import SecretStr

from d1ff.config import get_settings
from d1ff.storage.database import get_connection
from d1ff.storage.encryption import decrypt_value, encrypt_value


async def upsert_api_key(
    database_url: str,
    installation_id: int,
    provider: str,
    model: str,
    plaintext_key: str,
    encryption_key: SecretStr,
) -> None:
    """Encrypt and store an API key.

    One row per (installation_id, provider) using INSERT OR REPLACE.
    """
    encrypted = encrypt_value(plaintext_key, encryption_key)
    now = datetime.datetime.now(datetime.UTC).isoformat()

    async with get_connection(database_url) as conn:
        await conn.execute(
            """
            INSERT OR REPLACE INTO api_keys
                (installation_id, provider, model, encrypted_key, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (installation_id, provider, model, encrypted, now, now),
        )
        await conn.commit()


async def get_api_key(
    database_url: str,
    installation_id: int,
    provider: str,
    encryption_key: SecretStr,
) -> str | None:
    """Retrieve and decrypt an API key. Returns plaintext in memory only.

    # SECURITY: never log return value
    """
    async with get_connection(database_url) as conn, conn.execute(
        "SELECT encrypted_key FROM api_keys WHERE installation_id = ? AND provider = ?",
        (installation_id, provider),
    ) as cursor:
        row = await cursor.fetchone()
        if row is None:
            return None
        # SECURITY: never log return value
        return decrypt_value(str(row["encrypted_key"]), encryption_key)


async def delete_api_key(database_url: str, installation_id: int, provider: str) -> None:
    """Delete an API key record."""
    async with get_connection(database_url) as conn:
        await conn.execute(
            "DELETE FROM api_keys WHERE installation_id = ? AND provider = ?",
            (installation_id, provider),
        )
        await conn.commit()


# ---------------------------------------------------------------------------
# Web-layer helpers — use AppSettings for database_url and encryption_key.
# These are called from web routes where explicit key passing is not desired.
# ---------------------------------------------------------------------------


async def upsert_api_key_for_installation(
    installation_id: int,
    provider: str,
    model: str,
    api_key_plaintext: str,
    custom_endpoint: str | None = None,
) -> int:
    """Encrypt and store an API key using settings from environment.

    Web-layer wrapper — reads DATABASE_URL and ENCRYPTION_KEY from AppSettings
    so callers need not pass them explicitly.

    Returns the row id (via lastrowid from the INSERT OR REPLACE).
    # SECURITY: never log api_key_plaintext
    """
    settings = get_settings()
    encrypted = encrypt_value(api_key_plaintext, settings.ENCRYPTION_KEY)
    now = datetime.datetime.now(datetime.UTC).isoformat()

    async with get_connection(settings.DATABASE_URL) as conn:
        # Idempotent migration: add custom_endpoint column if it does not exist yet
        with contextlib.suppress(aiosqlite.OperationalError):
            await conn.execute("ALTER TABLE api_keys ADD COLUMN custom_endpoint TEXT")
        cursor = await conn.execute(
            """
            INSERT OR REPLACE INTO api_keys
                (installation_id, provider, model, encrypted_key,
                 custom_endpoint, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (installation_id, provider, model, encrypted, custom_endpoint, now, now),
        )
        await conn.commit()
        return int(cursor.lastrowid or 0)


async def get_api_key_config(installation_id: int) -> dict[str, str | None] | None:
    """Return provider, model, encrypted_key, and custom_endpoint for an installation.

    Web-layer function — reads DATABASE_URL from AppSettings.
    NEVER decrypts the key — returns encrypted_key only.
    Decryption happens at LLM request time (Epic 3).

    Returns {"provider": str, "model": str, "encrypted_key": str,
             "custom_endpoint": str | None} or None if not found.
    """
    settings = get_settings()

    async with get_connection(settings.DATABASE_URL) as conn:
        # Idempotent migration: add custom_endpoint column if it does not exist yet
        with contextlib.suppress(aiosqlite.OperationalError):
            await conn.execute("ALTER TABLE api_keys ADD COLUMN custom_endpoint TEXT")
            await conn.commit()
        async with conn.execute(
            "SELECT provider, model, encrypted_key, custom_endpoint"
            " FROM api_keys WHERE installation_id = ?",
            (installation_id,),
        ) as cursor:
            row = await cursor.fetchone()
            if row is None:
                return None
            endpoint = row["custom_endpoint"]
            return {
                "provider": str(row["provider"]),
                "model": str(row["model"]),
                "encrypted_key": str(row["encrypted_key"]),
                "custom_endpoint": str(endpoint) if endpoint is not None else None,
            }
