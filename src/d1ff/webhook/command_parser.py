"""Parse /d1ff slash commands from GitHub issue_comment webhook payloads."""

from __future__ import annotations

COMMAND_PREFIX = "/d1ff"

# Recognized commands
COMMAND_REVIEW = "review"
COMMAND_PAUSE = "pause"
COMMAND_RESUME = "resume"
COMMAND_SKIP = "skip"

RECOGNIZED_COMMANDS: frozenset[str] = frozenset({
    COMMAND_REVIEW,
    COMMAND_PAUSE,
    COMMAND_RESUME,
    COMMAND_SKIP,
})


def parse_command(comment_body: str) -> str | None:
    """Extract the /d1ff command from a comment body.

    Returns the command name (e.g., "review") or None if no recognized command found.
    The command must start with "/d1ff " followed by a command name.
    """
    stripped = comment_body.strip()
    if not stripped.startswith(COMMAND_PREFIX):
        return None
    after_prefix = stripped[len(COMMAND_PREFIX):]
    # The prefix must be followed by whitespace (or end of string) — reject "/d1ffreview"
    if after_prefix and not after_prefix[0].isspace():
        return None
    tokens = after_prefix.split()
    if not tokens:
        return None
    command = tokens[0].lower()
    if command in RECOGNIZED_COMMANDS:
        return command
    return None


def is_bot_user(sender_login: str, sender_type: str) -> bool:
    """Return True if the comment was posted by a bot (prevents infinite loops).

    GitHub bots have user_type="Bot" or logins ending with "[bot]".
    """
    return sender_type == "Bot" or sender_login.endswith("[bot]")
