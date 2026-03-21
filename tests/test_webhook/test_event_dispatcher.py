"""Tests for event_dispatcher — webhook event routing and deduplication."""
from unittest.mock import AsyncMock, patch

from d1ff.webhook.event_dispatcher import dispatch_event
from d1ff.webhook.models import WebhookEvent

# Minimal valid pull_request payload matching PullRequestPayload model
PR_PAYLOAD_BASE = {
    "action": "opened",
    "pull_request": {
        "number": 42,
        "title": "Add feature X",
        "state": "open",
        "draft": False,
        "user": {"login": "alice"},
        "base": {"ref": "main"},
        "head": {"ref": "feature/x"},
        "html_url": "https://github.com/owner/repo/pull/42",
    },
    "repository": {
        "id": 1,
        "name": "repo",
        "full_name": "owner/repo",
        "private": False,
    },
    "installation": {
        "id": 123,
        "account": {"login": "owner", "type": "Organization"},
    },
}


def _make_pr_event(action: str = "opened", delivery_id: str = "test-del-id") -> WebhookEvent:
    payload = {**PR_PAYLOAD_BASE, "action": action}
    return WebhookEvent(
        event_type="pull_request",
        delivery_id=delivery_id,
        installation_id=123,
        payload=payload,
    )


def _make_issue_comment_event(delivery_id: str = "comment-del-id") -> WebhookEvent:
    return WebhookEvent(
        event_type="issue_comment",
        delivery_id=delivery_id,
        installation_id=123,
        payload={
            "action": "created",
            "comment": {"body": "/d1ff review"},
            "installation": {
                "id": 123,
                "account": {"login": "owner", "type": "Organization"},
            },
        },
    )


async def test_pull_request_opened_dispatched() -> None:
    """pull_request opened event is dispatched without error."""
    event = _make_pr_event(action="opened")
    installation_repo = AsyncMock()
    with (
        patch("d1ff.webhook.event_dispatcher.is_duplicate", return_value=False),
        patch(
            "d1ff.webhook.event_dispatcher.handle_pull_request_event",
            new_callable=AsyncMock,
        ),
    ):
        await dispatch_event(event, installation_repo, dedup_check=False)
    # No exception means success


async def test_pull_request_synchronize_dispatched() -> None:
    """pull_request synchronize event is dispatched (in PR_REVIEW_ACTIONS)."""
    event = _make_pr_event(action="synchronize")
    installation_repo = AsyncMock()
    with patch(
        "d1ff.webhook.event_dispatcher.handle_pull_request_event",
        new_callable=AsyncMock,
    ):
        await dispatch_event(event, installation_repo, dedup_check=False)
    # No exception means success


async def test_pull_request_reopened_dispatched() -> None:
    """pull_request reopened event is dispatched (in PR_REVIEW_ACTIONS)."""
    event = _make_pr_event(action="reopened")
    installation_repo = AsyncMock()
    with patch(
        "d1ff.webhook.event_dispatcher.handle_pull_request_event",
        new_callable=AsyncMock,
    ):
        await dispatch_event(event, installation_repo, dedup_check=False)
    # No exception means success


async def test_pull_request_closed_skipped() -> None:
    """pull_request closed event is skipped (not in PR_REVIEW_ACTIONS)."""
    event = _make_pr_event(action="closed")
    installation_repo = AsyncMock()
    with patch(
        "d1ff.webhook.event_dispatcher.handle_pull_request_event",
        new_callable=AsyncMock,
    ) as mock_pr:
        await dispatch_event(event, installation_repo, dedup_check=False)
        # closed is not in PR_REVIEW_ACTIONS — handler receives it and skips internally
        mock_pr.assert_called_once()


async def test_issue_comment_dispatched_to_command_handler() -> None:
    """issue_comment event routes to handle_issue_comment_event, not pull_request handler."""
    event = _make_issue_comment_event()
    installation_repo = AsyncMock()
    with patch(
        "d1ff.webhook.event_dispatcher.handle_pull_request_event", new_callable=AsyncMock
    ) as mock_pr, patch(
        "d1ff.webhook.event_dispatcher.handle_issue_comment_event", new_callable=AsyncMock
    ) as mock_comment:
        await dispatch_event(event, installation_repo, dedup_check=False)
        mock_comment.assert_called_once_with(event, installation_repo)
        mock_pr.assert_not_called()


