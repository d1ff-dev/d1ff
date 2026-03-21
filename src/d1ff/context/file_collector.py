"""Fetch changed file contents from GitHub API with in-memory caching (FR9, FR11, NFR5, NFR10)."""

import asyncio
import base64
from typing import Any

import structlog

from d1ff.context.exceptions import ContextCollectionError
from d1ff.context.models import FileContext
from d1ff.github import GitHubAppClient

logger = structlog.get_logger()

# Language inference map: extension → language name
_EXT_TO_LANGUAGE: dict[str, str] = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".cs": "csharp",
    ".java": "java",
}


def _infer_language(path: str) -> str | None:
    """Infer programming language from file extension. Returns None if unknown."""
    dot_pos = path.rfind(".")
    if dot_pos == -1:
        return None
    ext = path[dot_pos:]
    return _EXT_TO_LANGUAGE.get(ext)


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


async def _fetch_file_content(
    gh: Any,
    installation_id: int,
    owner: str,
    repo: str,
    path: str,
    ref: str,
) -> str:
    """Fetch raw file content from GitHub API and decode from base64.

    Args:
        gh: githubkit installation-scoped client.
        installation_id: Installation ID for logging.
        owner: Repository owner.
        repo: Repository name.
        path: File path relative to repository root.
        ref: Git ref (commit SHA or branch name).

    Returns:
        Decoded file content as a UTF-8 string.

    Raises:
        ContextCollectionError: If both fetch attempts fail.
    """

    async def _fetch() -> str:
        response = await gh.rest.repos.async_get_content(
            owner=owner,
            repo=repo,
            path=path,
            ref=ref,
        )
        encoded = response.parsed_data.content
        # GitHub may include newlines in the base64 string — strip them
        return base64.b64decode(encoded.replace("\n", "")).decode("utf-8")

    result: str = await _with_retry(_fetch, stage="file_fetch", installation_id=installation_id)
    return result


class FileCache:
    """Per-review in-memory file content cache. Not thread-safe — single review only."""

    def __init__(self) -> None:
        self._cache: dict[str, str] = {}  # path → content

    async def get(
        self,
        path: str,
        gh: Any,
        installation_id: int,
        owner: str,
        repo: str,
        ref: str,
    ) -> str:
        """Return cached content or fetch from GitHub API."""
        if path in self._cache:
            logger.debug("file_cache_hit", path=path)
            return self._cache[path]

        logger.debug("file_cache_miss", path=path)
        content = await _fetch_file_content(gh, installation_id, owner, repo, path, ref)
        self._cache[path] = content
        return content

    @property
    def size(self) -> int:
        return len(self._cache)


async def collect_changed_files(
    github_client: GitHubAppClient,
    installation_id: int,
    owner: str,
    repo: str,
    ref: str,
    changed_paths: list[str],
    cache: FileCache,
) -> list[FileContext]:
    """Fetch full contents of each changed file, using the cache for deduplication.

    Args:
        github_client: Authenticated GitHub App client.
        installation_id: Installation ID for client auth.
        owner: Repository owner.
        repo: Repository name.
        ref: Head commit SHA.
        changed_paths: List of changed file paths from the diff.
        cache: Per-review FileCache instance.

    Returns:
        List of FileContext objects with path, content, and inferred language.
    """
    gh = await github_client.get_installation_client(installation_id)

    file_contexts: list[FileContext] = []
    for path in changed_paths:
        content = await cache.get(path, gh, installation_id, owner, repo, ref)
        file_contexts.append(
            FileContext(
                path=path,
                content=content,
                language=_infer_language(path),
            )
        )

    return file_contexts
