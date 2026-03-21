"""CRUD operations for the installations and repositories tables."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

import aiosqlite

from d1ff.storage.database import get_connection
from d1ff.storage.models import Installation, User

if TYPE_CHECKING:
    from d1ff.webhook.models import RepositoryInfo


class InstallationRepository:
    """Repository for installation and repository CRUD operations.

    Accepts a database connection via dependency injection — does NOT open connections
    internally. Uses aiosqlite directly (not SQLAlchemy).
    """

    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def upsert_installation(
        self,
        installation_id: int,
        account_login: str,
        account_type: str,
        suspended: bool = False,
    ) -> None:
        """Insert or replace an installation record."""
        now = datetime.datetime.now(datetime.UTC).isoformat()
        await self._db.execute(
            """
            INSERT INTO installations
                (installation_id, account_login, account_type, suspended, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(installation_id) DO UPDATE SET
                account_login = excluded.account_login,
                account_type  = excluded.account_type,
                suspended     = excluded.suspended,
                updated_at    = excluded.updated_at
            """,
            (installation_id, account_login, account_type, int(suspended), now, now),
        )
        await self._db.commit()

    async def upsert_repositories(
        self,
        installation_id: int,
        repositories: list[RepositoryInfo],
    ) -> None:
        """Insert or replace repository records for an installation."""
        for repo in repositories:
            await self._db.execute(
                """
                INSERT INTO repositories
                    (id, installation_id, repo_name, full_name, private)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    repo_name       = excluded.repo_name,
                    full_name       = excluded.full_name,
                    private         = excluded.private,
                    installation_id = excluded.installation_id
                """,
                (repo.id, installation_id, repo.name, repo.full_name, int(repo.private)),
            )
        await self._db.commit()

    async def delete_installation(self, installation_id: int) -> None:
        """Delete an installation and its associated repositories (cascade)."""
        await self._db.execute(
            "DELETE FROM installations WHERE installation_id = ?",
            (installation_id,),
        )
        await self._db.commit()

    async def update_installation_status(
        self, installation_id: int, suspended: bool
    ) -> None:
        """Update the suspended status of an installation."""
        now = datetime.datetime.now(datetime.UTC).isoformat()
        await self._db.execute(
            "UPDATE installations SET suspended = ?, updated_at = ? WHERE installation_id = ?",
            (int(suspended), now, installation_id),
        )
        await self._db.commit()

    async def get_installation(self, installation_id: int) -> Installation | None:
        """Retrieve an installation by ID, or None if not found."""
        async with self._db.execute(
            "SELECT installation_id, account_login, account_type, suspended, created_at, "
            "updated_at FROM installations WHERE installation_id = ?",
            (installation_id,),
        ) as cursor:
            row = await cursor.fetchone()
            if row is None:
                return None
            return Installation(
                installation_id=int(row["installation_id"]),
                account_login=str(row["account_login"]),
                account_type=str(row["account_type"]),
                suspended=bool(row["suspended"]),
                created_at=datetime.datetime.fromisoformat(str(row["created_at"])),
                updated_at=datetime.datetime.fromisoformat(str(row["updated_at"])),
            )

    async def list_installations(self) -> list[Installation]:
        """Return all installation records."""
        async with self._db.execute(
            "SELECT installation_id, account_login, account_type, suspended, created_at, "
            "updated_at FROM installations ORDER BY installation_id"
        ) as cursor:
            rows = await cursor.fetchall()
            return [
                Installation(
                    installation_id=int(row["installation_id"]),
                    account_login=str(row["account_login"]),
                    account_type=str(row["account_type"]),
                    suspended=bool(row["suspended"]),
                    created_at=datetime.datetime.fromisoformat(str(row["created_at"])),
                    updated_at=datetime.datetime.fromisoformat(str(row["updated_at"])),
                )
                for row in rows
            ]

    async def upsert_user(
        self,
        github_id: int,
        login: str,
        email: str | None,
        avatar_url: str | None,
        encrypted_token: str,
    ) -> int:
        """Insert or update a user record. Returns the user's row id."""
        now = datetime.datetime.now(datetime.UTC).isoformat()
        cursor = await self._db.execute(
            """
            INSERT INTO users (github_id, login, email, avatar_url, encrypted_token, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(github_id) DO UPDATE SET
                login           = excluded.login,
                email           = excluded.email,
                avatar_url      = excluded.avatar_url,
                encrypted_token = excluded.encrypted_token,
                updated_at      = excluded.updated_at
            """,
            (github_id, login, email, avatar_url, encrypted_token, now, now),
        )
        await self._db.commit()
        # On INSERT, lastrowid is the new row. On UPDATE, lastrowid may be 0,
        # so fall back to a SELECT in that case.
        if cursor.lastrowid:
            return cursor.lastrowid
        async with self._db.execute(
            "SELECT id FROM users WHERE github_id = ?", (github_id,)
        ) as select_cursor:
            row = await select_cursor.fetchone()
            return int(row["id"])

    async def sync_user_installations(
        self, user_id: int, installation_ids: list[int]
    ) -> None:
        """Replace all user_installations for a user with the given installation IDs.

        Only links to installations that actually exist in the installations table.
        This is a full sync — removes stale links and adds new ones.
        """
        await self._db.execute(
            "DELETE FROM user_installations WHERE user_id = ?", (user_id,)
        )
        for inst_id in installation_ids:
            await self._db.execute(
                """
                INSERT OR IGNORE INTO user_installations (user_id, installation_id)
                SELECT ?, installation_id FROM installations WHERE installation_id = ?
                """,
                (user_id, inst_id),
            )
        await self._db.commit()

    async def list_installations_for_user(self, user_id: int) -> list[Installation]:
        """Return installations linked to a user via user_installations join."""
        async with self._db.execute(
            """
            SELECT i.installation_id, i.account_login, i.account_type,
                   i.suspended, i.created_at, i.updated_at
            FROM installations i
            INNER JOIN user_installations ui ON i.installation_id = ui.installation_id
            WHERE ui.user_id = ?
            ORDER BY i.installation_id
            """,
            (user_id,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [
                Installation(
                    installation_id=int(row["installation_id"]),
                    account_login=str(row["account_login"]),
                    account_type=str(row["account_type"]),
                    suspended=bool(row["suspended"]),
                    created_at=datetime.datetime.fromisoformat(str(row["created_at"])),
                    updated_at=datetime.datetime.fromisoformat(str(row["updated_at"])),
                )
                for row in rows
            ]

    async def get_user_by_github_id(self, github_id: int) -> User | None:
        """Retrieve a user by their GitHub ID."""
        async with self._db.execute(
            "SELECT id, github_id, login, email, avatar_url, created_at, updated_at "
            "FROM users WHERE github_id = ?",
            (github_id,),
        ) as cursor:
            row = await cursor.fetchone()
            if row is None:
                return None
            return User(
                id=int(row["id"]),
                github_id=int(row["github_id"]),
                login=str(row["login"]),
                email=row["email"],
                avatar_url=row["avatar_url"],
                created_at=datetime.datetime.fromisoformat(str(row["created_at"])),
                updated_at=datetime.datetime.fromisoformat(str(row["updated_at"])),
            )

    async def delete_repository(self, installation_id: int, repo_id: int) -> None:
        """Delete a single repository record."""
        await self._db.execute(
            "DELETE FROM repositories WHERE installation_id = ? AND id = ?",
            (installation_id, repo_id),
        )
        await self._db.commit()


# ---------------------------------------------------------------------------
# Module-level helper functions — backward-compatible with Stories 1.x tests
# ---------------------------------------------------------------------------


async def upsert_installation(database_url: str, installation: Installation) -> None:
    """Insert or replace an installation record."""
    async with get_connection(database_url) as conn:
        now = installation.updated_at.isoformat()
        created = installation.created_at.isoformat()
        await conn.execute(
            """
            INSERT INTO installations
                (installation_id, account_login, account_type, suspended, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(installation_id) DO UPDATE SET
                account_login = excluded.account_login,
                account_type  = excluded.account_type,
                suspended     = excluded.suspended,
                updated_at    = excluded.updated_at
            """,
            (
                installation.installation_id,
                installation.account_login,
                installation.account_type,
                int(installation.suspended),
                created,
                now,
            ),
        )
        await conn.commit()


async def get_installation(database_url: str, installation_id: int) -> Installation | None:
    """Retrieve an installation by ID, or None if not found."""
    async with get_connection(database_url) as conn, conn.execute(
        "SELECT installation_id, account_login, account_type, suspended, created_at, updated_at "
        "FROM installations WHERE installation_id = ?",
        (installation_id,),
    ) as cursor:
        row = await cursor.fetchone()
        if row is None:
            return None
        return Installation(
            installation_id=int(row["installation_id"]),
            account_login=str(row["account_login"]),
            account_type=str(row["account_type"]),
            suspended=bool(row["suspended"]),
            created_at=datetime.datetime.fromisoformat(str(row["created_at"])),
            updated_at=datetime.datetime.fromisoformat(str(row["updated_at"])),
        )


async def delete_installation(database_url: str, installation_id: int) -> None:
    """Delete an installation record by ID."""
    async with get_connection(database_url) as conn:
        await conn.execute(
            "DELETE FROM installations WHERE installation_id = ?",
            (installation_id,),
        )
        await conn.commit()
