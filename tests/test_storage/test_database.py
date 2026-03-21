"""Tests for database initialization."""

from pathlib import Path

import aiosqlite
import pytest

from d1ff.storage.database import init_db


@pytest.fixture
def db_url(tmp_path: Path) -> str:
    return f"sqlite+aiosqlite:///{tmp_path}/test.db"


async def test_init_db_creates_tables(db_url: str, tmp_path: Path) -> None:
    await init_db(db_url)

    db_path = tmp_path / "test.db"
    assert db_path.exists()

    async with aiosqlite.connect(db_path) as conn, conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ) as cursor:
        rows = await cursor.fetchall()
        table_names = [row[0] for row in rows]

    assert "installations" in table_names
    assert "api_keys" in table_names


async def test_init_db_idempotent(db_url: str) -> None:
    # Should not raise when called twice (IF NOT EXISTS semantics)
    await init_db(db_url)
    await init_db(db_url)
