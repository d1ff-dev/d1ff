"""Tests for PR pause/resume state repository (Story 4.2, AC: 1, 2)."""

from pathlib import Path

import pytest

from d1ff.storage.database import init_db
from d1ff.storage.pr_state_repo import get_pr_state, set_pr_state


@pytest.fixture
async def db_url(tmp_path: Path) -> str:  # type: ignore[misc]
    """Provide a fresh test database URL and initialize schema."""
    url = f"sqlite+aiosqlite:///{tmp_path}/test_pr_states.db"
    await init_db(url)
    return url


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_get_pr_state_default_active(db_url: str) -> None:
    """No row in DB → returns 'active' as default."""
    result = await get_pr_state(1, "owner/repo", 1, database_url=db_url)
    assert result == "active"


async def test_set_pr_state_paused(db_url: str) -> None:
    """set_pr_state(..., 'paused') → get_pr_state returns 'paused'."""
    await set_pr_state(1, "owner/repo", 42, "paused", database_url=db_url)
    result = await get_pr_state(1, "owner/repo", 42, database_url=db_url)
    assert result == "paused"


async def test_set_pr_state_upsert(db_url: str) -> None:
    """Call set_pr_state('paused') then set_pr_state('active') → returns 'active'."""
    await set_pr_state(1, "owner/repo", 42, "paused", database_url=db_url)
    await set_pr_state(1, "owner/repo", 42, "active", database_url=db_url)
    result = await get_pr_state(1, "owner/repo", 42, database_url=db_url)
    assert result == "active"


async def test_pr_states_are_scoped_per_installation(db_url: str) -> None:
    """Two different installation IDs, same repo and PR → independent states."""
    await set_pr_state(100, "owner/repo", 42, "paused", database_url=db_url)
    await set_pr_state(200, "owner/repo", 42, "active", database_url=db_url)

    result_100 = await get_pr_state(100, "owner/repo", 42, database_url=db_url)
    result_200 = await get_pr_state(200, "owner/repo", 42, database_url=db_url)

    assert result_100 == "paused"
    assert result_200 == "active"


async def test_pr_states_are_scoped_per_repo(db_url: str) -> None:
    """Same installation, same PR number, different repos → independent states."""
    await set_pr_state(1, "org/repo-a", 10, "paused", database_url=db_url)
    await set_pr_state(1, "org/repo-b", 10, "active", database_url=db_url)

    result_a = await get_pr_state(1, "org/repo-a", 10, database_url=db_url)
    result_b = await get_pr_state(1, "org/repo-b", 10, database_url=db_url)

    assert result_a == "paused"
    assert result_b == "active"
