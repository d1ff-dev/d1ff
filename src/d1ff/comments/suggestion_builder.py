"""Pure string helper for building GitHub suggestion blocks (FR29).

This module is a standalone utility with no I/O, no models, no side effects.
It may be used by review_poster.py, future stories, or any caller that needs
to construct suggestion block strings.
"""


def build_suggestion_block(suggestion_code: str) -> str:
    """Wrap replacement code in a GitHub suggestion block.

    Returns the markdown string:
        ```suggestion
        {suggestion_code}
        ```

    Args:
        suggestion_code: The replacement code to wrap. May be empty or multiline.

    Returns:
        A GitHub-flavoured markdown suggestion block string.
    """
    return f"```suggestion\n{suggestion_code}\n```"
