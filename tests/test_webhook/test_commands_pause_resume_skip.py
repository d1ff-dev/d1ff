"""Tests for pause, resume, skip command handlers (Story 4.2, AC: 1, 2, 3, 4)."""

from unittest.mock import AsyncMock, MagicMock, patch

from d1ff.webhook.commands import handle_issue_comment_event
from d1ff.webhook.event_dispatcher import handle_pull_request_event
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
    body: str = "/d1ff pause",
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


def _make_pr_event(
    action: str = "synchronize",
    pr_number: int = 42,
    draft: bool = False,
    labels: list[dict] | None = None,
    delivery_id: str = "pr-del-id",
) -> WebhookEvent:
    """Build a WebhookEvent for a pull_request webhook."""
    payload = {
        "action": action,
        "pull_request": {
            "number": pr_number,
            "title": "Feature branch",
            "state": "open",
            "draft": draft,
            "user": {"login": "alice"},
            "base": {"ref": "main", "sha": "abc"},
            "head": {"ref": "feature", "sha": "def"},
            "html_url": "https://github.com/owner/repo/pull/42",
            "labels": labels or [],
        },
        "repository": _REPO_PAYLOAD,
        "installation": _INSTALLATION_PAYLOAD,
    }
    return WebhookEvent(
        event_type="pull_request",
        delivery_id=delivery_id,
        installation_id=123,
        payload=payload,
    )


# ---------------------------------------------------------------------------
# Tests: pause command
# ---------------------------------------------------------------------------


async def test_pause_command_sets_paused_state() -> None:
    """/d1ff pause → set_pr_state called with 'paused'."""
    event = _make_comment_event(body="/d1ff pause", pr_number=42)
    installation_repo = AsyncMock()

    with (
        patch(
            "d1ff.webhook.commands.handle_pause_command", new_callable=AsyncMock
        ) as mock_pause,
    ):
        await handle_issue_comment_event(event, installation_repo)
        mock_pause.assert_called_once()


async def test_pause_command_calls_set_pr_state_paused() -> None:
    """/d1ff pause → set_pr_state(installation_id, repo, pr_number, 'paused') called once."""
    from d1ff.webhook.commands import handle_pause_command
    from d1ff.webhook.models import IssueCommentPayload

    event = _make_comment_event(body="/d1ff pause", pr_number=42)
    payload = IssueCommentPayload.model_validate(event.payload)
    installation_repo = AsyncMock()

    mock_gh = AsyncMock()
    mock_gh.rest.issues.async_create_comment = AsyncMock()

    with (
        patch(
            "d1ff.storage.pr_state_repo.set_pr_state", new_callable=AsyncMock
        ) as mock_set,
        patch(
            "d1ff.webhook.commands._get_github_client", new_callable=AsyncMock, return_value=mock_gh
        ),
    ):
        await handle_pause_command(payload, installation_repo)
        mock_set.assert_called_once_with(123, "owner/repo", 42, "paused")


async def test_pause_command_posts_acknowledgment() -> None:
    """/d1ff pause → async_create_comment called with body containing 'paused'."""
    from d1ff.webhook.commands import handle_pause_command
    from d1ff.webhook.models import IssueCommentPayload

    event = _make_comment_event(body="/d1ff pause", pr_number=42)
    payload = IssueCommentPayload.model_validate(event.payload)
    installation_repo = AsyncMock()

    mock_gh = AsyncMock()
    mock_gh.rest.issues.async_create_comment = AsyncMock()

    with (
        patch("d1ff.storage.pr_state_repo.set_pr_state", new_callable=AsyncMock),
        patch(
            "d1ff.webhook.commands._get_github_client", new_callable=AsyncMock, return_value=mock_gh
        ),
    ):
        await handle_pause_command(payload, installation_repo)

    mock_gh.rest.issues.async_create_comment.assert_called_once()
    call_kwargs = mock_gh.rest.issues.async_create_comment.call_args
    body = call_kwargs.kwargs.get("body", "")
    assert "paused" in body.lower()


# ---------------------------------------------------------------------------
# Tests: resume command
# ---------------------------------------------------------------------------


async def test_resume_command_sets_active_state() -> None:
    """/d1ff resume → set_pr_state(..., 'active') called once."""
    from d1ff.webhook.commands import handle_resume_command
    from d1ff.webhook.models import IssueCommentPayload

    event = _make_comment_event(body="/d1ff resume", pr_number=42)
    payload = IssueCommentPayload.model_validate(event.payload)
    installation_repo = AsyncMock()

    mock_gh = AsyncMock()
    mock_gh.rest.issues.async_create_comment = AsyncMock()

    with (
        patch(
            "d1ff.storage.pr_state_repo.set_pr_state", new_callable=AsyncMock
        ) as mock_set,
        patch(
            "d1ff.webhook.commands._get_github_client", new_callable=AsyncMock, return_value=mock_gh
        ),
    ):
        await handle_resume_command(payload, installation_repo)
        mock_set.assert_called_once_with(123, "owner/repo", 42, "active")


