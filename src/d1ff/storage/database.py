"""Database engine initialization and connection management for asyncpg via SQLAlchemy."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import asyncpg
from sqlalchemy import make_url
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

_engine: AsyncEngine | None = None


def init_engine(database_url: str) -> AsyncEngine:
    """Create the global async engine. Call once at app startup."""
    global _engine  # noqa: PLW0603
    _engine = create_async_engine(database_url, pool_size=10, max_overflow=5)
    return _engine


def get_engine() -> AsyncEngine:
    """Return the global engine. Raises if init_engine() was not called."""
    assert _engine is not None, "Engine not initialized — call init_engine() first"
    return _engine


async def dispose_engine() -> None:
    """Dispose the global engine. Call at app shutdown."""
    global _engine  # noqa: PLW0603
    if _engine is not None:
        await _engine.dispose()
        _engine = None


@asynccontextmanager
async def get_connection() -> AsyncGenerator[AsyncConnection, None]:
    """Yield an AsyncConnection from the pool."""
    async with get_engine().connect() as conn:
        yield conn


async def get_db_connection() -> AsyncGenerator[AsyncConnection, None]:
    """FastAPI Depends() — yield an AsyncConnection per request."""
    async with get_engine().connect() as conn:
        yield conn


async def ensure_database_exists(database_url: str) -> None:
    """Connect to PostgreSQL; if the target DB does not exist, create it.

    Connects to the system 'postgres' DB to issue CREATE DATABASE.
    """
    url = make_url(database_url)
    # asyncpg needs a raw dsn without the +asyncpg driver prefix.
    # render_as_string(hide_password=False) is required because str() masks the password.
    raw_dsn = url.set(drivername="postgresql").render_as_string(hide_password=False)
    try:
        conn = await asyncpg.connect(dsn=raw_dsn)
        await conn.close()
    except asyncpg.InvalidCatalogNameError:
        # DB does not exist — create it via the system 'postgres' DB
        sys_dsn = url.set(drivername="postgresql", database="postgres").render_as_string(
            hide_password=False
        )
        conn = await asyncpg.connect(dsn=sys_dsn)
        try:
            db_name = url.database
            if not db_name or not db_name.replace("_", "").replace("-", "").isalnum():
                raise ValueError(f"Invalid database name: {db_name}")
            await conn.execute(f'CREATE DATABASE "{db_name}"')
        finally:
            await conn.close()


def run_alembic_upgrade(database_url: str) -> None:
    """Run alembic upgrade head programmatically.

    Runs in a dedicated thread so that asyncio.run() inside env.py works
    even when called from within an already-running event loop (e.g. async tests).
    """
    import concurrent.futures

    from alembic.config import Config

    from alembic import command

    def _upgrade() -> None:
        alembic_cfg = Config("alembic.ini")
        alembic_cfg.set_main_option("sqlalchemy.url", database_url)
        command.upgrade(alembic_cfg, "head")

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_upgrade)
        future.result()
