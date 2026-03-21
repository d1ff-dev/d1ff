"""Tests for command_parser — pure sync slash command parsing logic."""

from d1ff.webhook.command_parser import is_bot_user, parse_command


def test_parse_review_command() -> None:
    assert parse_command("/d1ff review") == "review"


def test_parse_review_command_with_trailing_text() -> None:
    assert parse_command("/d1ff review please") == "review"


def test_parse_review_command_with_leading_whitespace() -> None:
    assert parse_command("  /d1ff review  ") == "review"


def test_parse_unknown_command_returns_none() -> None:
    assert parse_command("/d1ff unknown") is None


def test_parse_no_prefix_returns_none() -> None:
    assert parse_command("hello world") is None


def test_parse_partial_prefix_returns_none() -> None:
    assert parse_command("/d1f review") is None


def test_parse_empty_body_returns_none() -> None:
    assert parse_command("") is None


def test_parse_prefix_only_returns_none() -> None:
    assert parse_command("/d1ff") is None


def test_is_bot_user_type_bot() -> None:
    assert is_bot_user("github-actions", "Bot") is True


def test_is_bot_user_login_suffix() -> None:
    assert is_bot_user("dependabot[bot]", "User") is True


def test_is_bot_user_regular_user() -> None:
    assert is_bot_user("alice", "User") is False


def test_parse_no_space_after_prefix_returns_none() -> None:
    """Reject /d1ffreview (no space between prefix and command)."""
    assert parse_command("/d1ffreview") is None


def test_parse_pause_command() -> None:
    assert parse_command("/d1ff pause") == "pause"


def test_parse_resume_command() -> None:
    assert parse_command("/d1ff resume") == "resume"


def test_parse_skip_command() -> None:
    assert parse_command("/d1ff skip") == "skip"
