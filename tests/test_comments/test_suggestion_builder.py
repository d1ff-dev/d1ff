"""Tests for suggestion_builder.py — pure string helper for GitHub suggestion blocks (FR29).

All functions under test are pure sync with no I/O — no mocking, no asyncio markers needed.
"""

from __future__ import annotations

from d1ff.comments.suggestion_builder import build_suggestion_block


def test_build_suggestion_block_wraps_code() -> None:
    """Single-line code is wrapped in a suggestion block."""
    result = build_suggestion_block("return x + 1")

    assert "```suggestion\nreturn x + 1\n```" in result


def test_build_suggestion_block_multiline() -> None:
    """Multiline code string is preserved verbatim inside the block."""
    code = "x = 1\ny = 2\nreturn x + y"

    result = build_suggestion_block(code)

    assert result == "```suggestion\nx = 1\ny = 2\nreturn x + y\n```"


def test_build_suggestion_block_empty_string() -> None:
    """Empty string produces a valid (though empty) suggestion block."""
    result = build_suggestion_block("")

    assert result == "```suggestion\n\n```"
