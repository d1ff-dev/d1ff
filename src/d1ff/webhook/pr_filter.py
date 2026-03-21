"""PR filtering logic: draft skip and large-PR detection (FR18, NFR3)."""

# Large PR threshold (NFR3)
LARGE_PR_LINES_THRESHOLD = 2000


def is_draft_pr(draft: bool) -> bool:
    """Return True if the PR is in draft state (FR18)."""
    return draft


def is_large_pr(lines_changed: int) -> bool:
    """Return True if PR exceeds the large-PR threshold (NFR3)."""
    return lines_changed > LARGE_PR_LINES_THRESHOLD


def truncate_diff(diff: str, max_lines: int = LARGE_PR_LINES_THRESHOLD) -> str:
    """Truncate a unified diff to max_lines lines.

    Preserves the first max_lines lines of the diff for pipeline consumption.
    """
    lines = diff.splitlines(keepends=True)
    return "".join(lines[:max_lines])
