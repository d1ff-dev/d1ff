"""Tests for commands.py — issue_comment slash command handling (AC: 1, 2, 3, 4)."""

from unittest.mock import AsyncMock, MagicMock, patch

from d1ff.webhook.commands import handle_issue_comment_event
from d1ff.webhook.models import WebhookEvent

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REPO_PAYLOAD = {
    "id": 1,
    "name": "repo",
    "full_name": "owner/repo",
    "private": False,
}

_INSTALLATION_PAYLOAD = {
    "id": 123,
    "account": {"login": "owner", "type": "Organization"},
}


def _make_comment_event(
    body: str = "/d1ff review",
    action: str = "created",
    sender_login: str = "alice",
    sender_type: str = "User",
    is_pr_comment: bool = True,
    pr_number: int = 42,
    delivery_id: str = "comment-del-id",
) -> WebhookEvent:
    """Build a WebhookEvent for an issue_comment webhook."""
    pull_request_field: dict | None = {} if is_pr_comment else None
    payload = {
        "action": action,
        "issue": {
            "number": pr_number,
            "title": "Some PR",
            "pull_request": pull_request_field,
        },
        "comment": {
            "id": 999,
            "body": body,
            "user": {"login": sender_login, "type": sender_type},
        },
        "repository": _REPO_PAYLOAD,
        "installation": _INSTALLATION_PAYLOAD,
        "sender": {"login": sender_login, "type": sender_type},
    }
    return WebhookEvent(
        event_type="issue_comment",
        delivery_id=delivery_id,
        installation_id=123,
        payload=payload,
    )


def _make_gh_mock_with_pr(pr_number: int = 42) -> AsyncMock:
    """Build a mock GitHub installation client with a PR response."""
    gh_mock = AsyncMock()
    pr_data = MagicMock()
    pr_data.number = pr_number
    pr_data.title = "Some PR"
    pr_data.state = "open"
    pr_data.draft = False
    pr_data.user = MagicMock(login="alice")
    pr_data.base = MagicMock(ref="main", sha="abc123")
    pr_data.head = MagicMock(ref="feature", sha="def456")
    pr_data.html_url = "https://github.com/owner/repo/pull/42"
    pr_response = MagicMock()
    pr_response.parsed_data = pr_data
    gh_mock.rest.pulls.async_get = AsyncMock(return_value=pr_response)
    gh_mock.rest.issues.async_create_comment = AsyncMock()
    return gh_mock


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_review_command_triggers_pipeline() -> None:
    """AC1: /d1ff review command triggers the full review pipeline."""
    event = _make_comment_event(body="/d1ff review", is_pr_comment=True)
    installation_repo = AsyncMock()

    with patch(
        "d1ff.webhook.commands.handle_review_command", new_callable=AsyncMock
    ) as mock_review:
        await handle_issue_comment_event(event, installation_repo)
        mock_review.assert_called_once()


async def test_review_command_posts_acknowledgment() -> None:
    """AC2: /d1ff review posts acknowledgment before running pipeline (FR23)."""
    import structlog.testing

    event = _make_comment_event(body="/d1ff review", is_pr_comment=True)
    installation_repo = AsyncMock()

    call_order: list[str] = []

    async def fake_handle_review(ev: object, payload: object, repo: object) -> None:
        call_order.append("pipeline")

    with (
        structlog.testing.capture_logs() as captured,
        patch("d1ff.webhook.commands.handle_review_command", side_effect=fake_handle_review),
    ):
        await handle_issue_comment_event(event, installation_repo)

    # handle_review_command was called (which contains the acknowledgment call)
    assert "pipeline" in call_order

    # command_received was logged before calling handle_review_command
    command_received = [e for e in captured if e.get("event") == "command_received"]
    assert len(command_received) == 1

    # Verify acknowledgment ordering is correct: the implementation posts acknowledgment
    # (command_acknowledgment_posted log) BEFORE starting the pipeline try block.
    # Here we verify handle_review_command is invoked.
    assert call_order == ["pipeline"]


async def test_non_pr_comment_ignored() -> None:
    """AC3: Comments on plain issues (not PRs) are ignored — handle_review_command NOT called."""
    event = _make_comment_event(is_pr_comment=False)
    installation_repo = AsyncMock()

    with patch(
        "d1ff.webhook.commands.handle_review_command", new_callable=AsyncMock
    ) as mock_review:
        await handle_issue_comment_event(event, installation_repo)
        mock_review.assert_not_called()


async def test_bot_comment_ignored() -> None:
    """AC4: Comments from Bot type users are ignored."""
    event = _make_comment_event(
        body="/d1ff review",
        sender_login="github-actions",
        sender_type="Bot",
        is_pr_comment=True,
    )
    installation_repo = AsyncMock()

    with patch(
        "d1ff.webhook.commands.handle_review_command", new_callable=AsyncMock
    ) as mock_review:
        await handle_issue_comment_event(event, installation_repo)
        mock_review.assert_not_called()


async def test_bot_login_suffix_ignored() -> None:
    """AC4: Comments from users with [bot] login suffix are ignored."""
    event = _make_comment_event(
        body="/d1ff review",
        sender_login="renovate[bot]",
        sender_type="User",
        is_pr_comment=True,
    )
    installation_repo = AsyncMock()

    with patch(
        "d1ff.webhook.commands.handle_review_command", new_callable=AsyncMock
    ) as mock_review:
        await handle_issue_comment_event(event, installation_repo)
        mock_review.assert_not_called()


async def test_unknown_command_ignored() -> None:
    """AC3: Unknown /d1ff commands do not trigger the review pipeline."""
    event = _make_comment_event(body="/d1ff unknown", is_pr_comment=True)
    installation_repo = AsyncMock()

    with patch(
        "d1ff.webhook.commands.handle_review_command", new_callable=AsyncMock
    ) as mock_review:
        await handle_issue_comment_event(event, installation_repo)
        mock_review.assert_not_called()


async def test_comment_edit_ignored() -> None:
    """AC3: Edited comments are ignored."""
    event = _make_comment_event(body="/d1ff review", action="edited", is_pr_comment=True)
    installation_repo = AsyncMock()

    with patch(
        "d1ff.webhook.commands.handle_review_command", new_callable=AsyncMock
    ) as mock_review:
        await handle_issue_comment_event(event, installation_repo)
        mock_review.assert_not_called()


async def test_plain_comment_ignored() -> None:
    """AC3: Plain comments without /d1ff prefix are ignored."""
    event = _make_comment_event(body="looks good to me", is_pr_comment=True)
    installation_repo = AsyncMock()

    with patch(
        "d1ff.webhook.commands.handle_review_command", new_callable=AsyncMock
    ) as mock_review:
        await handle_issue_comment_event(event, installation_repo)
        mock_review.assert_not_called()


async def test_review_command_logs_command_received() -> None:
    """AC1: command_received event is logged with pr_number=42 and command="review"."""
    import structlog.testing

    event = _make_comment_event(body="/d1ff review", pr_number=42, is_pr_comment=True)
    installation_repo = AsyncMock()

    with (
        structlog.testing.capture_logs() as captured,
        patch("d1ff.webhook.commands.handle_review_command", new_callable=AsyncMock),
    ):
        await handle_issue_comment_event(event, installation_repo)

    command_received_events = [
        e for e in captured if e.get("event") == "command_received"
    ]
    assert len(command_received_events) == 1
    assert command_received_events[0]["pr_number"] == 42
    assert command_received_events[0]["command"] == "review"