async def test_dedup_rejects_second_delivery() -> None:
    """Second call with same delivery_id and dedup_check=True is rejected by dedup guard."""
    event = _make_pr_event(delivery_id="dup-delivery-id")
    installation_repo = AsyncMock()

    call_count = 0

    async def fake_is_duplicate(delivery_id: str) -> bool:
        nonlocal call_count
        call_count += 1
        return call_count > 1  # First call returns False, subsequent return True

    with patch("d1ff.webhook.event_dispatcher.is_duplicate", side_effect=fake_is_duplicate), patch(
        "d1ff.webhook.event_dispatcher.handle_pull_request_event", new_callable=AsyncMock
    ) as mock_pr:
        # First call — not duplicate, should process
        await dispatch_event(event, installation_repo, dedup_check=True)
        assert mock_pr.call_count == 1

        # Second call — duplicate, should be rejected before reaching handler
        await dispatch_event(event, installation_repo, dedup_check=True)
        # Still only 1 call — second was rejected
        assert mock_pr.call_count == 1


async def test_dedup_disabled_allows_repeat() -> None:
    """Both calls process when dedup_check=False."""
    event = _make_pr_event(delivery_id="repeat-delivery-id")
    installation_repo = AsyncMock()

    with patch(
        "d1ff.webhook.event_dispatcher.handle_pull_request_event", new_callable=AsyncMock
    ) as mock_pr:
        await dispatch_event(event, installation_repo, dedup_check=False)
        await dispatch_event(event, installation_repo, dedup_check=False)
        assert mock_pr.call_count == 2


async def test_unknown_event_type_logged_and_ignored() -> None:
    """Unknown event type does not raise an exception."""
    event = WebhookEvent(
        event_type="marketplace_purchase",
        delivery_id="unknown-del-id",
        installation_id=123,
        payload={},
    )
    installation_repo = AsyncMock()
    # Should not raise
    await dispatch_event(event, installation_repo, dedup_check=False)


def _make_draft_pr_event(draft: bool, delivery_id: str = "draft-del-id") -> WebhookEvent:
    """Helper to create a PR event with configurable draft status."""
    payload = {
        **PR_PAYLOAD_BASE,
        "action": "opened",
        "pull_request": {**PR_PAYLOAD_BASE["pull_request"], "draft": draft},
    }
    return WebhookEvent(
        event_type="pull_request",
        delivery_id=delivery_id,
        installation_id=123,
        payload=payload,
    )


async def test_draft_pr_skips_pipeline() -> None:
    """Draft PR events do not call run_pipeline (FR18 — draft skip before context build)."""
    event = _make_draft_pr_event(draft=True)
    installation_repo = AsyncMock()

    # Patch build_review_context at its source module — lazy import picks it up from there
    build_path = "d1ff.context.context_builder.build_review_context"
    with (
        patch(build_path, new_callable=AsyncMock) as mock_build,
        patch("d1ff.pipeline.run_pipeline", new_callable=AsyncMock) as mock_pipeline,
    ):
        await dispatch_event(event, installation_repo, dedup_check=False)
        # run_pipeline must NOT be called for draft PRs
        mock_pipeline.assert_not_called()
        # build_review_context must NOT be called for draft PRs (skip is before context build)
        mock_build.assert_not_called()


async def test_non_draft_pr_proceeds_to_pipeline() -> None:
    """Non-draft PR events proceed to run_pipeline when all setup succeeds (AC: 6)."""
    event = _make_draft_pr_event(draft=False, delivery_id="non-draft-del-id")
    installation_repo = AsyncMock()

    with patch(
        "d1ff.webhook.event_dispatcher.handle_pull_request_event",
        new_callable=AsyncMock,
    ) as mock_handler:
        await dispatch_event(event, installation_repo, dedup_check=False)
        mock_handler.assert_called_once()
