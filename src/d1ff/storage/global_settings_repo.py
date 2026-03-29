"""Repository for user global LLM settings (PostgreSQL)."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncConnection

from d1ff.storage.schema import user_global_settings


class GlobalSettingsRepository:
    def __init__(self, db: AsyncConnection) -> None:
        self._db = db

    async def get(self, user_id: int) -> dict[str, str | None] | None:
        result = await self._db.execute(
            select(
                user_global_settings.c.provider,
                user_global_settings.c.model,
                user_global_settings.c.encrypted_api_key,
                user_global_settings.c.custom_endpoint,
            ).where(user_global_settings.c.user_id == user_id)
        )
        row = result.mappings().first()
        if not row:
            return None
        return {
            "provider": row["provider"],
            "model": row["model"],
            "encrypted_api_key": row["encrypted_api_key"],
            "custom_endpoint": row["custom_endpoint"],
        }

    async def has_settings(self, user_id: int) -> bool:
        result = await self._db.execute(
            select(user_global_settings.c.user_id).where(user_global_settings.c.user_id == user_id)
        )
        return result.first() is not None

    async def upsert(
        self,
        user_id: int,
        provider: str,
        model: str,
        encrypted_api_key: str,
        custom_endpoint: str | None,
    ) -> None:
        now = datetime.now(UTC)
        stmt = (
            insert(user_global_settings)
            .values(
                user_id=user_id,
                provider=provider,
                model=model,
                encrypted_api_key=encrypted_api_key,
                custom_endpoint=custom_endpoint,
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_update(
                index_elements=["user_id"],
                set_={
                    "provider": provider,
                    "model": model,
                    "encrypted_api_key": encrypted_api_key,
                    "custom_endpoint": custom_endpoint,
                    "updated_at": now,
                },
            )
        )
        await self._db.execute(stmt)
        await self._db.commit()
