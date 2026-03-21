"""Tree-sitter import parsing and related file discovery (FR10, NFR20)."""

import os
import time
from typing import Any

import structlog

from d1ff.context.file_collector import FileCache, _infer_language
from d1ff.context.models import FileContext, ReviewContext

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Language initialisation — module-level, done once at import time
# ---------------------------------------------------------------------------

_LANGUAGES: dict[str, Any] = {}

try:
    import tree_sitter_python as tspython
    from tree_sitter import Language  # noqa: F401 — imported here for type safety

    _LANGUAGES["python"] = Language(tspython.language())
except Exception as _exc:  # pragma: no cover
    logger.warning("tree_sitter_language_init_failed", language="python", error=str(_exc))

try:
    import tree_sitter_javascript as tsjavascript
    from tree_sitter import Language as _Language  # noqa: F811

    _LANGUAGES["javascript"] = _Language(tsjavascript.language())
except Exception as _exc:  # pragma: no cover
    logger.warning("tree_sitter_language_init_failed", language="javascript", error=str(_exc))

try:
    import tree_sitter_typescript as tstypescript
    from tree_sitter import Language as _Language2  # noqa: F811

    _LANGUAGES["typescript"] = _Language2(tstypescript.language_typescript())
    _LANGUAGES["tsx"] = _Language2(tstypescript.language_tsx())
except Exception as _exc:  # pragma: no cover
    logger.warning("tree_sitter_language_init_failed", language="typescript", error=str(_exc))

try:
    import tree_sitter_java as tsjava
    from tree_sitter import Language as _Language3  # noqa: F811

    _LANGUAGES["java"] = _Language3(tsjava.language())
except Exception as _exc:  # pragma: no cover
    logger.warning("tree_sitter_language_init_failed", language="java", error=str(_exc))

try:
    import tree_sitter_c_sharp as tscsharp
    from tree_sitter import Language as _Language4  # noqa: F811

    _LANGUAGES["csharp"] = _Language4(tscsharp.language())
except Exception as _exc:  # pragma: no cover
    logger.warning("tree_sitter_language_init_failed", language="csharp", error=str(_exc))

# ---------------------------------------------------------------------------
# Import query strings — Tree-sitter S-expression syntax
# ---------------------------------------------------------------------------

_IMPORT_QUERIES: dict[str, str] = {
    "python": """
        (import_statement (dotted_name) @import_path)
        (import_from_statement module_name: (dotted_name) @import_path)
        (import_from_statement module_name: (relative_import) @import_path)
    """,
    "javascript": """
        (import_statement source: (string (string_fragment) @import_path))
        (call_expression function: (identifier) @fn (#eq? @fn "require")
            arguments: (arguments (string (string_fragment) @import_path)))
    """,
    "typescript": """
        (import_statement source: (string (string_fragment) @import_path))
        (call_expression function: (identifier) @fn (#eq? @fn "require")
            arguments: (arguments (string (string_fragment) @import_path)))
    """,
    "tsx": """
        (import_statement source: (string (string_fragment) @import_path))
    """,
    "java": """
        (import_declaration (scoped_identifier) @import_path)
    """,
    "csharp": """
        (using_directive (qualified_name) @import_path)
        (using_directive (identifier) @import_path)
    """,
}

# ---------------------------------------------------------------------------
# Import parsing
# ---------------------------------------------------------------------------

_STDLIB_SINGLE_WORDS = frozenset(
    [
        "os",
        "sys",
        "re",
        "io",
        "abc",
        "ast",
        "csv",
        "dis",
        "enum",
        "math",
        "time",
        "copy",
        "glob",
        "json",
        "logging",
        "pathlib",
        "random",
        "shutil",
        "string",
        "struct",
        "typing",
        "warnings",
        "collections",
        "functools",
        "itertools",
        "operator",
        "threading",
        "asyncio",
        "contextlib",
        "dataclasses",
        "datetime",
        "decimal",
        "hashlib",
        "hmac",
        "inspect",
        "numbers",
        "pickle",
        "platform",
        "pprint",
        "queue",
        "signal",
        "socket",
        "sqlite3",
        "subprocess",
        "tempfile",
        "textwrap",
        "traceback",
        "unittest",
        "urllib",
        "uuid",
        "weakref",
        "zipfile",
    ]
)


def _parse_imports(content: str, language: str) -> list[str]:
    """Parse import statements from file content using Tree-sitter.

    Args:
        content: Source code as a string.
        language: Language identifier (e.g. "python", "typescript").

    Returns:
        List of raw import path strings found in the file.
        Returns empty list if language is unsupported or parsing fails.
    """
    if language not in _LANGUAGES:
        return []

    try:
        from tree_sitter import Parser, Query, QueryCursor

        parser = Parser(_LANGUAGES[language])
        tree = parser.parse(content.encode("utf-8"))
        query = Query(_LANGUAGES[language], _IMPORT_QUERIES[language])
        cursor = QueryCursor(query)
        captures = cursor.captures(tree.root_node)
        import_nodes = captures.get("import_path", [])
        return [
            node.text.decode("utf-8")
            for node in import_nodes
            if node.text is not None
        ]
    except Exception as exc:
        logger.warning(
            "tree_sitter_parse_error",
            language=language,
            error=str(exc),
        )
        return []


