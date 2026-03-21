"""Pipeline error → PR comment handler (FR41, AD-10)."""

import asyncio

import litellm.exceptions
import structlog

from d1ff.github import GitHubAppClient

logger = structlog.get_logger(__name__)


def _classify_error(stage: str, error: Exception) -> str:
    """Map a pipeline exception to a user-friendly message (FR41)."""
    err_str = str(error).lower()

    # Authentication / invalid API key
    if isinstance(error, litellm.exceptions.AuthenticationError) or any(
        k in err_str for k in ("authentication", "invalid api key", "unauthorized", "auth")
    ):
        return (
            "Review failed: Invalid API key. "
            "Please update your API key in d1ff settings."
        )

    # Rate limiting
    if isinstance(error, litellm.exceptions.RateLimitError) or any(
        k in err_str for k in ("rate limit", "rate_limit", "429", "too many requests")
    ):
        return (
            "Review failed: LLM provider rate limit exceeded. "
            "The review will retry on the next push."
        )

    # Timeout
    if isinstance(error, (asyncio.TimeoutError, litellm.exceptions.Timeout)) or any(
        k in err_str for k in ("timeout", "timed out", "time out")
    ):
        return (
            f"Review failed: Request timed out during {stage}. "
            "If this persists, check your LLM provider status or try a smaller PR."
        )

    # Generic fallback
    return (
        f"Review failed: An unexpected error occurred during {stage}. "
        "Please try again or contact support if the issue persists."
    )


async def post_error_comment(
    github_client: GitHubAppClient,
    installation_id: int,
    owner: str,
    repo: str,
    pr_number: int,
    stage: str,
    error: Exception,
) -> None:
    """Post a user-friendly error comment to a PR when a review pipeline fails (FR41)."""
    user_message = _classify_error(stage, error)
    body = "## d1ff: Review Failed\n\n" + user_message

    try:
        gh = await github_client.get_installation_client(installation_id)
        await gh.rest.pulls.async_create_review(
            owner=owner,
            repo=repo,
            pull_number=pr_number,
            body=body,
            event="COMMENT",
            comments=[],
        )
        logger.info(
            "review_error_comment_posted",
            installation_id=installation_id,
            pr_number=pr_number,
            stage=stage,
            error_type=type(error).__name__,
        )
    except Exception as post_exc:
        logger.warning(
            "review_error_comment_failed",
            installation_id=installation_id,
            pr_number=pr_number,
            stage=stage,
            error=str(post_exc),
        )
        # Intentional swallowing: error comment failure must not raise
