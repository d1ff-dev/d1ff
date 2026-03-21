"""Tests for PR review comment reaction handler (AC: 1, FR38, FR39)."""

from unittest.mock import AsyncMock, MagicMock, patch

from d1ff.webhook.event_dispatcher import (
    dispatch_event,
    handle_pr_review_comment_reaction_event,
)
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

_PULL_REQUEST_PAYLOAD = {
    "number": 42,
    "title": "Add feature X",
    "state": "open",
    "draft": False,
    "user": {"login": "alice"},
    "base": {"ref": "main"},
    "head": {"ref": "feature/x"},
    "html_url": "https://github.com/owner/repo/pull/42",
}

_COMMENT_PAYLOAD = {
    "id": 9999,
    "body": "Consider using a list comprehension here.",
    "user": {"login": "bot", "type": "Bot"},
}


def _make_pr_review_comment_event(
    delivery_id: str = "rxn-del-id",
    action: str = "created",
) -> WebhookEvent:
    """Build a WebhookEvent for a pull_request_review_comment webhook."""
    return WebhookEvent(
        event_type="pull_request_review_comment",
        delivery_id=delivery_id,
        installation_id=123,
        payload={
            "action": action,
            "comment": _COMMENT_PAYLOAD,
            "pull_request": _PULL_REQUEST_PAYLOAD,
            "repository": _REPO_PAYLOAD,
            "installation": _INSTALLATION_PAYLOAD,
        },
    )


def _make_reaction(content: str) -> MagicMock:
    """Return a mock Reaction object with a .content attribute."""
    rxn = MagicMock()
    rxn.content = content
    return rxn


def _make_gh_mock(reactions: list) -> AsyncMock:
    """Return an AsyncMock GitHub client that returns the given reactions list."""
    gh = AsyncMock()
    resp = AsyncMock()
    resp.parsed_data = reactions
    gh.rest.reactions.async_list_for_pull_request_review_comment.return_value = resp
    return gh


def _make_settings_mock() -> MagicMock:
    """Return a minimal mock of AppSettings."""
    settings = MagicMock()
    settings.GITHUB_APP_ID = 1
    settings.GITHUB_PRIVATE_KEY = "fake-key"
    return settings


# ---------------------------------------------------------------------------
# Tests: handle_pr_review_comment_reaction_event
# ---------------------------------------------------------------------------


async def test_reaction_handler_records_thumbs_up() -> None:
    """Reactions list containing '+1' → record_reaction called once with reaction_type='+1'."""
    event = _make_pr_review_comment_event()
    gh = _make_gh_mock([_make_reaction("+1")])
    installation_repo = AsyncMock()

    with (
        patch(
            "d1ff.webhook.event_dispatcher.get_settings",
            return_value=_make_settings_mock(),
        ),
        patch(
            "d1ff.github.GitHubAppClient"
        ) as MockClient,
        patch(
            "d1ff.feedback.reaction_collector.record_reaction",
            new_callable=AsyncMock,
        ) as mock_record,
    ):
        mock_instance = AsyncMock()
        mock_instance.get_installation_client.return_value = gh
        MockClient.return_value = mock_instance

        await handle_pr_review_comment_reaction_event(event, installation_repo)

        mock_record.assert_called_once()
        call_args = mock_record.call_args[0][0]
        assert call_args.reaction_type == "+1"
        assert call_args.comment_id == 9999
        assert call_args.installation_id == 123


async def test_reaction_handler_records_thumbs_down() -> None:
    """Reactions list containing '-1' → record_reaction called once with reaction_type='-1'."""
    event = _make_pr_review_comment_event()
    gh = _make_gh_mock([_make_reaction("-1")])
    installation_repo = AsyncMock()

    with (
        patch(
            "d1ff.webhook.event_dispatcher.get_settings",
            return_value=_make_settings_mock(),
        ),
        patch(
            "d1ff.github.GitHubAppClient"
        ) as MockClient,
        patch(
            "d1ff.feedback.reaction_collector.record_reaction",
            new_callable=AsyncMock,
        ) as mock_record,
    ):
        mock_instance = AsyncMock()
        mock_instance.get_installation_client.return_value = gh
        MockClient.return_value = mock_instance

        await handle_pr_review_comment_reaction_event(event, installation_repo)

        mock_record.assert_called_once()
        call_args = mock_record.call_args[0][0]
        assert call_args.reaction_type == "-1"


