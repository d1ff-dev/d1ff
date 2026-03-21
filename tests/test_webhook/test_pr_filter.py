"""Tests for pr_filter — draft skip and large-PR detection logic (FR18, NFR3)."""

from d1ff.webhook.pr_filter import (
    LARGE_PR_LINES_THRESHOLD,
    is_draft_pr,
    is_large_pr,
    truncate_diff,
)


def test_is_draft_pr_true() -> None:
    """is_draft_pr returns True for draft PRs."""
    assert is_draft_pr(True) is True


def test_is_draft_pr_false() -> None:
    """is_draft_pr returns False for non-draft PRs."""
    assert is_draft_pr(False) is False


def test_is_large_pr_over_threshold() -> None:
    """is_large_pr returns True when lines_changed exceeds the threshold."""
    assert is_large_pr(2001) is True


def test_is_large_pr_at_threshold() -> None:
    """is_large_pr returns False when lines_changed equals the threshold (strictly greater than)."""
    assert is_large_pr(2000) is False


def test_is_large_pr_under_threshold() -> None:
    """is_large_pr returns False when lines_changed is well under the threshold."""
    assert is_large_pr(500) is False


def test_truncate_diff_truncates_to_max_lines() -> None:
    """truncate_diff truncates a diff with 3000 lines to exactly 2000 lines."""
    diff = "\n".join(f"+line {i}" for i in range(3000)) + "\n"
    result = truncate_diff(diff, 2000)
    assert len(result.splitlines()) == 2000


def test_truncate_diff_short_diff_unchanged() -> None:
    """truncate_diff returns the original diff when it has fewer lines than max_lines."""
    diff = "\n".join(f"+line {i}" for i in range(500)) + "\n"
    result = truncate_diff(diff, 2000)
    assert result == diff


def test_truncate_diff_empty_string() -> None:
    """truncate_diff handles empty string without crashing."""
    assert truncate_diff("") == ""


def test_large_pr_threshold_value() -> None:
    """LARGE_PR_LINES_THRESHOLD is set to 2000."""
    assert LARGE_PR_LINES_THRESHOLD == 2000
