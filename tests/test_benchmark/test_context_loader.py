"""Tests for benchmark/context_loader.py (Story 7.1, AC: #1).

Verifies that load_dataset_entry constructs a valid ReviewContext from local
diff + files without any network calls.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from benchmark.context_loader import (
    BENCHMARK_INSTALLATION_ID,
    _count_changed_lines,
    _infer_language,
    load_dataset_entry,
)
from d1ff.context.models import ReviewContext

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SIMPLE_DIFF = Path(__file__).parent.parent / "fixtures" / "diffs" / "simple_bug.patch"


@pytest.fixture()
def minimal_entry(tmp_path: Path) -> Path:
    """Dataset entry with only metadata.json + diff.patch (no files/)."""
    metadata = {
        "pr_id": "pr-test-minimal",
        "repo": "test-org/test-repo",
        "title": "Minimal test PR",
        "known_bugs": [
            {
                "file": "src/utils/helpers.py",
                "line": 5,
                "description": "No guard",
                "severity": "high",
            }
        ],
    }
    diff_content = SIMPLE_DIFF.read_text(encoding="utf-8")
    entry_dir = tmp_path / "pr-test-minimal"
    entry_dir.mkdir()
    (entry_dir / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    (entry_dir / "diff.patch").write_text(diff_content, encoding="utf-8")
    return entry_dir


@pytest.fixture()
def entry_with_files(tmp_path: Path) -> Path:
    """Dataset entry with metadata.json, diff.patch, AND a files/ directory."""
    metadata = {
        "pr_id": "pr-test-with-files",
        "repo": "test-org/test-repo",
        "title": "PR with full file context",
        "known_bugs": [],
    }
    diff_content = SIMPLE_DIFF.read_text(encoding="utf-8")
    entry_dir = tmp_path / "pr-test-with-files"
    entry_dir.mkdir()
    (entry_dir / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    (entry_dir / "diff.patch").write_text(diff_content, encoding="utf-8")

    files_dir = entry_dir / "files"
    (files_dir / "src" / "utils").mkdir(parents=True)
    (files_dir / "src" / "utils" / "helpers.py").write_text(
        "def divide(a, b):\n    return a / b\n",
        encoding="utf-8",
    )
    (files_dir / "src" / "utils" / "other.ts").write_text(
        "export const hello = () => 'world';\n",
        encoding="utf-8",
    )
    return entry_dir


# ---------------------------------------------------------------------------
# Tests: _infer_language
# ---------------------------------------------------------------------------


def test_infer_language_python() -> None:
    assert _infer_language("src/utils/foo.py") == "python"


def test_infer_language_typescript() -> None:
    assert _infer_language("src/components/Button.tsx") == "typescript"


def test_infer_language_javascript() -> None:
    assert _infer_language("src/index.js") == "javascript"


def test_infer_language_unknown_extension() -> None:
    assert _infer_language("README.md") is None


def test_infer_language_no_extension() -> None:
    assert _infer_language("Makefile") is None


# ---------------------------------------------------------------------------
# Tests: _count_changed_lines
# ---------------------------------------------------------------------------


def test_count_changed_lines_additions_only() -> None:
    diff = "+++ b/foo.py\n+line1\n+line2\n context\n"
    assert _count_changed_lines(diff) == 2


def test_count_changed_lines_additions_and_deletions() -> None:
    diff = "+++ b/foo.py\n+added\n--- a/foo.py\n-removed\n context\n"
    assert _count_changed_lines(diff) == 2


def test_count_changed_lines_empty_diff() -> None:
    assert _count_changed_lines("") == 0


def test_count_changed_lines_excludes_diff_headers() -> None:
    # Lines starting with +++ / --- are header lines, not code changes
    diff = "+++ b/foo.py\n--- a/foo.py\n+actual change\n"
    assert _count_changed_lines(diff) == 1


# ---------------------------------------------------------------------------
# Tests: load_dataset_entry — minimal (no files/)
# ---------------------------------------------------------------------------


def test_load_dataset_entry_returns_metadata_and_context(minimal_entry: Path) -> None:
    metadata, context = load_dataset_entry(minimal_entry)
    assert isinstance(metadata, dict)
    assert isinstance(context, ReviewContext)


def test_load_dataset_entry_sets_benchmark_installation_id(minimal_entry: Path) -> None:
    _, context = load_dataset_entry(minimal_entry)
    assert context.installation_id == BENCHMARK_INSTALLATION_ID


def test_load_dataset_entry_sets_correct_title(minimal_entry: Path) -> None:
    _, context = load_dataset_entry(minimal_entry)
    assert context.pr_metadata.title == "Minimal test PR"


def test_load_dataset_entry_diff_is_nonempty(minimal_entry: Path) -> None:
    _, context = load_dataset_entry(minimal_entry)
    assert len(context.diff) > 0


def test_load_dataset_entry_no_files_dir_gives_empty_changed_files(minimal_entry: Path) -> None:
    _, context = load_dataset_entry(minimal_entry)
    assert context.changed_files == []


def test_load_dataset_entry_related_files_empty(minimal_entry: Path) -> None:
    _, context = load_dataset_entry(minimal_entry)
    assert context.related_files == []


def test_load_dataset_entry_lines_changed_nonzero(minimal_entry: Path) -> None:
    _, context = load_dataset_entry(minimal_entry)
    assert context.lines_changed > 0


def test_load_dataset_entry_metadata_has_known_bugs(minimal_entry: Path) -> None:
    metadata, _ = load_dataset_entry(minimal_entry)
    assert len(metadata["known_bugs"]) == 1


# ---------------------------------------------------------------------------
# Tests: load_dataset_entry — with files/
# ---------------------------------------------------------------------------


def test_load_dataset_entry_with_files_loads_changed_files(entry_with_files: Path) -> None:
    _, context = load_dataset_entry(entry_with_files)
    assert len(context.changed_files) == 2


def test_load_dataset_entry_with_files_paths_use_forward_slashes(entry_with_files: Path) -> None:
    _, context = load_dataset_entry(entry_with_files)
    for fc in context.changed_files:
        assert "\\" not in fc.path


def test_load_dataset_entry_with_files_infers_language(entry_with_files: Path) -> None:
    _, context = load_dataset_entry(entry_with_files)
    languages = {fc.path: fc.language for fc in context.changed_files}
    assert languages.get("src/utils/helpers.py") == "python"
    assert languages.get("src/utils/other.ts") == "typescript"


# ---------------------------------------------------------------------------
# Tests: load_dataset_entry — error cases
# ---------------------------------------------------------------------------


def test_load_dataset_entry_missing_metadata_raises(tmp_path: Path) -> None:
    entry_dir = tmp_path / "bad-entry"
    entry_dir.mkdir()
    (entry_dir / "diff.patch").write_text("+ change\n", encoding="utf-8")
    with pytest.raises(FileNotFoundError, match="metadata.json"):
        load_dataset_entry(entry_dir)


def test_load_dataset_entry_missing_diff_raises(tmp_path: Path) -> None:
    entry_dir = tmp_path / "bad-entry"
    entry_dir.mkdir()
    (entry_dir / "metadata.json").write_text('{"pr_id":"x","known_bugs":[]}', encoding="utf-8")
    with pytest.raises(FileNotFoundError, match="diff.patch"):
        load_dataset_entry(entry_dir)