async def test_reaction_handler_ignores_other_reactions() -> None:
    """Reactions 'heart' and 'rocket' → record_reaction NOT called."""
    event = _make_pr_review_comment_event()
    gh = _make_gh_mock([_make_reaction("heart"), _make_reaction("rocket")])
    installation_repo = AsyncMock()

    with (
        patch(
            "d1ff.webhook.event_dispatcher.get_settings",
            return_value=_make_settings_mock(),
        ),
        patch(
            "d1ff.github.GitHubAppClient"
        ) as MockClient,
        patch(
            "d1ff.feedback.reaction_collector.record_reaction",
            new_callable=AsyncMock,
        ) as mock_record,
    ):
        mock_instance = AsyncMock()
        mock_instance.get_installation_client.return_value = gh
        MockClient.return_value = mock_instance

        await handle_pr_review_comment_reaction_event(event, installation_repo)

        mock_record.assert_not_called()


async def test_reaction_handler_mixed_reactions() -> None:
    """Reactions ['+1', 'heart', '-1'] → record_reaction called twice (only thumbs reactions)."""
    event = _make_pr_review_comment_event()
    gh = _make_gh_mock(
        [_make_reaction("+1"), _make_reaction("heart"), _make_reaction("-1")]
    )
    installation_repo = AsyncMock()

    with (
        patch(
            "d1ff.webhook.event_dispatcher.get_settings",
            return_value=_make_settings_mock(),
        ),
        patch(
            "d1ff.github.GitHubAppClient"
        ) as MockClient,
        patch(
            "d1ff.feedback.reaction_collector.record_reaction",
            new_callable=AsyncMock,
        ) as mock_record,
    ):
        mock_instance = AsyncMock()
        mock_instance.get_installation_client.return_value = gh
        MockClient.return_value = mock_instance

        await handle_pr_review_comment_reaction_event(event, installation_repo)

        assert mock_record.call_count == 2
        recorded_types = {c[0][0].reaction_type for c in mock_record.call_args_list}
        assert recorded_types == {"+1", "-1"}


async def test_reaction_handler_no_reactions() -> None:
    """Empty reactions list → record_reaction NOT called."""
    event = _make_pr_review_comment_event()
    gh = _make_gh_mock([])
    installation_repo = AsyncMock()

    with (
        patch(
            "d1ff.webhook.event_dispatcher.get_settings",
            return_value=_make_settings_mock(),
        ),
        patch(
            "d1ff.github.GitHubAppClient"
        ) as MockClient,
        patch(
            "d1ff.feedback.reaction_collector.record_reaction",
            new_callable=AsyncMock,
        ) as mock_record,
    ):
        mock_instance = AsyncMock()
        mock_instance.get_installation_client.return_value = gh
        MockClient.return_value = mock_instance

        await handle_pr_review_comment_reaction_event(event, installation_repo)

        mock_record.assert_not_called()


async def test_reaction_handler_github_api_error() -> None:
    """GitHub API raises an exception → no re-raise (handler logs error, returns silently)."""
    event = _make_pr_review_comment_event()
    installation_repo = AsyncMock()

    with (
        patch(
            "d1ff.webhook.event_dispatcher.get_settings",
            return_value=_make_settings_mock(),
        ),
        patch(
            "d1ff.github.GitHubAppClient"
        ) as MockClient,
        patch(
            "d1ff.feedback.reaction_collector.record_reaction",
            new_callable=AsyncMock,
        ) as mock_record,
    ):
        mock_instance = AsyncMock()
        mock_instance.get_installation_client.side_effect = RuntimeError("GitHub API error")
        MockClient.return_value = mock_instance

        # Must not raise
        await handle_pr_review_comment_reaction_event(event, installation_repo)

        mock_record.assert_not_called()


# ---------------------------------------------------------------------------
# Tests: dispatch_event routing
# ---------------------------------------------------------------------------


async def test_dispatch_routes_pr_review_comment_event() -> None:
    """dispatch_event with event_type='pull_request_review_comment' calls the reaction handler."""
    event = _make_pr_review_comment_event()
    installation_repo = AsyncMock()

    with patch(
        "d1ff.webhook.event_dispatcher.handle_pr_review_comment_reaction_event",
        new_callable=AsyncMock,
    ) as mock_handler:
        await dispatch_event(event, installation_repo, dedup_check=False)
        mock_handler.assert_called_once_with(event, installation_repo)
