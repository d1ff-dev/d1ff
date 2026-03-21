"""Tests for review_poster.py — posting formatted reviews to GitHub (FR29, FR30, AC: 1, 2, 3).

All tests are async (asyncio_mode = "auto" in pyproject.toml — no @pytest.mark.asyncio needed).
GitHub API calls are mocked via unittest.mock.AsyncMock.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from githubkit.exception import RequestFailed

from d1ff.comments.models import FormattedReview, InlineComment, ReviewSummary
from d1ff.comments.review_poster import post_review
from d1ff.context.models import FileContext, PRMetadata, ReviewContext

# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------


def make_review_context() -> ReviewContext:
    return ReviewContext(
        installation_id=123,
        pr_metadata=PRMetadata(
            number=42,
            title="Add feature X",
            author="alice",
            base_branch="main",
            head_branch="feat/x",
            html_url="https://github.com/acme/backend/pull/42",
            draft=False,
        ),
        diff="+ def foo(): pass",
        changed_files=[FileContext(path="main.py", content="def foo(): pass")],
    )


def make_formatted_review(inline_count: int = 1) -> FormattedReview:
    inline = [
        InlineComment(
            file="main.py",
            line=10,
            body="**🔴 Critical [bug]** (confidence: high)\n\nIssue here.",
        )
        for _ in range(inline_count)
    ]
    summary = ReviewSummary(body="## Review Summary\n\n🔴 Critical: 1")
    return FormattedReview(
        inline_comments=inline,
        summary=summary,
        was_degraded=False,
    )


def make_mock_github_client(
    create_review_side_effect: BaseException | None = None,
) -> MagicMock:
    """Create a mock GitHubAppClient whose installation client has mocked pulls API."""
    mock_pulls = AsyncMock()
    if create_review_side_effect is not None:
        mock_pulls.async_create_review.side_effect = create_review_side_effect

    mock_rest = MagicMock()
    mock_rest.pulls = mock_pulls

    mock_gh = MagicMock()
    mock_gh.rest = mock_rest

    mock_client = AsyncMock()
    mock_client.get_installation_client = AsyncMock(return_value=mock_gh)

    return mock_client


def make_request_failed() -> RequestFailed:
    """Create a RequestFailed exception with a mock response for testing."""
    mock_response = MagicMock()
    return RequestFailed(mock_response)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_post_review_calls_github_api_with_comment_event() -> None:
    """GitHub API is called with event='COMMENT' — never 'REQUEST_CHANGES' (FR30)."""
    context = make_review_context()
    formatted = make_formatted_review(inline_count=1)
    mock_client = make_mock_github_client()

    await post_review(formatted, context, mock_client, owner="acme", repo="backend")

    mock_gh = await mock_client.get_installation_client(123)
    mock_gh.rest.pulls.async_create_review.assert_called_once()
    call_kwargs = mock_gh.rest.pulls.async_create_review.call_args.kwargs
    assert call_kwargs["event"] == "COMMENT"
    assert call_kwargs["event"] != "REQUEST_CHANGES"
    assert call_kwargs["event"] != "APPROVE"


async def test_post_review_passes_summary_body() -> None:
    """The review summary body is passed as the top-level review body."""
    context = make_review_context()
    formatted = make_formatted_review()
    mock_client = make_mock_github_client()

    await post_review(formatted, context, mock_client, owner="acme", repo="backend")

    mock_gh = await mock_client.get_installation_client(123)
    call_kwargs = mock_gh.rest.pulls.async_create_review.call_args.kwargs
    assert call_kwargs["body"] == formatted.summary.body


async def test_post_review_passes_inline_comments() -> None:
    """Inline comments have correct path, line, and body from InlineComment."""
    context = make_review_context()
    formatted = make_formatted_review(inline_count=1)
    mock_client = make_mock_github_client()

    await post_review(formatted, context, mock_client, owner="acme", repo="backend")

    mock_gh = await mock_client.get_installation_client(123)
    call_kwargs = mock_gh.rest.pulls.async_create_review.call_args.kwargs
    comments = call_kwargs["comments"]
    assert len(comments) == 1
    assert comments[0]["path"] == "main.py"
    assert comments[0]["line"] == 10
    assert comments[0]["body"] == (
        "**🔴 Critical [bug]** (confidence: high)\n\nIssue here."
    )


async def test_post_review_retries_once_on_api_error() -> None:
    """GitHub API is called twice when the first attempt raises RequestFailed."""
    context = make_review_context()
    formatted = make_formatted_review()

    call_count = 0

    async def side_effect(**kwargs: object) -> None:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise make_request_failed()

    mock_pulls = AsyncMock()
    mock_pulls.async_create_review.side_effect = side_effect
    mock_rest = MagicMock()
    mock_rest.pulls = mock_pulls
    mock_gh = MagicMock()
    mock_gh.rest = mock_rest
    mock_client = AsyncMock()
    mock_client.get_installation_client = AsyncMock(return_value=mock_gh)

    with patch("d1ff.comments.review_poster.asyncio.sleep", new_callable=AsyncMock):
        await post_review(formatted, context, mock_client, owner="acme", repo="backend")

    assert call_count == 2


async def test_post_review_raises_after_two_failures() -> None:
    """RequestFailed propagates when both the first and retry attempts fail."""
    context = make_review_context()
    formatted = make_formatted_review()

    mock_pulls = AsyncMock()
    mock_pulls.async_create_review.side_effect = make_request_failed()
    mock_rest = MagicMock()
    mock_rest.pulls = mock_pulls
    mock_gh = MagicMock()
    mock_gh.rest = mock_rest
    mock_client = AsyncMock()
    mock_client.get_installation_client = AsyncMock(return_value=mock_gh)

    with (
        patch("d1ff.comments.review_poster.asyncio.sleep", new_callable=AsyncMock),
        pytest.raises(RequestFailed),
    ):
        await post_review(formatted, context, mock_client, owner="acme", repo="backend")

    assert mock_pulls.async_create_review.call_count == 2


async def test_post_review_empty_inline_comments() -> None:
    """FormattedReview with no inline comments passes comments=[] to the API."""
    context = make_review_context()
    formatted = make_formatted_review(inline_count=0)
    mock_client = make_mock_github_client()

    await post_review(formatted, context, mock_client, owner="acme", repo="backend")

    mock_gh = await mock_client.get_installation_client(123)
    call_kwargs = mock_gh.rest.pulls.async_create_review.call_args.kwargs
    assert call_kwargs["comments"] == []