# ---------------------------------------------------------------------------
# Import path resolution
# ---------------------------------------------------------------------------


def _resolve_relative_js_path(import_str: str, source_path: str) -> list[str]:
    """Resolve a relative JS/TS import path to candidate file paths."""
    source_dir = os.path.dirname(source_path)
    base = os.path.normpath(os.path.join(source_dir, import_str)).replace("\\", "/")
    return [f"{base}.ts", f"{base}.tsx", f"{base}.js", f"{base}/index.ts"]


def _resolve_import_paths(
    import_strings: list[str], source_file_path: str, language: str
) -> list[str]:
    """Convert import strings to candidate repository-relative file paths.

    Args:
        import_strings: Raw import strings extracted from source.
        source_file_path: Repo-relative path of the importing file.
        language: Language identifier.

    Returns:
        List of candidate paths (may not all exist — checked externally).
    """
    candidates: list[str] = []

    for imp in import_strings:
        if language == "python":
            # Filter out stdlib single-word imports
            if imp in _STDLIB_SINGLE_WORDS:
                continue
            # Strip trailing imported name if it looks like a class (uppercase first)
            parts = imp.split(".")
            if len(parts) > 1 and parts[-1][0].isupper():
                parts = parts[:-1]
            # Convert dots to slashes, prepend src/, append .py
            path = "src/" + "/".join(parts) + ".py"
            candidates.append(path)

        elif language in ("javascript", "typescript", "tsx"):
            if imp.startswith("."):
                # Relative import
                candidates.extend(_resolve_relative_js_path(imp, source_file_path))
            # Absolute/node_modules imports — skip (not in repo)

        elif language == "java":
            # com.example.MyClass → src/main/java/com/example/MyClass.java
            path = "src/main/java/" + imp.replace(".", "/") + ".java"
            candidates.append(path)

        elif language == "csharp":
            # MyNamespace.MyClass → MyNamespace/MyClass.cs (best-effort)
            path = imp.replace(".", "/") + ".cs"
            candidates.append(path)

        # Cap at 5 candidates per import to avoid explosion
        if len(candidates) >= 5:
            break

    return candidates


# ---------------------------------------------------------------------------
# Main public function
# ---------------------------------------------------------------------------


async def resolve_related_files(
    context: ReviewContext,
    github_client: Any,
    cache: FileCache,
    owner: str,
    repo: str,
    head_sha: str,
) -> ReviewContext:
    """Enrich a ReviewContext with related files discovered via Tree-sitter.

    Parses import statements from each changed file, resolves them to
    repository paths, fetches their contents via GitHub API (using the cache),
    and returns a new ReviewContext with ``related_files`` populated.

    At most 3 unique related files are added in total (across all changed files).
    Files already in ``context.changed_files`` are never duplicated.

    Args:
        context: ReviewContext with changed_files already populated.
        github_client: Authenticated GitHub App client.
        cache: Per-review FileCache — reuse the same instance from context_builder.
        owner: Repository owner.
        repo: Repository name.
        head_sha: Head commit SHA for file fetching.

    Returns:
        A new ReviewContext (model_copy) with related_files populated.
        Returns the original context unchanged if any unhandled error occurs.
    """
    installation_id = context.installation_id
    pr_number = context.pr_metadata.number
    start_time = time.monotonic()

    try:
        gh = await github_client.get_installation_client(installation_id)
        changed_paths = {fc.path for fc in context.changed_files}
        related_files: list[FileContext] = []

        for file in context.changed_files:
            if file.language is None:
                continue

            if len(related_files) >= 3:
                break

            try:
                import_strings = _parse_imports(file.content, file.language)
            except Exception as exc:
                logger.warning(
                    "tree_sitter_parse_error",
                    installation_id=installation_id,
                    pr_number=pr_number,
                    stage="import_resolution",
                    file_path=file.path,
                    language=file.language,
                    error=str(exc),
                )
                continue

            candidates = _resolve_import_paths(import_strings, file.path, file.language)

            for candidate in candidates:
                if len(related_files) >= 3:
                    break
                if candidate in changed_paths:
                    continue

                try:
                    content = await cache.get(
                        candidate, gh, installation_id, owner, repo, head_sha
                    )
                    related_files.append(
                        FileContext(
                            path=candidate,
                            content=content,
                            language=_infer_language(candidate),
                        )
                    )
                    changed_paths.add(candidate)  # prevent duplicates across iterations
                except Exception:
                    pass  # File may not exist; skip silently

        duration_ms = int((time.monotonic() - start_time) * 1000)
        logger.info(
            "import_resolver_complete",
            installation_id=installation_id,
            pr_number=pr_number,
            stage="import_resolution",
            related_file_count=len(related_files),
            duration_ms=duration_ms,
        )

        return context.model_copy(update={"related_files": related_files})

    except Exception as exc:
        logger.warning(
            "import_resolution_failed",
            installation_id=installation_id,
            pr_number=pr_number,
            stage="import_resolution",
            error=str(exc),
        )
        return context
