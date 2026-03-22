"""Database initialization and connection management for aiosqlite."""

import contextlib
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite


def get_db_path(database_url: str) -> Path:
    """Extract the filesystem path from a DATABASE_URL string.

    Example: "sqlite+aiosqlite:////data/d1ff.db" -> Path("/data/d1ff.db")
    """
    prefix = "sqlite+aiosqlite:///"
    return Path(database_url.removeprefix(prefix))


async def _init_tables(conn: aiosqlite.Connection) -> None:
    """Create all tables on the given connection. Called by init_db."""
    await conn.execute("PRAGMA foreign_keys = ON")
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS installations (
            installation_id INTEGER PRIMARY KEY,
            account_login   TEXT NOT NULL,
            account_type    TEXT NOT NULL,
            created_at      TEXT NOT NULL,
            updated_at      TEXT NOT NULL
        )
        """
    )
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS api_keys (
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
        """
        CREATE TABLE IF NOT EXISTS repositories (
            id              INTEGER PRIMARY KEY,
            installation_id INTEGER NOT NULL
                REFERENCES installations(installation_id) ON DELETE CASCADE,
            repo_name       TEXT NOT NULL,
            full_name       TEXT NOT NULL,
            private         INTEGER NOT NULL DEFAULT 0,
            created_at      TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS pr_states (
            installation_id INTEGER NOT NULL,
            repo_full_name  TEXT NOT NULL,
            pr_number       INTEGER NOT NULL,
            state           TEXT NOT NULL DEFAULT 'active',
            updated_at      TEXT NOT NULL,
            PRIMARY KEY (installation_id, repo_full_name, pr_number)
        )
        """
    )
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS feedback_reactions (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            comment_id       INTEGER NOT NULL,
            reaction_type    TEXT NOT NULL,
            installation_id  INTEGER NOT NULL,
            pr_number        INTEGER NOT NULL,
            repo_full_name   TEXT NOT NULL,
            created_at       TEXT NOT NULL
        )
        """
    )
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            github_id       INTEGER UNIQUE NOT NULL,
            login           TEXT NOT NULL,
            email           TEXT,
            avatar_url      TEXT,
            encrypted_token TEXT NOT NULL,
            created_at      TEXT NOT NULL,
            updated_at      TEXT NOT NULL
        )
        """
    )
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS user_installations (
            user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            installation_id INTEGER NOT NULL REFERENCES installations(installation_id) ON DELETE CASCADE,
            PRIMARY KEY (user_id, installation_id)
        )
        """
    )
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS user_global_settings (
            user_id          INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            provider         TEXT NOT NULL,
            model            TEXT NOT NULL,
            encrypted_api_key TEXT NOT NULL,
            custom_endpoint  TEXT,
            created_at       TEXT NOT NULL,
            updated_at       TEXT NOT NULL
        )
        """
    )
    # Idempotent migration: add suspended column if it does not exist yet
    with contextlib.suppress(aiosqlite.OperationalError):
        await conn.execute(
            "ALTER TABLE installations ADD COLUMN suspended INTEGER NOT NULL DEFAULT 0"
        )
    # Idempotent migration: add custom_endpoint column if it does not exist yet
    with contextlib.suppress(aiosqlite.OperationalError):
        await conn.execute("ALTER TABLE api_keys ADD COLUMN custom_endpoint TEXT")
    await conn.commit()


async def init_db(
    database_url: str,
    _conn_override: aiosqlite.Connection | None = None,
) -> None:
    """Initialize the SQLite database, creating tables if they do not exist.

    ``_conn_override`` is intended for tests only — when provided the caller's
    in-memory connection is used directly and no file is created.
    """
    if _conn_override is not None:
        await _init_tables(_conn_override)
        return

    path = get_db_path(database_url)
    path.parent.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(path) as conn:
        await _init_tables(conn)


@asynccontextmanager
async def get_connection(database_url: str) -> AsyncGenerator[aiosqlite.Connection, None]:
    """Yield an aiosqlite connection with row_factory set to aiosqlite.Row.

    A fresh connection is opened and closed for each operation — no shared global connection.
    """
    path = get_db_path(database_url)
    async with aiosqlite.connect(path) as conn:
        await conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = aiosqlite.Row
        yield conn


async def get_db_connection() -> AsyncGenerator[aiosqlite.Connection, None]:
    """FastAPI dependency that yields an aiosqlite connection.

    Uses the DATABASE_URL from AppSettings. Intended for use with FastAPI Depends().
    """
    from d1ff.config import get_settings  # local import to avoid circular dependency

    settings = get_settings()
    async with get_connection(settings.DATABASE_URL) as conn:
        yield conn
