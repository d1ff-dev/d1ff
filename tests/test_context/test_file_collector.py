"""Tests for file_collector — fetch changed file contents with caching (AC: 2, 3)."""

import base64
from unittest.mock import AsyncMock, MagicMock

from d1ff.context.file_collector import FileCache, _infer_language, collect_changed_files
from d1ff.context.models import FileContext
from d1ff.github import GitHubAppClient


def _make_content_response(text: str) -> MagicMock:
    """Build a mock githubkit get_content response with base64-encoded content."""
    encoded = base64.b64encode(text.encode("utf-8")).decode("ascii")
    response = MagicMock()
    response.parsed_data.content = encoded
    return response


def _make_installation_client(file_contents: dict[str, str]) -> MagicMock:
    """Build a mock githubkit client that returns content for given path→text mapping."""

    async def get_content(**kwargs):  # type: ignore[no-untyped-def]
        path = kwargs.get("path", "")
        text = file_contents.get(path, "")
        return _make_content_response(text)

    gh = MagicMock()
    gh.rest.repos.async_get_content = AsyncMock(side_effect=get_content)
    return gh


def _make_github_client(gh: MagicMock) -> MagicMock:
    """Build a mock GitHubAppClient that returns the given installation client."""
    client = MagicMock(spec=GitHubAppClient)
    client.get_installation_client = AsyncMock(return_value=gh)
    return client


async def test_fetch_file_content_decodes_base64() -> None:
    """_fetch_file_content returns decoded UTF-8 string from base64 API response."""
    from d1ff.context.file_collector import _fetch_file_content

    expected_text = "print('hello world')\n"
    gh = _make_installation_client({"src/foo.py": expected_text})

    result = await _fetch_file_content(gh, 123, "owner", "repo", "src/foo.py", "abc123")

    assert result == expected_text


async def test_file_cache_hit_avoids_api_call() -> None:
    """Calling cache.get() twice for the same path makes only one API call."""
    text = "cached content\n"
    gh = _make_installation_client({"src/foo.py": text})

    cache = FileCache()
    result1 = await cache.get("src/foo.py", gh, 123, "owner", "repo", "abc123")
    result2 = await cache.get("src/foo.py", gh, 123, "owner", "repo", "abc123")

    assert result1 == text
    assert result2 == text
    assert gh.rest.repos.async_get_content.await_count == 1


async def test_file_cache_miss_fetches_and_stores() -> None:
    """cache.get() on a new path fetches from API and stores in cache."""
    text = "new content\n"
    gh = _make_installation_client({"new_file.py": text})

    cache = FileCache()
    assert cache.size == 0

    result = await cache.get("new_file.py", gh, 123, "owner", "repo", "abc123")

    assert result == text
    assert cache.size == 1
    gh.rest.repos.async_get_content.assert_awaited_once()


async def test_collect_changed_files_returns_file_contexts() -> None:
    """collect_changed_files returns FileContext objects for each changed path."""
    file_map = {
        "src/a.py": "content a\n",
        "src/b.py": "content b\n",
        "src/c.ts": "content c\n",
    }
    gh = _make_installation_client(file_map)
    client = _make_github_client(gh)

    cache = FileCache()
    results = await collect_changed_files(
        client, 123, "owner", "repo", "abc123",
        ["src/a.py", "src/b.py", "src/c.ts"], cache
    )

    assert len(results) == 3
    assert all(isinstance(r, FileContext) for r in results)
    paths = [r.path for r in results]
    assert "src/a.py" in paths
    assert "src/b.py" in paths
    assert "src/c.ts" in paths
    for r in results:
        assert r.content == file_map[r.path]


def test_language_inference_python() -> None:
    """Files with .py extension get language='python'."""
    assert _infer_language("src/foo.py") == "python"


def test_language_inference_typescript() -> None:
    """Files with .ts or .tsx extension get language='typescript'."""
    assert _infer_language("src/App.tsx") == "typescript"
    assert _infer_language("src/utils.ts") == "typescript"


def test_language_inference_javascript() -> None:
    """Files with .js or .jsx extension get language='javascript'."""
    assert _infer_language("src/index.js") == "javascript"
    assert _infer_language("src/App.jsx") == "javascript"


def test_language_inference_unknown() -> None:
    """Files with unrecognised or missing extension get language=None."""
    assert _infer_language("data/config.toml") is None
    assert _infer_language("Makefile") is None
