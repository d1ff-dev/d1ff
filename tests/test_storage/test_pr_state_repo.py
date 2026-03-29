"""Tests for PR pause/resume state repository (PostgreSQL)."""

import pytest
from sqlalchemy import text

from d1ff.storage.database import dispose_engine, init_engine, run_alembic_upgrade
from d1ff.storage.pr_state_repo import get_pr_state, set_pr_state


@pytest.fixture
async def setup_db(postgres_url: str):
    run_alembic_upgrade(postgres_url)
    engine = init_engine(postgres_url)
    yield
    async with engine.connect() as conn:
        await conn.execute(text("DELETE FROM pr_states"))
        await conn.commit()
    await dispose_engine()


async def test_default_active(setup_db) -> None:
    result = await get_pr_state(1, "owner/repo", 1)
    assert result == "active"


async def test_set_paused(setup_db) -> None:
    await set_pr_state(1, "owner/repo", 42, "paused")
    result = await get_pr_state(1, "owner/repo", 42)
    assert result == "paused"


async def test_upsert_state(setup_db) -> None:
    await set_pr_state(1, "owner/repo", 42, "paused")
    await set_pr_state(1, "owner/repo", 42, "active")
    result = await get_pr_state(1, "owner/repo", 42)
    assert result == "active"


async def test_scoped_per_installation(setup_db) -> None:
    await set_pr_state(100, "owner/repo", 42, "paused")
    await set_pr_state(200, "owner/repo", 42, "active")
    assert await get_pr_state(100, "owner/repo", 42) == "paused"
    assert await get_pr_state(200, "owner/repo", 42) == "active"


async def test_scoped_per_repo(setup_db) -> None:
    await set_pr_state(1, "org/repo-a", 10, "paused")
    await set_pr_state(1, "org/repo-b", 10, "active")
    assert await get_pr_state(1, "org/repo-a", 10) == "paused"
    assert await get_pr_state(1, "org/repo-b", 10) == "active"
