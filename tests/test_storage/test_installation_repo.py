"""Tests for installation repository CRUD operations."""

import datetime
from pathlib import Path

import aiosqlite
import pytest

from d1ff.storage.database import init_db
from d1ff.storage.installation_repo import (
    InstallationRepository,
    delete_installation,
    get_installation,
    upsert_installation,
)
from d1ff.storage.models import Installation
from d1ff.webhook.models import (
    RepositoryInfo,
)

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def make_installation(installation_id: int = 1) -> Installation:
    now = datetime.datetime.now(datetime.UTC)
    return Installation(
        installation_id=installation_id,
        account_login="testuser",
        account_type="User",
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def db_url(tmp_path: Path) -> str:
    return f"sqlite+aiosqlite:///{tmp_path}/test.db"


# ---------------------------------------------------------------------------
# Module-level function tests (backward-compat with Story 1.x)
# ---------------------------------------------------------------------------


async def test_upsert_and_get_installation(db_url: str) -> None:
    await init_db(db_url)
    inst = make_installation()

    await upsert_installation(db_url, inst)
    result = await get_installation(db_url, inst.installation_id)

    assert result is not None
    assert result.installation_id == inst.installation_id
    assert result.account_login == inst.account_login
    assert result.account_type == inst.account_type


async def test_get_nonexistent_returns_none(db_url: str) -> None:
    await init_db(db_url)
    result = await get_installation(db_url, 99999)
    assert result is None


async def test_delete_installation(db_url: str) -> None:
    await init_db(db_url)
    inst = make_installation()

    await upsert_installation(db_url, inst)
    await delete_installation(db_url, inst.installation_id)

    result = await get_installation(db_url, inst.installation_id)
    assert result is None


# ---------------------------------------------------------------------------
# InstallationRepository class tests (Story 2.1)
# ---------------------------------------------------------------------------


@pytest.fixture
async def repo_and_conn(tmp_path: Path):  # type: ignore[no-untyped-def]
    """Yield (InstallationRepository, aiosqlite.Connection) backed by in-memory DB."""
    db_url = f"sqlite+aiosqlite:///{tmp_path}/repo_test.db"
    await init_db(db_url)
    async with aiosqlite.connect(f"{tmp_path}/repo_test.db") as conn:
        await conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = aiosqlite.Row
        yield InstallationRepository(conn), conn


async def test_upsert_installation_creates_record(repo_and_conn) -> None:  # type: ignore[no-untyped-def]
    repo, conn = repo_and_conn
    await repo.upsert_installation(1001, "myorg", "Organization")
    result = await repo.get_installation(1001)
    assert result is not None
    assert result.installation_id == 1001
    assert result.account_login == "myorg"
    assert result.account_type == "Organization"
    assert result.suspended is False


async def test_upsert_installation_updates_existing(repo_and_conn) -> None:  # type: ignore[no-untyped-def]
    repo, conn = repo_and_conn
    await repo.upsert_installation(1002, "original-login", "User")
    await repo.upsert_installation(1002, "updated-login", "Organization")
    result = await repo.get_installation(1002)
    assert result is not None
    assert result.account_login == "updated-login"
    assert result.account_type == "Organization"


async def test_upsert_repositories_stores_repo_list(repo_and_conn) -> None:  # type: ignore[no-untyped-def]
    repo, conn = repo_and_conn
    await repo.upsert_installation(1003, "repoorg", "Organization")
    repos = [
        RepositoryInfo(id=201, name="repo-a", full_name="repoorg/repo-a", private=False),
        RepositoryInfo(id=202, name="repo-b", full_name="repoorg/repo-b", private=True),
    ]
    await repo.upsert_repositories(1003, repos)

    async with conn.execute(
        "SELECT id, repo_name, full_name, private FROM repositories "
        "WHERE installation_id = ? ORDER BY id",
        (1003,),
    ) as cursor:
        rows = await cursor.fetchall()

    assert len(rows) == 2
    assert int(rows[0]["id"]) == 201
    assert str(rows[0]["repo_name"]) == "repo-a"
    assert bool(rows[1]["private"]) is True


async def test_delete_installation_cascades_repositories(repo_and_conn) -> None:  # type: ignore[no-untyped-def]
    repo, conn = repo_and_conn
    await repo.upsert_installation(1004, "cascadeorg", "Organization")
    repos = [
        RepositoryInfo(
            id=301, name="cascade-repo", full_name="cascadeorg/cascade-repo", private=False
        )
    ]
    await repo.upsert_repositories(1004, repos)

    await repo.delete_installation(1004)

    result = await repo.get_installation(1004)
    assert result is None

    async with conn.execute(
        "SELECT id FROM repositories WHERE installation_id = ?", (1004,)
    ) as cursor:
        row = await cursor.fetchone()
    assert row is None


async def test_update_installation_status_suspended(repo_and_conn) -> None:  # type: ignore[no-untyped-def]
    repo, conn = repo_and_conn
    await repo.upsert_installation(1005, "suspendme", "User")
    await repo.update_installation_status(1005, suspended=True)
    result = await repo.get_installation(1005)
    assert result is not None
    assert result.suspended is True

    await repo.update_installation_status(1005, suspended=False)
    result2 = await repo.get_installation(1005)
    assert result2 is not None
    assert result2.suspended is False


async def test_get_installation_returns_none_for_unknown(repo_and_conn) -> None:  # type: ignore[no-untyped-def]
    repo, conn = repo_and_conn
    result = await repo.get_installation(99999)
    assert result is None
