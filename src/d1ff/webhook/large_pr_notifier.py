"""Post a large-PR limitation notice to a GitHub PR (NFR3)."""

import structlog

from d1ff.github import GitHubAppClient

logger = structlog.get_logger(__name__)

LARGE_PR_NOTICE = (
    "## d1ff: Large PR Detected\n\n"
    "This PR has more than 2,000 lines changed. "
    "d1ff has reviewed the first 2,000 lines of the diff. "
    "Consider breaking large PRs into smaller, focused changes for more thorough review coverage."
)


async def post_large_pr_notice(
    github_client: GitHubAppClient,
    installation_id: int,
    owner: str,
    repo: str,
    pr_number: int,
    lines_changed: int,
) -> None:
    """Post a notice comment to the PR about the large-PR limitation."""
    try:
        gh = await github_client.get_installation_client(installation_id)
        await gh.rest.pulls.async_create_review(
            owner=owner,
            repo=repo,
            pull_number=pr_number,
            body=LARGE_PR_NOTICE,
            event="COMMENT",
            comments=[],
        )
        logger.info(
            "large_pr_notice_posted",
            installation_id=installation_id,
            pr_number=pr_number,
            lines_changed=lines_changed,
            stage="large_pr_notify",
        )
    except Exception as exc:
        logger.warning(
            "large_pr_notice_failed",
            installation_id=installation_id,
            pr_number=pr_number,
            stage="large_pr_notify",
            error=str(exc),
        )
        # Swallowing is intentional: notice failure must not block the review
