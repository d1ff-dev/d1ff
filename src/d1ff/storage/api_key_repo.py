"""CRUD operations for the api_keys table with encryption (PostgreSQL)."""

from datetime import UTC, datetime

from pydantic import SecretStr
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncConnection

from d1ff.config import get_settings
from d1ff.storage.encryption import decrypt_value, encrypt_value
from d1ff.storage.schema import api_keys


async def upsert_api_key(
    conn: AsyncConnection,
    installation_id: int,
    provider: str,
    model: str,
    plaintext_key: str,
    encryption_key: SecretStr,
) -> None:
    encrypted = encrypt_value(plaintext_key, encryption_key)
    now = datetime.now(UTC)
    stmt = (
        insert(api_keys)
        .values(
            installation_id=installation_id,
            provider=provider,
            model=model,
            encrypted_key=encrypted,
            created_at=now,
            updated_at=now,
        )
        .on_conflict_do_update(
            constraint="api_keys_installation_id_provider_key",
            set_={"model": model, "encrypted_key": encrypted, "updated_at": now},
        )
    )
    await conn.execute(stmt)
    await conn.commit()


async def get_api_key(
    conn: AsyncConnection,
    installation_id: int,
    provider: str,
    encryption_key: SecretStr,
) -> str | None:
    result = await conn.execute(
        select(api_keys.c.encrypted_key).where(
            (api_keys.c.installation_id == installation_id) & (api_keys.c.provider == provider)
        )
    )
    row = result.first()
    if row is None:
        return None
    return decrypt_value(row[0], encryption_key)


async def delete_api_key(
    conn: AsyncConnection,
    installation_id: int,
    provider: str,
) -> None:
    await conn.execute(
        delete(api_keys).where(
            (api_keys.c.installation_id == installation_id) & (api_keys.c.provider == provider)
        )
    )
    await conn.commit()


async def upsert_api_key_for_installation(
    installation_id: int,
    provider: str,
    model: str,
    api_key_plaintext: str,
    custom_endpoint: str | None = None,
) -> int:
    from d1ff.storage.database import get_connection  # noqa: PLC0415

    settings = get_settings()
    encrypted = encrypt_value(api_key_plaintext, settings.ENCRYPTION_KEY)
    now = datetime.now(UTC)

    async with get_connection() as conn:
        stmt = (
            insert(api_keys)
            .values(
                installation_id=installation_id,
                provider=provider,
                model=model,
                encrypted_key=encrypted,
                custom_endpoint=custom_endpoint,
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_update(
                constraint="api_keys_installation_id_provider_key",
                set_={
                    "model": model,
                    "encrypted_key": encrypted,
                    "custom_endpoint": custom_endpoint,
                    "updated_at": now,
                },
            )
            .returning(api_keys.c.id)
        )
        result = await conn.execute(stmt)
        await conn.commit()
        return int(result.scalar_one())


async def get_api_key_config(installation_id: int) -> dict[str, str | None] | None:
    from d1ff.storage.database import get_connection  # noqa: PLC0415

    async with get_connection() as conn:
        result = await conn.execute(
            select(
                api_keys.c.provider,
                api_keys.c.model,
                api_keys.c.encrypted_key,
                api_keys.c.custom_endpoint,
            ).where(api_keys.c.installation_id == installation_id)
        )
        row = result.mappings().first()
        if row is None:
            return None
        return {
            "provider": row["provider"],
            "model": row["model"],
            "encrypted_key": row["encrypted_key"],
            "custom_endpoint": row["custom_endpoint"],
        }
