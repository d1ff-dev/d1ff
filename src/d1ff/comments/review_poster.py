"""Post a formatted review to GitHub as a non-blocking COMMENT review (FR29, FR30, AD-9).

This module receives a FormattedReview (produced by severity_formatter.py in Story 3.7)
and posts it to GitHub via the GitHubAppClient wrapper.

Architecture rules enforced here:
- event MUST be "COMMENT" — never "REQUEST_CHANGES" or "APPROVE" (FR30)
- InlineComment.body is posted verbatim — not re-formatted
- One retry with asyncio.sleep(2) backoff on API failure (NFR19)
- Exceptions propagate to caller after two failures — no swallowing (AD-10)
- github_client received as parameter — not created here (DI pattern)
"""

from __future__ import annotations

import asyncio
from typing import Literal

import structlog
from githubkit.exception import RequestFailed
from githubkit.versions.v2026_03_10.types import (
    ReposOwnerRepoPullsPullNumberReviewsPostBodyPropCommentsItemsType,
)

from d1ff.comments.models import CostBadge, FormattedReview
from d1ff.context.models import ReviewContext
from d1ff.github import GitHubAppClient

logger = structlog.get_logger(__name__)


async def post_review(
    formatted: FormattedReview,
    context: ReviewContext,
    github_client: GitHubAppClient,
    owner: str,
    repo: str,
    cost_badge: CostBadge | None = None,
) -> None:
    """Post a formatted review to GitHub as a non-blocking COMMENT review.

    Posts the review summary and all inline comments in a single API call.
    Uses one retry with exponential backoff on GitHub API error (NFR19).

    Args:
        formatted: The fully formatted review (from severity_formatter.py).
        context: Review context containing installation_id and pr_metadata.
        github_client: Authenticated GitHub App client.
        owner: Repository owner (GitHub login or organization name).
        repo: Repository name.
        cost_badge: Optional cost badge to append to the summary comment (FR36).
                    If None, the badge is omitted (graceful degradation).

    Raises:
        RequestFailed: If the GitHub API call fails after one retry attempt.
    """
    pr_number = context.pr_metadata.number
    installation_id = context.installation_id

    comments: list[ReposOwnerRepoPullsPullNumberReviewsPostBodyPropCommentsItemsType] = [
        {
            "path": inline_comment.file,
            "line": inline_comment.line,
            "body": inline_comment.body,
        }
        for inline_comment in formatted.inline_comments
    ]

    event: Literal["COMMENT"] = "COMMENT"

    body = formatted.summary.body
    if cost_badge is not None:
        body = body + "\n\n---\n" + cost_badge.format()

    await _post_review_api(
        github_client=github_client,
        installation_id=installation_id,
        owner=owner,
        repo=repo,
        pr_number=pr_number,
        body=body,
        event=event,
        comments=comments,
    )

    logger.info(
        "review_posted",
        installation_id=installation_id,
        pr_number=pr_number,
        stage="review_posting",
        inline_count=len(formatted.inline_comments),
        event_type="COMMENT",
    )


async def _post_review_api(
    github_client: GitHubAppClient,
    installation_id: int,
    owner: str,
    repo: str,
    pr_number: int,
    body: str,
    event: Literal["COMMENT"],
    comments: list[ReposOwnerRepoPullsPullNumberReviewsPostBodyPropCommentsItemsType],
) -> None:
    """Call the GitHub API to create a pull request review, with one retry on failure.

    Args:
        github_client: Authenticated GitHub App client.
        installation_id: GitHub App installation ID.
        owner: Repository owner.
        repo: Repository name.
        pr_number: Pull request number.
        body: The review summary body (markdown).
        event: The review event type — always "COMMENT" (FR30).
        comments: List of inline comments.

    Raises:
        RequestFailed: If the API call fails on both the first attempt and the retry.
    """
    gh = await github_client.get_installation_client(installation_id)
    try:
        await gh.rest.pulls.async_create_review(
            owner=owner,
            repo=repo,
            pull_number=pr_number,
            body=body,
            event=event,
            comments=comments,
        )
    except RequestFailed:
        logger.warning(
            "review_post_retry",
            installation_id=installation_id,
            pr_number=pr_number,
            stage="review_posting",
        )
        await asyncio.sleep(2)
        await gh.rest.pulls.async_create_review(
            owner=owner,
            repo=repo,
            pull_number=pr_number,
            body=body,
            event=event,
            comments=comments,
        )
        # Second failure propagates up — no further retry (NFR19)
