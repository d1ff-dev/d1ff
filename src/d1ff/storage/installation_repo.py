"""CRUD operations for the installations and repositories tables (PostgreSQL)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncConnection

from d1ff.storage.models import Installation, User
from d1ff.storage.schema import installations, repositories, user_installations, users

if TYPE_CHECKING:
    from d1ff.webhook.models import RepositoryInfo


class InstallationRepository:
    """Repository for installation and repository CRUD operations."""

    def __init__(self, db: AsyncConnection) -> None:
        self._db = db

    async def upsert_installation(
        self,
        installation_id: int,
        account_login: str,
        account_type: str,
        suspended: bool = False,
    ) -> None:
        now = datetime.now(UTC)
        stmt = (
            insert(installations)
            .values(
                installation_id=installation_id,
                account_login=account_login,
                account_type=account_type,
                suspended=suspended,
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_update(
                index_elements=["installation_id"],
                set_={
                    "account_login": account_login,
                    "account_type": account_type,
                    "suspended": suspended,
                    "updated_at": now,
                },
            )
        )
        await self._db.execute(stmt)
        await self._db.commit()

    async def upsert_repositories(
        self,
        installation_id: int,
        repos_list: list[RepositoryInfo],
    ) -> None:
        for repo in repos_list:
            stmt = (
                insert(repositories)
                .values(
                    id=repo.id,
                    installation_id=installation_id,
                    repo_name=repo.name,
                    full_name=repo.full_name,
                    private=repo.private,
                    created_at=datetime.now(UTC),
                )
                .on_conflict_do_update(
                    index_elements=["id"],
                    set_={
                        "repo_name": repo.name,
                        "full_name": repo.full_name,
                        "private": repo.private,
                        "installation_id": installation_id,
                    },
                )
            )
            await self._db.execute(stmt)
        await self._db.commit()

    async def delete_installation(self, installation_id: int) -> None:
        await self._db.execute(
            delete(installations).where(installations.c.installation_id == installation_id)
        )
        await self._db.commit()

    async def update_installation_status(self, installation_id: int, suspended: bool) -> None:
        now = datetime.now(UTC)
        await self._db.execute(
            update(installations)
            .where(installations.c.installation_id == installation_id)
            .values(suspended=suspended, updated_at=now)
        )
        await self._db.commit()

    async def get_installation(self, installation_id: int) -> Installation | None:
        result = await self._db.execute(
            select(installations).where(installations.c.installation_id == installation_id)
        )
        row = result.mappings().first()
        if row is None:
            return None
        return Installation(
            installation_id=row["installation_id"],
            account_login=row["account_login"],
            account_type=row["account_type"],
            suspended=row["suspended"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    async def list_installations(self) -> list[Installation]:
        result = await self._db.execute(
            select(installations).order_by(installations.c.installation_id)
        )
        return [
            Installation(
                installation_id=row["installation_id"],
                account_login=row["account_login"],
                account_type=row["account_type"],
                suspended=row["suspended"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in result.mappings().fetchall()
        ]

    async def upsert_user(
        self,
        github_id: int,
        login: str,
        email: str | None,
        avatar_url: str | None,
        encrypted_token: str,
    ) -> int:
        now = datetime.now(UTC)
        stmt = (
            insert(users)
            .values(
                github_id=github_id,
                login=login,
                email=email,
                avatar_url=avatar_url,
                encrypted_token=encrypted_token,
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_update(
                index_elements=["github_id"],
                set_={
                    "login": login,
                    "email": email,
                    "avatar_url": avatar_url,
                    "encrypted_token": encrypted_token,
                    "updated_at": now,
                },
            )
            .returning(users.c.id)
        )
        result = await self._db.execute(stmt)
        await self._db.commit()
        return int(result.scalar_one())

    async def sync_user_installations(self, user_id: int, installation_ids: list[int]) -> None:
        await self._db.execute(
            delete(user_installations).where(user_installations.c.user_id == user_id)
        )
        for inst_id in installation_ids:
            exists = await self._db.execute(
                select(installations.c.installation_id).where(
                    installations.c.installation_id == inst_id
                )
            )
            if exists.first() is not None:
                await self._db.execute(
                    insert(user_installations)
                    .values(user_id=user_id, installation_id=inst_id)
                    .on_conflict_do_nothing()
                )
        await self._db.commit()

    async def list_installations_for_user(self, user_id: int) -> list[Installation]:
        stmt = (
            select(installations)
            .join(
                user_installations,
                installations.c.installation_id == user_installations.c.installation_id,
            )
            .where(user_installations.c.user_id == user_id)
            .order_by(installations.c.installation_id)
        )
        result = await self._db.execute(stmt)
        return [
            Installation(
                installation_id=row["installation_id"],
                account_login=row["account_login"],
                account_type=row["account_type"],
                suspended=row["suspended"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in result.mappings().fetchall()
        ]

    async def get_user_by_github_id(self, github_id: int) -> User | None:
        result = await self._db.execute(
            select(
                users.c.id,
                users.c.github_id,
                users.c.login,
                users.c.email,
                users.c.avatar_url,
                users.c.created_at,
                users.c.updated_at,
            ).where(users.c.github_id == github_id)
        )
        row = result.mappings().first()
        if row is None:
            return None
        return User(
            id=row["id"],
            github_id=row["github_id"],
            login=row["login"],
            email=row["email"],
            avatar_url=row["avatar_url"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    async def delete_repository(self, installation_id: int, repo_id: int) -> None:
        await self._db.execute(
            delete(repositories).where(
                (repositories.c.installation_id == installation_id) & (repositories.c.id == repo_id)
            )
        )
        await self._db.commit()
