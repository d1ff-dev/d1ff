"""Tests for import_resolver — Tree-sitter import parsing & related file discovery (AC: 1-4)."""

from unittest.mock import AsyncMock, MagicMock, patch

import structlog.testing

from d1ff.context.import_resolver import (
    _parse_imports,
    _resolve_import_paths,
    resolve_related_files,
)
from d1ff.context.models import FileContext, PRMetadata, ReviewContext

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PR_METADATA = PRMetadata(
    number=42,
    title="Add feature X",
    author="alice",
    base_branch="main",
    head_branch="feature/x",
    html_url="https://github.com/owner/repo/pull/42",
    draft=False,
)


def _make_review_context(changed_files: list[FileContext]) -> ReviewContext:
    return ReviewContext(
        installation_id=123,
        pr_metadata=PR_METADATA,
        diff="",
        changed_files=changed_files,
    )


def _make_github_client() -> MagicMock:
    client = MagicMock()
    client.get_installation_client = AsyncMock(return_value=MagicMock())
    return client


def _make_cache(path_to_content: dict[str, str] | None = None) -> MagicMock:
    path_to_content = path_to_content or {}

    async def _get(  # type: ignore[no-untyped-def]
        path: str,
        gh: object,
        installation_id: int,
        owner: str,
        repo: str,
        ref: str,
    ) -> str:
        if path in path_to_content:
            return path_to_content[path]
        raise FileNotFoundError(f"Not found: {path}")

    cache = MagicMock()
    cache.get = AsyncMock(side_effect=_get)
    return cache


# ---------------------------------------------------------------------------
# Unit tests — _parse_imports()
# ---------------------------------------------------------------------------


def test_parse_imports_python_basic() -> None:
    """Python import and from-import statements are extracted."""
    content = "import os\nfrom pathlib import Path\n"
    result = _parse_imports(content, "python")
    assert "os" in result
    assert "pathlib" in result


def test_parse_imports_typescript_import() -> None:
    """TypeScript ES import source path is extracted."""
    content = 'import { foo } from "./utils";\n'
    result = _parse_imports(content, "typescript")
    assert "./utils" in result


def test_parse_imports_javascript_require() -> None:
    """JavaScript require() call source path is extracted."""
    content = "const x = require('./bar');\n"
    result = _parse_imports(content, "javascript")
    assert "./bar" in result


def test_parse_imports_unsupported_language() -> None:
    """Unsupported language returns empty list without error."""
    result = _parse_imports("x = 1", "ruby")
    assert result == []


def test_parse_imports_tree_sitter_error() -> None:
    """Any tree-sitter exception is caught — returns empty list, no raise."""
    mock_lang = MagicMock(side_effect=Exception("boom"))
    with patch("d1ff.context.import_resolver._LANGUAGES", {"python": mock_lang}):
        result = _parse_imports("import os", "python")
    assert result == []


def test_parse_imports_java() -> None:
    """Java import declaration is extracted."""
    content = "import com.example.Foo;\n"
    result = _parse_imports(content, "java")
    assert "com.example.Foo" in result


def test_parse_imports_csharp() -> None:
    """C# using directive is extracted."""
    content = "using System.IO;\n"
    result = _parse_imports(content, "csharp")
    assert "System.IO" in result


# ---------------------------------------------------------------------------
# Unit tests — _resolve_import_paths()
# ---------------------------------------------------------------------------


def test_resolve_python_dotted_import() -> None:
    """Dotted Python import resolves to src/.../.py path."""
    result = _resolve_import_paths(["d1ff.context.models"], "src/d1ff/app.py", "python")
    assert "src/d1ff/context/models.py" in result


def test_resolve_typescript_relative() -> None:
    """Relative TypeScript import produces .ts and .tsx candidates."""
    result = _resolve_import_paths(["./utils"], "src/app/index.ts", "typescript")
    assert "src/app/utils.ts" in result
    assert "src/app/utils.tsx" in result


def test_resolve_skips_stdlib() -> None:
    """Single-word stdlib-like Python imports produce no local candidates."""
    result = _resolve_import_paths(["os"], "src/d1ff/app.py", "python")
    # "os" is in _STDLIB_SINGLE_WORDS — should be filtered
    assert result == []


def test_resolve_python_class_import_strips_class_name() -> None:
    """Python import ending with uppercase class strips class name from path."""
    result = _resolve_import_paths(
        ["d1ff.context.models.ReviewContext"], "src/d1ff/app.py", "python"
    )
    assert "src/d1ff/context/models.py" in result


def test_resolve_java_import() -> None:
    """Java import maps to src/main/java/... .java path."""
    result = _resolve_import_paths(
        ["com.example.MyClass"], "src/main/java/com/example/App.java", "java"
    )
    assert "src/main/java/com/example/MyClass.java" in result


def test_resolve_csharp_import() -> None:
    """C# using maps to Namespace/Class.cs path."""
    result = _resolve_import_paths(["MyNamespace.MyClass"], "MyNamespace/App.cs", "csharp")
    assert "MyNamespace/MyClass.cs" in result


# ---------------------------------------------------------------------------
# Integration tests — resolve_related_files()
# ---------------------------------------------------------------------------


