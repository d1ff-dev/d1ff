"""Repository for user global LLM settings."""

from datetime import UTC, datetime

import aiosqlite


class GlobalSettingsRepository:
    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def get(self, user_id: int) -> dict[str, str | None] | None:
        cursor = await self._db.execute(
            "SELECT provider, model, encrypted_api_key, custom_endpoint "
            "FROM user_global_settings WHERE user_id = ?",
            (user_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return {
            "provider": row["provider"],
            "model": row["model"],
            "encrypted_api_key": row["encrypted_api_key"],
            "custom_endpoint": row["custom_endpoint"],
        }

    async def has_settings(self, user_id: int) -> bool:
        cursor = await self._db.execute(
            "SELECT 1 FROM user_global_settings WHERE user_id = ?",
            (user_id,),
        )
        return await cursor.fetchone() is not None

    async def upsert(
        self,
        user_id: int,
        provider: str,
        model: str,
        encrypted_api_key: str,
        custom_endpoint: str | None,
    ) -> None:
        now = datetime.now(UTC).isoformat()
        await self._db.execute(
            """
            INSERT INTO user_global_settings
                (user_id, provider, model, encrypted_api_key, custom_endpoint, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (user_id) DO UPDATE SET
                provider = excluded.provider,
                model = excluded.model,
                encrypted_api_key = excluded.encrypted_api_key,
                custom_endpoint = excluded.custom_endpoint,
                updated_at = excluded.updated_at
            """,
            (user_id, provider, model, encrypted_api_key, custom_endpoint, now, now),
        )
        await self._db.commit()
