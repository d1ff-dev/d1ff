"""Orchestrate PR diff and file collection into a ReviewContext (AD-9, FR9, FR11, NFR5)."""

import time

import structlog

from d1ff.context.diff_collector import collect_diff
from d1ff.context.exceptions import ContextCollectionError
from d1ff.context.file_collector import FileCache, collect_changed_files
from d1ff.context.import_resolver import resolve_related_files
from d1ff.context.models import PRMetadata, ReviewContext
from d1ff.github import GitHubAppClient
from d1ff.webhook.models import PullRequestPayload

logger = structlog.get_logger()

# NFR5: GitHub API calls must complete within 15 seconds total
_TOTAL_BUDGET_SECONDS = 15.0


def _count_lines_changed(diff: str) -> int:
    """Count added + deleted lines in a unified diff (excludes +++ / --- headers)."""
    count = 0
    for line in diff.splitlines():
        if line.startswith(("+", "-")) and not line.startswith(("+++", "---")):
            count += 1
    return count


async def build_review_context(
    github_client: GitHubAppClient,
    pr_payload: PullRequestPayload,
) -> ReviewContext:
    """Build a ReviewContext from a pull request webhook payload.

    Fetches the PR diff and full contents of all changed files. Applies a
    15-second budget across all API calls; if the budget is exceeded, logs a
    warning and returns partial context rather than raising.

    Args:
        github_client: Authenticated GitHub App client.
        pr_payload: Validated PullRequestPayload from the webhook.

    Returns:
        ReviewContext populated with diff, changed_files, and pr_metadata.
        related_files defaults to [] (populated by Story 3.3).
    """
    parts = pr_payload.repository.full_name.split("/", 1)
    owner = parts[0]
    repo = parts[1]
    pr_number = pr_payload.pull_request.number
    head_sha: str = pr_payload.pull_request.head["sha"]
    installation_id = pr_payload.installation.id

    pr_metadata = PRMetadata(
        number=pr_number,
        title=pr_payload.pull_request.title,
        author=pr_payload.pull_request.user["login"],
        base_branch=pr_payload.pull_request.base["ref"],
        head_branch=pr_payload.pull_request.head["ref"],
        html_url=pr_payload.pull_request.html_url,
        draft=pr_payload.pull_request.draft,
    )

    logger.info(
        "context_collection_started",
        installation_id=installation_id,
        pr_number=pr_number,
        stage="context_build",
    )

    start_time = time.monotonic()
    cache = FileCache()  # Per-review — NFR10

    # --- Collect diff ---
    diff = ""
    try:
        diff = await collect_diff(github_client, installation_id, owner, repo, pr_number)
    except ContextCollectionError as exc:
        logger.error(
            "diff_collection_failed",
            installation_id=installation_id,
            pr_number=pr_number,
            stage="context_build",
            error=str(exc),
        )

    # Check budget after diff collection
    elapsed = time.monotonic() - start_time
    if elapsed >= _TOTAL_BUDGET_SECONDS:
        logger.warning(
            "context_collection_budget_exceeded",
            installation_id=installation_id,
            pr_number=pr_number,
            stage="context_build",
            elapsed_ms=int(elapsed * 1000),
        )
        return ReviewContext(
            installation_id=installation_id,
            pr_metadata=pr_metadata,
            diff=diff,
            changed_files=[],
            lines_changed=_count_lines_changed(diff),
        )

    # --- Get list of changed file paths ---
    changed_paths: list[str] = []
    try:
        gh = await github_client.get_installation_client(installation_id)
        files_response = await gh.rest.pulls.async_list_files(
            owner=owner, repo=repo, pull_number=pr_number
        )
        parsed = files_response.parsed_data
        if parsed is not None:
            changed_paths = [f.filename for f in parsed if f.status != "removed"]
    except Exception as exc:
        logger.error(
            "changed_files_list_failed",
            installation_id=installation_id,
            pr_number=pr_number,
            stage="context_build",
            error=str(exc),
        )

    # Check budget after listing files
    elapsed = time.monotonic() - start_time
    if elapsed >= _TOTAL_BUDGET_SECONDS:
        logger.warning(
            "context_collection_budget_exceeded",
            installation_id=installation_id,
            pr_number=pr_number,
            stage="context_build",
            elapsed_ms=int(elapsed * 1000),
        )
        return ReviewContext(
            installation_id=installation_id,
            pr_metadata=pr_metadata,
            diff=diff,
            changed_files=[],
            lines_changed=_count_lines_changed(diff),
        )

    # --- Fetch file contents ---
    changed_files = []
    try:
        changed_files = await collect_changed_files(
            github_client, installation_id, owner, repo, head_sha, changed_paths, cache
        )
    except ContextCollectionError as exc:
        logger.error(
            "file_collection_failed",
            installation_id=installation_id,
            pr_number=pr_number,
            stage="context_build",
            error=str(exc),
        )

    context = ReviewContext(
        installation_id=installation_id,
        pr_metadata=pr_metadata,
        diff=diff,
        changed_files=changed_files,
        lines_changed=_count_lines_changed(diff),
    )

    # Story 3.3: Enrich with related files via Tree-sitter import parsing
    # Graceful degradation: if import resolution fails, continue with empty related_files
    logger.debug(
        "import_resolution_started",
        installation_id=installation_id,
        pr_number=pr_number,
    )
    try:
        context = await resolve_related_files(
            context, github_client, cache, owner, repo, head_sha
        )
    except Exception as exc:
        logger.warning(
            "import_resolution_failed",
            installation_id=installation_id,
            pr_number=pr_number,
            stage="context_build",
            error=str(exc),
        )

    duration_ms = int((time.monotonic() - start_time) * 1000)
    file_count = len(context.changed_files)

    if duration_ms >= int(_TOTAL_BUDGET_SECONDS * 1000):
        logger.warning(
            "context_collection_budget_exceeded",
            installation_id=installation_id,
            pr_number=pr_number,
            stage="context_build",
            elapsed_ms=duration_ms,
        )

    logger.info(
        "context_collection_complete",
        installation_id=installation_id,
        pr_number=pr_number,
        stage="context_build",
        file_count=file_count,
        related_file_count=len(context.related_files),
        duration_ms=duration_ms,
    )

    return context