async def test_resolve_related_files_success() -> None:
    """resolve_related_files returns context with related files populated."""
    py_content = "from d1ff.context.models import ReviewContext\n"
    changed_files = [
        FileContext(path="src/d1ff/app.py", content=py_content, language="python")
    ]
    context = _make_review_context(changed_files)
    github_client = _make_github_client()
    cache = _make_cache({"src/d1ff/context/models.py": "class ReviewContext: pass"})

    result = await resolve_related_files(
        context, github_client, cache, "owner", "repo", "abc123"
    )

    assert len(result.related_files) >= 1
    related_paths = [f.path for f in result.related_files]
    assert "src/d1ff/context/models.py" in related_paths


async def test_resolve_related_files_graceful_on_parse_failure() -> None:
    """If _parse_imports raises, original context is returned unchanged."""
    changed_files = [
        FileContext(path="src/d1ff/app.py", content="import os\n", language="python")
    ]
    context = _make_review_context(changed_files)
    github_client = _make_github_client()
    cache = _make_cache()

    with patch(
        "d1ff.context.import_resolver._parse_imports",
        side_effect=RuntimeError("parse boom"),
    ):
        result = await resolve_related_files(
            context, github_client, cache, "owner", "repo", "abc123"
        )

    # Should still return a valid ReviewContext (with empty related_files)
    assert isinstance(result, ReviewContext)
    assert result.related_files == []


async def test_resolve_related_files_skips_already_changed_files() -> None:
    """Files already in changed_files are not added to related_files."""
    py_content = "from d1ff.context.models import ReviewContext\n"
    # Both files are in changed_files — the import target is already present
    changed_files = [
        FileContext(path="src/d1ff/app.py", content=py_content, language="python"),
        FileContext(
            path="src/d1ff/context/models.py",
            content="class ReviewContext: pass",
            language="python",
        ),
    ]
    context = _make_review_context(changed_files)
    github_client = _make_github_client()
    cache = _make_cache({"src/d1ff/context/models.py": "class ReviewContext: pass"})

    result = await resolve_related_files(
        context, github_client, cache, "owner", "repo", "abc123"
    )

    related_paths = [f.path for f in result.related_files]
    assert "src/d1ff/context/models.py" not in related_paths


async def test_resolve_related_files_max_3_files() -> None:
    """At most 3 related files are added across all changed files."""
    # Python file importing 5 different modules
    py_content = (
        "from d1ff.a import A\n"
        "from d1ff.b import B\n"
        "from d1ff.c import C\n"
        "from d1ff.d import D\n"
        "from d1ff.e import E\n"
    )
    changed_files = [
        FileContext(path="src/d1ff/app.py", content=py_content, language="python")
    ]
    context = _make_review_context(changed_files)
    github_client = _make_github_client()
    # All candidate paths exist
    cache = _make_cache(
        {
            "src/d1ff/a.py": "class A: pass",
            "src/d1ff/b.py": "class B: pass",
            "src/d1ff/c.py": "class C: pass",
            "src/d1ff/d.py": "class D: pass",
            "src/d1ff/e.py": "class E: pass",
        }
    )

    result = await resolve_related_files(
        context, github_client, cache, "owner", "repo", "abc123"
    )

    assert len(result.related_files) <= 3


async def test_resolve_related_files_unsupported_language_skipped() -> None:
    """Changed files with language=None are skipped silently."""
    changed_files = [
        FileContext(
            path="data/config.toml",
            content="[settings]\nkey = value\n",
            language=None,
        )
    ]
    context = _make_review_context(changed_files)
    github_client = _make_github_client()
    cache = _make_cache()

    with patch("d1ff.context.import_resolver._parse_imports") as mock_parse:
        result = await resolve_related_files(
            context, github_client, cache, "owner", "repo", "abc123"
        )

    mock_parse.assert_not_called()
    assert result.related_files == []


async def test_resolve_related_files_fetch_failure_is_silent() -> None:
    """If cache.get() raises, no exception is raised and that candidate is skipped."""
    py_content = "from d1ff.context.models import ReviewContext\n"
    changed_files = [
        FileContext(path="src/d1ff/app.py", content=py_content, language="python")
    ]
    context = _make_review_context(changed_files)
    github_client = _make_github_client()
    # cache always raises — simulates file not found
    cache = _make_cache()  # all paths raise FileNotFoundError

    result = await resolve_related_files(
        context, github_client, cache, "owner", "repo", "abc123"
    )

    # No exception, just empty related_files
    assert result.related_files == []


async def test_resolve_related_files_returns_model_copy() -> None:
    """The returned context is a new object; original related_files remains empty."""
    py_content = "from d1ff.context.models import ReviewContext\n"
    changed_files = [
        FileContext(path="src/d1ff/app.py", content=py_content, language="python")
    ]
    context = _make_review_context(changed_files)
    github_client = _make_github_client()
    cache = _make_cache({"src/d1ff/context/models.py": "class ReviewContext: pass"})

    result = await resolve_related_files(
        context, github_client, cache, "owner", "repo", "abc123"
    )

    assert result is not context
    assert context.related_files == []


async def test_resolve_related_files_logs_completion() -> None:
    """resolve_related_files emits import_resolver_complete log entry."""
    changed_files = [
        FileContext(path="src/d1ff/app.py", content="import os\n", language="python")
    ]
    context = _make_review_context(changed_files)
    github_client = _make_github_client()
    cache = _make_cache()

    with structlog.testing.capture_logs() as logs:
        await resolve_related_files(
            context, github_client, cache, "owner", "repo", "abc123"
        )

    complete_logs = [e for e in logs if e.get("event") == "import_resolver_complete"]
    assert len(complete_logs) == 1
    assert "related_file_count" in complete_logs[0]
    assert "duration_ms" in complete_logs[0]
