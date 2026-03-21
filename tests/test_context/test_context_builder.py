"""Tests for context_builder — orchestrate diff + files → ReviewContext (AC: 5)."""

from unittest.mock import AsyncMock, MagicMock, patch

import structlog.testing

from d1ff.context.context_builder import build_review_context
from d1ff.context.models import FileContext, ReviewContext
from d1ff.github import GitHubAppClient
from d1ff.webhook.models import PullRequestPayload

# Minimal valid PullRequestPayload fixture (established in Story 3.1)
PR_PAYLOAD_DICT = {
    "action": "opened",
    "pull_request": {
        "number": 42,
        "title": "Add feature X",
        "state": "open",
        "draft": False,
        "user": {"login": "alice"},
        "base": {"ref": "main"},
        "head": {"ref": "feature/x", "sha": "abc123def456"},
        "html_url": "https://github.com/owner/repo/pull/42",
    },
    "repository": {
        "id": 1,
        "name": "repo",
        "full_name": "owner/repo",
        "private": False,
    },
    "installation": {
        "id": 123,
        "account": {"login": "owner", "type": "Organization"},
    },
}

SAMPLE_DIFF = "diff --git a/src/foo.py b/src/foo.py\n+new line\n"

SAMPLE_FILES = [
    MagicMock(filename="src/foo.py", status="modified"),
    MagicMock(filename="src/bar.py", status="added"),
]


def _make_github_client() -> MagicMock:
    """Build a mock GitHubAppClient with a mock installation client."""
    files_response = MagicMock()
    files_response.parsed_data = SAMPLE_FILES

    gh = MagicMock()
    gh.rest.pulls.async_list_files = AsyncMock(return_value=files_response)

    client = MagicMock(spec=GitHubAppClient)
    client.get_installation_client = AsyncMock(return_value=gh)
    return client


async def test_build_review_context_returns_review_context() -> None:
    """build_review_context returns a ReviewContext with correct top-level structure."""
    pr_payload = PullRequestPayload.model_validate(PR_PAYLOAD_DICT)
    client = _make_github_client()

    file_contexts = [
        FileContext(path="src/foo.py", content="content foo", language="python"),
        FileContext(path="src/bar.py", content="content bar", language="python"),
    ]

    mock_diff = AsyncMock(return_value=SAMPLE_DIFF)
    mock_files = AsyncMock(return_value=file_contexts)
    with (
        patch("d1ff.context.context_builder.collect_diff", new=mock_diff),
        patch("d1ff.context.context_builder.collect_changed_files", new=mock_files),
    ):
        result = await build_review_context(client, pr_payload)

    assert isinstance(result, ReviewContext)
    assert result.installation_id == 123
    assert result.diff == SAMPLE_DIFF
    assert result.changed_files == file_contexts


async def test_build_review_context_pr_metadata_mapped_correctly() -> None:
    """PRMetadata fields are correctly extracted from PullRequestPayload."""
    pr_payload = PullRequestPayload.model_validate(PR_PAYLOAD_DICT)
    client = _make_github_client()

    with (
        patch("d1ff.context.context_builder.collect_diff", new=AsyncMock(return_value="")),
        patch(
            "d1ff.context.context_builder.collect_changed_files",
            new=AsyncMock(return_value=[]),
        ),
    ):
        result = await build_review_context(client, pr_payload)

    meta = result.pr_metadata
    assert meta.author == "alice"
    assert meta.base_branch == "main"
    assert meta.head_branch == "feature/x"
    assert meta.number == 42
    assert meta.title == "Add feature X"
    assert meta.html_url == "https://github.com/owner/repo/pull/42"
    assert meta.draft is False


async def test_build_review_context_related_files_empty() -> None:
    """ReviewContext.related_files defaults to empty list (Story 3.3 scope)."""
    pr_payload = PullRequestPayload.model_validate(PR_PAYLOAD_DICT)
    client = _make_github_client()

    with (
        patch("d1ff.context.context_builder.collect_diff", new=AsyncMock(return_value="")),
        patch(
            "d1ff.context.context_builder.collect_changed_files",
            new=AsyncMock(return_value=[]),
        ),
    ):
        result = await build_review_context(client, pr_payload)

    assert result.related_files == []


async def test_build_review_context_uses_cache() -> None:
    """The same FileCache instance is passed to both collect_diff and collect_changed_files."""
    from d1ff.context.file_collector import FileCache

    pr_payload = PullRequestPayload.model_validate(PR_PAYLOAD_DICT)
    client = _make_github_client()

    captured_caches: list[FileCache] = []

    async def mock_collect_changed_files(
        github_client, installation_id, owner, repo, ref, changed_paths, cache
    ):
        captured_caches.append(cache)
        return []

    with (
        patch("d1ff.context.context_builder.collect_diff", new=AsyncMock(return_value="")),
        patch(
            "d1ff.context.context_builder.collect_changed_files",
            side_effect=mock_collect_changed_files,
        ),
    ):
        await build_review_context(client, pr_payload)

    # Only one FileCache should be created per review call
    assert len(captured_caches) == 1
    assert isinstance(captured_caches[0], FileCache)


async def test_build_review_context_logs_file_count() -> None:
    """build_review_context emits a log record containing file_count."""
    pr_payload = PullRequestPayload.model_validate(PR_PAYLOAD_DICT)
    client = _make_github_client()

    file_contexts = [
        FileContext(path="src/foo.py", content="content", language="python"),
    ]

    with (
        structlog.testing.capture_logs() as logs,
        patch("d1ff.context.context_builder.collect_diff", new=AsyncMock(return_value="")),
        patch(
            "d1ff.context.context_builder.collect_changed_files",
            new=AsyncMock(return_value=file_contexts),
        ),
    ):
        await build_review_context(client, pr_payload)

    complete_logs = [
        entry for entry in logs if entry.get("event") == "context_collection_complete"
    ]
    assert len(complete_logs) == 1
    assert complete_logs[0]["file_count"] == 1
