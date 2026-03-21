"""Tests for large_pr_notifier — posting large-PR limitation notices (NFR3, AC: 3, 4)."""

from unittest.mock import AsyncMock, MagicMock

from d1ff.webhook.large_pr_notifier import LARGE_PR_NOTICE, post_large_pr_notice


async def test_post_large_pr_notice_calls_create_review() -> None:
    """post_large_pr_notice calls async_create_review with event=COMMENT and correct body."""
    github_client = MagicMock()
    mock_gh = AsyncMock()
    github_client.get_installation_client = AsyncMock(return_value=mock_gh)
    mock_gh.rest.pulls.async_create_review = AsyncMock()

    await post_large_pr_notice(
        github_client=github_client,
        installation_id=123,
        owner="owner",
        repo="repo",
        pr_number=42,
        lines_changed=3500,
    )

    mock_gh.rest.pulls.async_create_review.assert_called_once()
    call_kwargs = mock_gh.rest.pulls.async_create_review.call_args.kwargs
    assert call_kwargs["event"] == "COMMENT"
    assert call_kwargs["comments"] == []
    assert "d1ff: Large PR Detected" in call_kwargs["body"]


def test_large_pr_notice_content() -> None:
    """LARGE_PR_NOTICE mentions the 2,000 line limit."""
    assert "2,000" in LARGE_PR_NOTICE
    assert "d1ff: Large PR Detected" in LARGE_PR_NOTICE


async def test_post_large_pr_notice_github_api_failure_swallowed() -> None:
    """post_large_pr_notice swallows exceptions — notice failure must not block the review."""
    github_client = MagicMock()
    mock_gh = AsyncMock()
    github_client.get_installation_client = AsyncMock(return_value=mock_gh)
    mock_gh.rest.pulls.async_create_review = AsyncMock(side_effect=Exception("API error"))

    # Should not raise
    await post_large_pr_notice(
        github_client=github_client,
        installation_id=123,
        owner="owner",
        repo="repo",
        pr_number=42,
        lines_changed=3500,
    )


async def test_post_large_pr_notice_passes_correct_pr_fields() -> None:
    """post_large_pr_notice forwards owner, repo, and pull_number correctly."""
    github_client = MagicMock()
    mock_gh = AsyncMock()
    github_client.get_installation_client = AsyncMock(return_value=mock_gh)
    mock_gh.rest.pulls.async_create_review = AsyncMock()

    await post_large_pr_notice(
        github_client=github_client,
        installation_id=999,
        owner="acme",
        repo="myrepo",
        pr_number=77,
        lines_changed=2500,
    )

    github_client.get_installation_client.assert_called_once_with(999)
    call_kwargs = mock_gh.rest.pulls.async_create_review.call_args.kwargs
    assert call_kwargs["owner"] == "acme"
    assert call_kwargs["repo"] == "myrepo"
    assert call_kwargs["pull_number"] == 77