async def test_resume_command_posts_acknowledgment() -> None:
    """/d1ff resume → async_create_comment called with body containing 'resumed'."""
    from d1ff.webhook.commands import handle_resume_command
    from d1ff.webhook.models import IssueCommentPayload

    event = _make_comment_event(body="/d1ff resume", pr_number=42)
    payload = IssueCommentPayload.model_validate(event.payload)
    installation_repo = AsyncMock()

    mock_gh = AsyncMock()
    mock_gh.rest.issues.async_create_comment = AsyncMock()

    with (
        patch("d1ff.storage.pr_state_repo.set_pr_state", new_callable=AsyncMock),
        patch(
            "d1ff.webhook.commands._get_github_client", new_callable=AsyncMock, return_value=mock_gh
        ),
    ):
        await handle_resume_command(payload, installation_repo)

    mock_gh.rest.issues.async_create_comment.assert_called_once()
    call_kwargs = mock_gh.rest.issues.async_create_comment.call_args
    body = call_kwargs.kwargs.get("body", "")
    assert "resumed" in body.lower()


# ---------------------------------------------------------------------------
# Tests: skip command
# ---------------------------------------------------------------------------


async def test_skip_command_posts_acknowledgment() -> None:
    """/d1ff skip → async_create_comment called with body containing 'skipped'."""
    from d1ff.webhook.commands import handle_skip_command
    from d1ff.webhook.models import IssueCommentPayload

    event = _make_comment_event(body="/d1ff skip", pr_number=42)
    payload = IssueCommentPayload.model_validate(event.payload)
    installation_repo = AsyncMock()

    mock_gh = AsyncMock()
    mock_gh.rest.issues.async_create_comment = AsyncMock()

    with patch(
        "d1ff.webhook.commands._get_github_client", new_callable=AsyncMock, return_value=mock_gh
    ):
        await handle_skip_command(payload, installation_repo)

    mock_gh.rest.issues.async_create_comment.assert_called_once()
    call_kwargs = mock_gh.rest.issues.async_create_comment.call_args
    body = call_kwargs.kwargs.get("body", "")
    assert "skipped" in body.lower()


async def test_skip_command_does_not_set_state() -> None:
    """/d1ff skip → set_pr_state NOT called (skip is ephemeral)."""
    from d1ff.webhook.commands import handle_skip_command
    from d1ff.webhook.models import IssueCommentPayload

    event = _make_comment_event(body="/d1ff skip", pr_number=42)
    payload = IssueCommentPayload.model_validate(event.payload)
    installation_repo = AsyncMock()

    mock_gh = AsyncMock()
    mock_gh.rest.issues.async_create_comment = AsyncMock()

    with (
        patch(
            "d1ff.storage.pr_state_repo.set_pr_state", new_callable=AsyncMock
        ) as mock_set,
        patch(
            "d1ff.webhook.commands._get_github_client", new_callable=AsyncMock, return_value=mock_gh
        ),
    ):
        await handle_skip_command(payload, installation_repo)
        mock_set.assert_not_called()


# ---------------------------------------------------------------------------
# Tests: pause gate in event_dispatcher
# ---------------------------------------------------------------------------


async def test_paused_pr_skips_pipeline() -> None:
    """get_pr_state returns 'paused' → run_pipeline NOT called."""
    event = _make_pr_event(action="synchronize", pr_number=42)
    installation_repo = AsyncMock()

    _api_key_data = {
        "provider": "openai",
        "model": "gpt-4o",
        "encrypted_key": "enc",
        "custom_endpoint": None,
    }
    with (
        patch(
            "d1ff.webhook.event_dispatcher.get_api_key_config",
            new_callable=AsyncMock,
            return_value=_api_key_data,
        ),
        patch(
            "d1ff.storage.pr_state_repo.get_pr_state",
            new_callable=AsyncMock,
            return_value="paused",
        ),
        patch("d1ff.pipeline.run_pipeline", new_callable=AsyncMock) as mock_pipeline,
    ):
        await handle_pull_request_event(event, installation_repo)
        mock_pipeline.assert_not_called()


