"""Fetch PR diff from GitHub API via githubkit (FR9, NFR5)."""

import asyncio
import time
from typing import Any

import structlog

from d1ff.context.exceptions import ContextCollectionError
from d1ff.github import GitHubAppClient

logger = structlog.get_logger()


async def _with_retry(coro_fn: Any, stage: str, installation_id: int) -> Any:
    """Execute coroutine with one retry on failure. 15s timeout per attempt."""
    for attempt in range(2):
        try:
            return await asyncio.wait_for(coro_fn(), timeout=15.0)
        except (TimeoutError, Exception) as exc:
            if attempt == 0:
                logger.warning(
                    "github_api_retry",
                    stage=stage,
                    installation_id=installation_id,
                    attempt=attempt,
                    error=str(exc),
                )
                await asyncio.sleep(1.0 * (2**attempt))  # 1s then 2s
                continue
            raise ContextCollectionError(stage=stage, message=str(exc)) from exc


async def collect_diff(
    github_client: GitHubAppClient,
    installation_id: int,
    owner: str,
    repo: str,
    pr_number: int,
) -> str:
    """Fetch the full unified diff for a pull request.

    Uses GitHub API with Accept: application/vnd.github.v3.diff header.
    Applies a 15-second timeout per attempt and retries once on failure.

    Args:
        github_client: Authenticated GitHub App client.
        installation_id: GitHub App installation ID (used for logging and auth).
        owner: Repository owner (user or org login).
        repo: Repository name.
        pr_number: Pull request number.

    Returns:
        The raw unified diff as a string.

    Raises:
        ContextCollectionError: If both attempts fail.
    """
    start_time = time.monotonic()

    logger.info(
        "diff_collection_started",
        installation_id=installation_id,
        pr_number=pr_number,
        stage="diff_collection",
    )

    gh = await github_client.get_installation_client(installation_id)

    async def _fetch() -> str:
        response = await gh.rest.pulls.async_get(
            owner=owner,
            repo=repo,
            pull_number=pr_number,
            headers={"Accept": "application/vnd.github.v3.diff"},
        )
        return response.text

    result: str = await _with_retry(
        _fetch, stage="diff_collection", installation_id=installation_id
    )

    duration_ms = int((time.monotonic() - start_time) * 1000)
    logger.info(
        "diff_collection_complete",
        installation_id=installation_id,
        pr_number=pr_number,
        stage="diff_collection",
        duration_ms=duration_ms,
    )

    return result
