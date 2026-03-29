"""Tests for PostgreSQL database initialization and connection management."""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from d1ff.storage.database import (
    dispose_engine,
    get_connection,
    get_db_connection,
    get_engine,
    init_engine,
)


@pytest.fixture
async def engine(postgres_url: str):
    """Create engine for tests, dispose after."""
    eng = init_engine(postgres_url)
    yield eng
    await dispose_engine()


async def test_init_engine_returns_engine(engine: AsyncEngine) -> None:
    assert isinstance(engine, AsyncEngine)


async def test_get_engine_after_init(engine: AsyncEngine) -> None:
    assert get_engine() is engine


async def test_get_engine_before_init_raises() -> None:
    with pytest.raises(AssertionError, match="Engine not initialized"):
        get_engine()


async def test_get_connection_yields_async_connection(engine: AsyncEngine) -> None:
    async with get_connection() as conn:
        assert isinstance(conn, AsyncConnection)
        result = await conn.execute(text("SELECT 1"))
        assert result.scalar() == 1


async def test_get_db_connection_yields_connection(engine: AsyncEngine) -> None:
    gen = get_db_connection()
    conn = await gen.__anext__()
    assert isinstance(conn, AsyncConnection)
    result = await conn.execute(text("SELECT 1"))
    assert result.scalar() == 1
    with pytest.raises(StopAsyncIteration):
        await gen.__anext__()