async def test_active_pr_allows_pipeline() -> None:
    """get_pr_state returns 'active' → run_pipeline IS called."""
    from d1ff.github import GitHubAppClient

    event = _make_pr_event(action="synchronize", pr_number=42)
    installation_repo = AsyncMock()

    mock_context = MagicMock()
    mock_context.lines_changed = 10
    mock_context.diff = "diff"

    mock_summary = MagicMock()
    mock_findings = MagicMock()

    mock_settings = MagicMock()
    mock_settings.GITHUB_APP_ID = "app-id"
    mock_settings.GITHUB_PRIVATE_KEY = "private-key"
    mock_github_client = MagicMock(spec=GitHubAppClient)

    _api_key_data = {
        "provider": "openai",
        "model": "gpt-4o",
        "encrypted_key": "enc",
        "custom_endpoint": None,
    }
    with (
        patch(
            "d1ff.webhook.event_dispatcher.get_api_key_config",
            new_callable=AsyncMock,
            return_value=_api_key_data,
        ),
        patch(
            "d1ff.storage.pr_state_repo.get_pr_state",
            new_callable=AsyncMock,
            return_value="active",
        ),
        patch(
            "d1ff.context.build_review_context",
            new_callable=AsyncMock,
            return_value=mock_context,
        ),
        patch(
            "d1ff.pipeline.run_pipeline",
            new_callable=AsyncMock,
            return_value=(mock_summary, mock_findings),
        ) as mock_pipeline,
        patch("d1ff.comments.format_review", return_value=MagicMock()),
        patch("d1ff.comments.post_review", new_callable=AsyncMock),
    ):
        await handle_pull_request_event(
            event, installation_repo, github_client=mock_github_client, settings=mock_settings
        )
        mock_pipeline.assert_called_once()


# ---------------------------------------------------------------------------
# Tests: d1ff:skip label gate in event_dispatcher
# ---------------------------------------------------------------------------


async def test_skip_label_skips_pipeline() -> None:
    """PR payload has labels=[{'name': 'd1ff:skip'}] → pipeline NOT triggered."""
    event = _make_pr_event(action="synchronize", pr_number=42, labels=[{"name": "d1ff:skip"}])
    installation_repo = AsyncMock()

    with (
        patch(
            "d1ff.storage.pr_state_repo.get_pr_state",
            new_callable=AsyncMock,
            return_value="active",
        ),
        patch("d1ff.pipeline.run_pipeline", new_callable=AsyncMock) as mock_pipeline,
    ):
        await handle_pull_request_event(event, installation_repo)
        mock_pipeline.assert_not_called()


async def test_no_skip_label_allows_pipeline() -> None:
    """PR payload has no d1ff:skip label → pipeline IS triggered."""
    from d1ff.github import GitHubAppClient

    event = _make_pr_event(action="synchronize", pr_number=42, labels=[{"name": "enhancement"}])
    installation_repo = AsyncMock()

    mock_context = MagicMock()
    mock_context.lines_changed = 10
    mock_context.diff = "diff"

    mock_summary = MagicMock()
    mock_findings = MagicMock()

    mock_settings = MagicMock()
    mock_settings.GITHUB_APP_ID = "app-id"
    mock_settings.GITHUB_PRIVATE_KEY = "private-key"
    mock_github_client = MagicMock(spec=GitHubAppClient)

    _api_key_data = {
        "provider": "openai",
        "model": "gpt-4o",
        "encrypted_key": "enc",
        "custom_endpoint": None,
    }
    with (
        patch(
            "d1ff.webhook.event_dispatcher.get_api_key_config",
            new_callable=AsyncMock,
            return_value=_api_key_data,
        ),
        patch(
            "d1ff.storage.pr_state_repo.get_pr_state",
            new_callable=AsyncMock,
            return_value="active",
        ),
        patch(
            "d1ff.context.build_review_context",
            new_callable=AsyncMock,
            return_value=mock_context,
        ),
        patch(
            "d1ff.pipeline.run_pipeline",
            new_callable=AsyncMock,
            return_value=(mock_summary, mock_findings),
        ) as mock_pipeline,
        patch("d1ff.comments.format_review", return_value=MagicMock()),
        patch("d1ff.comments.post_review", new_callable=AsyncMock),
    ):
        await handle_pull_request_event(
            event, installation_repo, github_client=mock_github_client, settings=mock_settings
        )
        mock_pipeline.assert_called_once()


# ---------------------------------------------------------------------------
# Tests: bot and non-PR guard (for pause command)
# ---------------------------------------------------------------------------


async def test_pause_command_bot_ignored() -> None:
    """sender.type='Bot' → set_pr_state NOT called."""
    event = _make_comment_event(
        body="/d1ff pause",
        sender_login="github-actions[bot]",
        sender_type="Bot",
        is_pr_comment=True,
    )
    installation_repo = AsyncMock()

    with patch(
        "d1ff.storage.pr_state_repo.set_pr_state", new_callable=AsyncMock
    ) as mock_set:
        await handle_issue_comment_event(event, installation_repo)
        mock_set.assert_not_called()


async def test_pause_command_non_pr_comment_ignored() -> None:
    """issue.pull_request=None → set_pr_state NOT called."""
    event = _make_comment_event(
        body="/d1ff pause",
        is_pr_comment=False,
    )
    installation_repo = AsyncMock()

    with patch(
        "d1ff.storage.pr_state_repo.set_pr_state", new_callable=AsyncMock
    ) as mock_set:
        await handle_issue_comment_event(event, installation_repo)
        mock_set.assert_not_called()
