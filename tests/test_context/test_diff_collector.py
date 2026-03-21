"""Tests for diff_collector — fetch PR diff via GitHub API (AC: 1, 4)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import structlog.testing

from d1ff.context.diff_collector import collect_diff
from d1ff.context.exceptions import ContextCollectionError
from d1ff.github import GitHubAppClient


def _make_github_client(installation_client: MagicMock) -> MagicMock:
    """Build a mock GitHubAppClient that returns the given installation client."""
    client = MagicMock(spec=GitHubAppClient)
    client.get_installation_client = AsyncMock(return_value=installation_client)
    return client


def _make_installation_client(diff_text: str = "diff --git a/foo.py b/foo.py\n") -> MagicMock:
    """Build a mock githubkit installation client that returns a diff response."""
    response = MagicMock()
    response.text = diff_text

    gh = MagicMock()
    gh.rest.pulls.async_get = AsyncMock(return_value=response)
    return gh


async def test_collect_diff_success() -> None:
    """collect_diff returns the diff text from the GitHub API."""
    expected_diff = "diff --git a/src/foo.py b/src/foo.py\n+added line\n"
    gh = _make_installation_client(expected_diff)
    client = _make_github_client(gh)

    result = await collect_diff(
        client, installation_id=123, owner="owner", repo="repo", pr_number=42
    )

    assert result == expected_diff
    gh.rest.pulls.async_get.assert_awaited_once()


async def test_collect_diff_timeout_retries() -> None:
    """collect_diff retries once on TimeoutError and returns diff on second attempt."""
    expected_diff = "diff --git a/bar.py b/bar.py\n"
    response = MagicMock()
    response.text = expected_diff

    # First call raises TimeoutError; second call succeeds
    gh = MagicMock()
    call_count = 0

    async def async_get_side_effect(**kwargs):  # type: ignore[no-untyped-def]
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise TimeoutError()
        return response

    gh.rest.pulls.async_get = AsyncMock(side_effect=async_get_side_effect)
    client = _make_github_client(gh)

    with patch("d1ff.context.diff_collector.asyncio.sleep", new_callable=AsyncMock):
        result = await collect_diff(
            client, installation_id=123, owner="owner", repo="repo", pr_number=42
        )

    assert result == expected_diff
    assert call_count == 2


async def test_collect_diff_fails_after_retry() -> None:
    """collect_diff raises ContextCollectionError when both attempts fail."""
    gh = MagicMock()
    gh.rest.pulls.async_get = AsyncMock(side_effect=TimeoutError())
    client = _make_github_client(gh)

    with (
        patch("d1ff.context.diff_collector.asyncio.sleep", new_callable=AsyncMock),
        pytest.raises(ContextCollectionError) as exc_info,
    ):
        await collect_diff(
            client, installation_id=123, owner="owner", repo="repo", pr_number=42
        )

    assert exc_info.value.stage == "diff_collection"


async def test_collect_diff_logs_duration() -> None:
    """collect_diff emits a log record with stage=diff_collection and duration_ms."""
    expected_diff = "diff --git a/x.py b/x.py\n"
    gh = _make_installation_client(expected_diff)
    client = _make_github_client(gh)

    with structlog.testing.capture_logs() as logs:
        await collect_diff(
            client, installation_id=123, owner="owner", repo="repo", pr_number=1
        )

    complete_logs = [
        entry for entry in logs if entry.get("event") == "diff_collection_complete"
    ]
    assert len(complete_logs) == 1
    assert complete_logs[0]["stage"] == "diff_collection"
    assert "duration_ms" in complete_logs[0]
