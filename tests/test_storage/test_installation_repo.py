"""Tests for installation repository CRUD operations (PostgreSQL)."""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from d1ff.storage.database import dispose_engine, init_engine, run_alembic_upgrade
from d1ff.storage.installation_repo import InstallationRepository
from d1ff.webhook.models import RepositoryInfo


@pytest.fixture
async def conn(postgres_url: str):
    """Yield an AsyncConnection with migrations applied."""
    run_alembic_upgrade(postgres_url)
    engine = init_engine(postgres_url)
    async with engine.connect() as connection:
        trans = await connection.begin()
        yield connection
        await trans.rollback()
    await dispose_engine()


@pytest.fixture
def repo(conn: AsyncConnection) -> InstallationRepository:
    return InstallationRepository(conn)


async def test_upsert_creates_installation(repo: InstallationRepository) -> None:
    await repo.upsert_installation(1001, "myorg", "Organization")
    result = await repo.get_installation(1001)
    assert result is not None
    assert result.installation_id == 1001
    assert result.account_login == "myorg"
    assert result.account_type == "Organization"
    assert result.suspended is False


async def test_upsert_updates_existing(repo: InstallationRepository) -> None:
    await repo.upsert_installation(1002, "original", "User")
    await repo.upsert_installation(1002, "updated", "Organization")
    result = await repo.get_installation(1002)
    assert result is not None
    assert result.account_login == "updated"
    assert result.account_type == "Organization"


async def test_get_nonexistent_returns_none(repo: InstallationRepository) -> None:
    result = await repo.get_installation(99999)
    assert result is None


async def test_delete_installation(repo: InstallationRepository) -> None:
    await repo.upsert_installation(1003, "deleteme", "User")
    await repo.delete_installation(1003)
    result = await repo.get_installation(1003)
    assert result is None


async def test_update_installation_status(repo: InstallationRepository) -> None:
    await repo.upsert_installation(1004, "suspendme", "User")
    await repo.update_installation_status(1004, suspended=True)
    result = await repo.get_installation(1004)
    assert result is not None
    assert result.suspended is True

    await repo.update_installation_status(1004, suspended=False)
    result2 = await repo.get_installation(1004)
    assert result2 is not None
    assert result2.suspended is False


async def test_list_installations(repo: InstallationRepository) -> None:
    await repo.upsert_installation(1, "a", "User")
    await repo.upsert_installation(2, "b", "Organization")
    results = await repo.list_installations()
    assert len(results) >= 2
    ids = [r.installation_id for r in results]
    assert 1 in ids
    assert 2 in ids


async def test_upsert_repositories(repo: InstallationRepository, conn: AsyncConnection) -> None:
    await repo.upsert_installation(1005, "repoorg", "Organization")
    repos = [
        RepositoryInfo(id=201, name="repo-a", full_name="repoorg/repo-a", private=False),
        RepositoryInfo(id=202, name="repo-b", full_name="repoorg/repo-b", private=True),
    ]
    await repo.upsert_repositories(1005, repos)

    result = await conn.execute(
        text(
            "SELECT id, repo_name, full_name, private"
            " FROM repositories WHERE installation_id = 1005 ORDER BY id"
        )
    )
    rows = result.fetchall()
    assert len(rows) == 2
    assert rows[0][1] == "repo-a"
    assert rows[1][3] is True


async def test_delete_installation_cascades_repositories(
    repo: InstallationRepository, conn: AsyncConnection
) -> None:
    await repo.upsert_installation(1006, "cascadeorg", "Organization")
    repos = [
        RepositoryInfo(
            id=301, name="cascade-repo", full_name="cascadeorg/cascade-repo", private=False
        )
    ]
    await repo.upsert_repositories(1006, repos)
    await repo.delete_installation(1006)

    result = await conn.execute(text("SELECT id FROM repositories WHERE installation_id = 1006"))
    assert result.fetchone() is None


async def test_upsert_user_and_get_by_github_id(repo: InstallationRepository) -> None:
    user_id = await repo.upsert_user(
        github_id=42,
        login="testuser",
        email="test@example.com",
        avatar_url="https://avatar.url",
        encrypted_token="enc-token",
    )
    assert user_id > 0

    user = await repo.get_user_by_github_id(42)
    assert user is not None
    assert user.login == "testuser"
    assert user.github_id == 42


async def test_sync_user_installations(repo: InstallationRepository) -> None:
    await repo.upsert_installation(100, "org1", "Organization")
    await repo.upsert_installation(200, "org2", "Organization")
    user_id = await repo.upsert_user(
        github_id=50,
        login="syncuser",
        email=None,
        avatar_url=None,
        encrypted_token="enc-token",
    )
    await repo.sync_user_installations(user_id, [100, 200])
    installs = await repo.list_installations_for_user(user_id)
    assert len(installs) == 2

    await repo.sync_user_installations(user_id, [100])
    installs = await repo.list_installations_for_user(user_id)
    assert len(installs) == 1
    assert installs[0].installation_id == 100


async def test_delete_repository(repo: InstallationRepository, conn: AsyncConnection) -> None:
    await repo.upsert_installation(1007, "delrepo", "Organization")
    repos = [RepositoryInfo(id=401, name="repo-x", full_name="delrepo/repo-x", private=False)]
    await repo.upsert_repositories(1007, repos)
    await repo.delete_repository(1007, 401)

    result = await conn.execute(text("SELECT id FROM repositories WHERE id = 401"))
    assert result.fetchone() is None
