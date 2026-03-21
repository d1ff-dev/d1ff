"""Tests for context models — Pydantic contracts (AC: 5)."""

import pytest
from pydantic import ValidationError

from d1ff.context.models import FileContext, PRMetadata, ReviewContext


def _make_pr_metadata(**overrides) -> PRMetadata:  # type: ignore[no-untyped-def]
    defaults = {
        "number": 42,
        "title": "Add feature X",
        "author": "alice",
        "base_branch": "main",
        "head_branch": "feature/x",
        "html_url": "https://github.com/owner/repo/pull/42",
        "draft": False,
    }
    defaults.update(overrides)
    return PRMetadata(**defaults)


def _make_review_context(**overrides) -> ReviewContext:  # type: ignore[no-untyped-def]
    defaults = {
        "installation_id": 123,
        "pr_metadata": _make_pr_metadata(),
        "diff": "diff text",
        "changed_files": [],
    }
    defaults.update(overrides)
    return ReviewContext(**defaults)


def test_review_context_is_frozen() -> None:
    """ReviewContext raises ValidationError on field mutation attempt."""
    ctx = _make_review_context()
    with pytest.raises((ValidationError, TypeError)):
        ctx.diff = "mutated"  # type: ignore[misc]


def test_file_context_is_frozen() -> None:
    """FileContext raises ValidationError on field mutation attempt."""
    fc = FileContext(path="src/foo.py", content="hello", language="python")
    with pytest.raises((ValidationError, TypeError)):
        fc.content = "mutated"  # type: ignore[misc]


def test_review_context_default_related_files_empty() -> None:
    """ReviewContext.related_files defaults to empty list when not provided."""
    ctx = _make_review_context()
    assert ctx.related_files == []


def test_pr_metadata_fields_present() -> None:
    """PRMetadata contains all required fields with correct values."""
    meta = _make_pr_metadata()
    assert meta.number == 42
    assert meta.title == "Add feature X"
    assert meta.author == "alice"
    assert meta.base_branch == "main"
    assert meta.head_branch == "feature/x"
    assert meta.html_url == "https://github.com/owner/repo/pull/42"
    assert meta.draft is False


def test_file_context_language_none_by_default() -> None:
    """FileContext.language defaults to None when not provided."""
    fc = FileContext(path="Makefile", content="build:")
    assert fc.language is None
