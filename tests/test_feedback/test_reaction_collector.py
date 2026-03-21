"""Tests for reaction_collector — feedback_reactions table CRUD (AC: 1, 2)."""

from pathlib import Path

import pytest

from d1ff.feedback.models import FeedbackReaction
from d1ff.feedback.reaction_collector import get_reaction_summary, record_reaction
from d1ff.storage.database import init_db

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def db_url(tmp_path: Path) -> str:  # type: ignore[misc]
    """Provide a fresh test database URL and initialize schema."""
    url = f"sqlite+aiosqlite:///{tmp_path}/test_feedback.db"
    await init_db(url)
    return url


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_reaction(
    comment_id: int = 1001,
    reaction_type: str = "+1",
    installation_id: int = 42,
    pr_number: int = 7,
    repo_full_name: str = "owner/repo",
    created_at: str = "2026-03-21T00:00:00+00:00",
) -> FeedbackReaction:
    return FeedbackReaction(
        comment_id=comment_id,
        reaction_type=reaction_type,
        installation_id=installation_id,
        pr_number=pr_number,
        repo_full_name=repo_full_name,
        created_at=created_at,
    )


# ---------------------------------------------------------------------------
# Tests: record_reaction
# ---------------------------------------------------------------------------


async def test_record_reaction_stores_thumbs_up(db_url: str) -> None:
    """record_reaction with '+1' stores a row with correct fields."""
    reaction = make_reaction(reaction_type="+1")
    await record_reaction(reaction, database_url=db_url)

    summary = await get_reaction_summary(42, "owner/repo", database_url=db_url)
    assert len(summary) == 1
    assert summary[0]["comment_id"] == 1001
    assert summary[0]["thumbs_up"] == 1
    assert summary[0]["thumbs_down"] == 0


async def test_record_reaction_stores_thumbs_down(db_url: str) -> None:
    """record_reaction with '-1' stores a row with correct fields."""
    reaction = make_reaction(reaction_type="-1")
    await record_reaction(reaction, database_url=db_url)

    summary = await get_reaction_summary(42, "owner/repo", database_url=db_url)
    assert len(summary) == 1
    assert summary[0]["comment_id"] == 1001
    assert summary[0]["thumbs_up"] == 0
    assert summary[0]["thumbs_down"] == 1


async def test_record_reaction_multiple(db_url: str) -> None:
    """Same comment can receive multiple reactions (append-only log) — two calls yield two rows."""
    reaction1 = make_reaction(reaction_type="+1")
    reaction2 = make_reaction(reaction_type="-1")
    await record_reaction(reaction1, database_url=db_url)
    await record_reaction(reaction2, database_url=db_url)

    summary = await get_reaction_summary(42, "owner/repo", database_url=db_url)
    assert len(summary) == 1
    assert summary[0]["thumbs_up"] == 1
    assert summary[0]["thumbs_down"] == 1


# ---------------------------------------------------------------------------
# Tests: get_reaction_summary
# ---------------------------------------------------------------------------


async def test_get_reaction_summary_empty(db_url: str) -> None:
    """No reactions in DB → returns empty list."""
    result = await get_reaction_summary(42, "owner/repo", database_url=db_url)
    assert result == []


async def test_get_reaction_summary_counts(db_url: str) -> None:
    """3 thumbs-up and 1 thumbs-down → correct aggregate counts."""
    for _ in range(3):
        await record_reaction(make_reaction(reaction_type="+1"), database_url=db_url)
    await record_reaction(make_reaction(reaction_type="-1"), database_url=db_url)

    summary = await get_reaction_summary(42, "owner/repo", database_url=db_url)
    assert len(summary) == 1
    entry = summary[0]
    assert entry["comment_id"] == 1001
    assert entry["thumbs_up"] == 3
    assert entry["thumbs_down"] == 1


async def test_get_reaction_summary_scoped_by_installation(db_url: str) -> None:
    """Reactions from two different installation_ids are not mixed in get_reaction_summary."""
    await record_reaction(
        make_reaction(installation_id=100, reaction_type="+1"), database_url=db_url
    )
    await record_reaction(
        make_reaction(installation_id=200, reaction_type="-1"), database_url=db_url
    )

    summary_100 = await get_reaction_summary(100, "owner/repo", database_url=db_url)
    summary_200 = await get_reaction_summary(200, "owner/repo", database_url=db_url)

    assert len(summary_100) == 1
    assert summary_100[0]["thumbs_up"] == 1
    assert summary_100[0]["thumbs_down"] == 0

    assert len(summary_200) == 1
    assert summary_200[0]["thumbs_up"] == 0
    assert summary_200[0]["thumbs_down"] == 1


async def test_get_reaction_summary_scoped_by_repo(db_url: str) -> None:
    """Same installation, different repo_full_name → separate aggregate results."""
    await record_reaction(
        make_reaction(repo_full_name="org/repo-a", reaction_type="+1"), database_url=db_url
    )
    await record_reaction(
        make_reaction(repo_full_name="org/repo-b", reaction_type="-1"), database_url=db_url
    )

    summary_a = await get_reaction_summary(42, "org/repo-a", database_url=db_url)
    summary_b = await get_reaction_summary(42, "org/repo-b", database_url=db_url)

    assert len(summary_a) == 1
    assert summary_a[0]["thumbs_up"] == 1
    assert summary_a[0]["thumbs_down"] == 0

    assert len(summary_b) == 1
    assert summary_b[0]["thumbs_up"] == 0
    assert summary_b[0]["thumbs_down"] == 1


async def test_reaction_summary_multiple_comments(db_url: str) -> None:
    """Two different comment_ids → two separate entries in summary."""
    await record_reaction(
        make_reaction(comment_id=111, reaction_type="+1"), database_url=db_url
    )
    await record_reaction(
        make_reaction(comment_id=222, reaction_type="-1"), database_url=db_url
    )

    summary = await get_reaction_summary(42, "owner/repo", database_url=db_url)
    assert len(summary) == 2

    by_comment = {entry["comment_id"]: entry for entry in summary}
    assert by_comment[111]["thumbs_up"] == 1
    assert by_comment[111]["thumbs_down"] == 0
    assert by_comment[222]["thumbs_up"] == 0
    assert by_comment[222]["thumbs_down"] == 1
