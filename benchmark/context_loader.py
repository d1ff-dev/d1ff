"""Build ReviewContext from local benchmark dataset files (Story 7.1, AC: #1).

Reads diff.patch and optional files/ directory from a dataset entry directory
and constructs a fully populated ReviewContext suitable for passing directly
to pipeline/orchestrator.py.

No GitHub API calls are made — this is the benchmark-mode bypass layer.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import structlog

from d1ff.context.models import FileContext, PRMetadata, ReviewContext

logger = structlog.get_logger(__name__)

# Sentinel installation_id used throughout benchmark runs.
BENCHMARK_INSTALLATION_ID = 0


def _infer_language(path: str) -> str | None:
    """Infer programming language from file extension."""
    ext_map: dict[str, str] = {
        ".py": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".java": "java",
        ".cs": "csharp",
        ".go": "go",
        ".rb": "ruby",
        ".rs": "rust",
        ".cpp": "cpp",
        ".c": "c",
        ".h": "c",
        ".hpp": "cpp",
        ".php": "php",
        ".swift": "swift",
        ".kt": "kotlin",
        ".scala": "scala",
    }
    suffix = Path(path).suffix.lower()
    return ext_map.get(suffix)


def _count_changed_lines(diff: str) -> int:
    """Count added + deleted lines in a unified diff."""
    count = 0
    for line in diff.splitlines():
        is_add = line.startswith("+") and not line.startswith("+++")
        is_del = line.startswith("-") and not line.startswith("---")
        if is_add or is_del:
            count += 1
    return count


def load_dataset_entry(entry_dir: Path) -> tuple[dict, ReviewContext]:
    """Load a benchmark dataset entry and construct a ReviewContext.

    Args:
        entry_dir: Path to a dataset entry directory containing metadata.json
                   and diff.patch (and optionally a files/ subdirectory).

    Returns:
        Tuple of (metadata_dict, ReviewContext) where metadata_dict contains
        the raw parsed metadata.json content.

    Raises:
        FileNotFoundError: If metadata.json or diff.patch are missing.
        ValueError: If metadata.json is malformed.
    """
    metadata_path = entry_dir / "metadata.json"
    diff_path = entry_dir / "diff.patch"

    if not metadata_path.exists():
        raise FileNotFoundError(f"metadata.json not found in {entry_dir}")
    if not diff_path.exists():
        raise FileNotFoundError(f"diff.patch not found in {entry_dir}")

    with metadata_path.open(encoding="utf-8") as fh:
        metadata: dict = json.load(fh)

    pr_id: str = metadata.get("pr_id", entry_dir.name)
    repo: str = metadata.get("repo", "benchmark/unknown")
    title: str = metadata.get("title", pr_id)

    diff: str = diff_path.read_text(encoding="utf-8")

    # Load full file contents from files/ subdirectory (optional)
    changed_files: list[FileContext] = []
    files_dir = entry_dir / "files"
    if files_dir.is_dir():
        for file_path in sorted(files_dir.rglob("*")):
            if file_path.is_file():
                rel_path = str(file_path.relative_to(files_dir)).replace(os.sep, "/")
                try:
                    content = file_path.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    logger.warning(
                        "benchmark_skip_binary_file",
                        installation_id="benchmark",
                        pr_number=pr_id,
                        stage="context_loader",
                        file=rel_path,
                    )
                    continue
                changed_files.append(
                    FileContext(
                        path=rel_path,
                        content=content,
                        language=_infer_language(rel_path),
                    )
                )

    lines_changed = _count_changed_lines(diff)

    pr_metadata = PRMetadata(
        number=0,
        title=title,
        author="benchmark",
        base_branch="main",
        head_branch="benchmark",
        html_url=f"https://github.com/{repo}/pull/0",
        draft=False,
    )

    context = ReviewContext(
        installation_id=BENCHMARK_INSTALLATION_ID,
        pr_metadata=pr_metadata,
        diff=diff,
        changed_files=changed_files,
        related_files=[],
        lines_changed=lines_changed,
    )

    logger.info(
        "benchmark_context_loaded",
        installation_id="benchmark",
        pr_number=pr_id,
        stage="context_loader",
        changed_files_count=len(changed_files),
        lines_changed=lines_changed,
    )

    return metadata, context
