"""Tests for d1ff.observability.error_reporter."""

from unittest.mock import AsyncMock, MagicMock

import litellm.exceptions

from d1ff.observability.error_reporter import _classify_error, post_error_comment


def _make_github_client(raises: Exception | None = None) -> MagicMock:
    """Create a mock GitHubAppClient with mocked installation client."""
    mock_review = AsyncMock()
    if raises is not None:
        mock_review.side_effect = raises

    mock_gh = MagicMock()
    mock_gh.rest.pulls.async_create_review = mock_review

    mock_client = MagicMock()
    mock_client.get_installation_client = AsyncMock(return_value=mock_gh)

    return mock_client, mock_gh, mock_review


async def test_post_error_comment_authentication_error() -> None:
    """AuthenticationError → comment body contains 'Invalid API key' and 'd1ff settings'."""
    mock_client, mock_gh, mock_review = _make_github_client()
    error = litellm.exceptions.AuthenticationError(
        message="Invalid API key", llm_provider="openai", model="gpt-4"
    )

    await post_error_comment(
        github_client=mock_client,
        installation_id=123,
        owner="owner",
        repo="repo",
        pr_number=42,
        stage="pipeline",
        error=error,
    )

    mock_review.assert_awaited_once()
    call_kwargs = mock_review.call_args.kwargs
    assert "Invalid API key" in call_kwargs["body"]
    assert "d1ff settings" in call_kwargs["body"]


async def test_post_error_comment_rate_limit_error() -> None:
    """RateLimitError → comment body contains 'rate limit exceeded' and 'retry on the next push'."""
    mock_client, mock_gh, mock_review = _make_github_client()
    error = litellm.exceptions.RateLimitError(
        message="Rate limit exceeded", llm_provider="openai", model="gpt-4"
    )

    await post_error_comment(
        github_client=mock_client,
        installation_id=123,
        owner="owner",
        repo="repo",
        pr_number=42,
        stage="pipeline",
        error=error,
    )

    mock_review.assert_awaited_once()
    call_kwargs = mock_review.call_args.kwargs
    assert "rate limit exceeded" in call_kwargs["body"].lower()
    assert "retry on the next push" in call_kwargs["body"]


async def test_post_error_comment_timeout_error() -> None:
    """asyncio.TimeoutError produces comment body containing 'timed out' and stage name."""
    mock_client, mock_gh, mock_review = _make_github_client()
    error = TimeoutError()

    await post_error_comment(
        github_client=mock_client,
        installation_id=123,
        owner="owner",
        repo="repo",
        pr_number=42,
        stage="pipeline",
        error=error,
    )

    mock_review.assert_awaited_once()
    call_kwargs = mock_review.call_args.kwargs
    assert "timed out" in call_kwargs["body"].lower()
    assert "pipeline" in call_kwargs["body"]


async def test_post_error_comment_generic_error() -> None:
    """Generic Exception produces comment body containing 'unexpected error' and stage name."""
    mock_client, mock_gh, mock_review = _make_github_client()
    error = Exception("something unexpected")

    await post_error_comment(
        github_client=mock_client,
        installation_id=123,
        owner="owner",
        repo="repo",
        pr_number=42,
        stage="pipeline",
        error=error,
    )

    mock_review.assert_awaited_once()
    call_kwargs = mock_review.call_args.kwargs
    assert "unexpected error" in call_kwargs["body"].lower()
    assert "pipeline" in call_kwargs["body"]


async def test_post_error_comment_posts_as_review_comment() -> None:
    """async_create_review called with event='COMMENT', comments=[], correct params."""
    mock_client, mock_gh, mock_review = _make_github_client()
    error = Exception("oops")

    await post_error_comment(
        github_client=mock_client,
        installation_id=999,
        owner="myorg",
        repo="myrepo",
        pr_number=7,
        stage="pipeline",
        error=error,
    )

    mock_review.assert_awaited_once()
    call_kwargs = mock_review.call_args.kwargs
    assert call_kwargs["event"] == "COMMENT"
    assert call_kwargs["comments"] == []
    assert call_kwargs["owner"] == "myorg"
    assert call_kwargs["repo"] == "myrepo"
    assert call_kwargs["pull_number"] == 7


async def test_post_error_comment_github_api_failure_swallowed() -> None:
    """If async_create_review raises, post_error_comment returns without raising."""
    mock_client, mock_gh, mock_review = _make_github_client(raises=Exception("GitHub API down"))
    error = Exception("pipeline error")

    # Should not raise
    await post_error_comment(
        github_client=mock_client,
        installation_id=123,
        owner="owner",
        repo="repo",
        pr_number=42,
        stage="pipeline",
        error=error,
    )

    # Verify the review was attempted
    mock_review.assert_awaited_once()


async def test_post_error_comment_body_has_header() -> None:
    """Comment body starts with '## d1ff: Review Failed'."""
    mock_client, mock_gh, mock_review = _make_github_client()
    error = Exception("some error")

    await post_error_comment(
        github_client=mock_client,
        installation_id=123,
        owner="owner",
        repo="repo",
        pr_number=42,
        stage="pipeline",
        error=error,
    )

    mock_review.assert_awaited_once()
    call_kwargs = mock_review.call_args.kwargs
    assert call_kwargs["body"].startswith("## d1ff: Review Failed")


def test_classify_error_by_message_content() -> None:
    """String-based classification works even when exception type is a base class."""
    # Authentication via message content (not typed exception)
    auth_err = Exception("invalid api key provided")
    result = _classify_error("pipeline", auth_err)
    assert "Invalid API key" in result
    assert "d1ff settings" in result

    # Rate limit via message content
    rate_err = Exception("rate limit exceeded for this model")
    result = _classify_error("pipeline", rate_err)
    assert "rate limit exceeded" in result.lower()
    assert "retry on the next push" in result

    # Timeout via message content
    timeout_err = Exception("request timed out after 30 seconds")
    result = _classify_error("pipeline", timeout_err)
    assert "timed out" in result.lower()

    # Generic fallback
    generic_err = Exception("some other error")
    result = _classify_error("pipeline", generic_err)
    assert "unexpected error" in result.lower()
