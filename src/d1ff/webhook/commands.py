"""Handle /d1ff slash commands from issue_comment webhooks (FR19, FR23)."""

from __future__ import annotations

import structlog

from d1ff.storage.api_key_repo import get_api_key_config
from d1ff.storage.installation_repo import InstallationRepository
from d1ff.webhook.command_parser import (
    COMMAND_PAUSE,
    COMMAND_RESUME,
    COMMAND_REVIEW,
    COMMAND_SKIP,
    is_bot_user,
    parse_command,
)
from d1ff.webhook.models import IssueCommentPayload, WebhookEvent

logger = structlog.get_logger(__name__)


async def handle_issue_comment_event(
    event: WebhookEvent,
    installation_repo: InstallationRepository,
) -> None:
    """Route issue_comment events to the appropriate command handler (FR19-FR23, Epic 4)."""
    payload = IssueCommentPayload.model_validate(event.payload)
    installation_id = event.installation_id

    # Guard: only process "created" actions — ignore edits and deletes
    if payload.action != "created":
        logger.debug(
            "issue_comment_action_skipped",
            installation_id=installation_id,
            action=payload.action,
            stage="command_dispatch",
        )
        return

    # Guard: skip plain issue comments (not on a PR)
    if payload.issue.pull_request is None:
        logger.debug(
            "issue_comment_not_on_pr_skipped",
            installation_id=installation_id,
            stage="command_dispatch",
        )
        return

    # Guard: skip bot comments to prevent infinite loops
    if is_bot_user(payload.sender.login, payload.sender.type):
        logger.debug(
            "bot_comment_ignored",
            installation_id=installation_id,
            sender_login=payload.sender.login,
            stage="command_dispatch",
        )
        return

    # Parse the command from the comment body
    command = parse_command(payload.comment.body)
    if command is None:
        return

    pr_number = payload.issue.number
    logger.info(
        "command_received",
        installation_id=installation_id,
        pr_number=pr_number,
        command=command,
        stage="command_dispatch",
    )

    if command == COMMAND_REVIEW:
        await handle_review_command(event, payload, installation_repo)
    elif command == COMMAND_PAUSE:
        try:
            await handle_pause_command(payload, installation_repo)
        except Exception as exc:
            logger.error(
                "pause_command_failed",
                installation_id=installation_id,
                pr_number=pr_number,
                stage="command_dispatch",
                error=str(exc),
            )
    elif command == COMMAND_RESUME:
        try:
            await handle_resume_command(payload, installation_repo)
        except Exception as exc:
            logger.error(
                "resume_command_failed",
                installation_id=installation_id,
                pr_number=pr_number,
                stage="command_dispatch",
                error=str(exc),
            )
    elif command == COMMAND_SKIP:
        try:
            await handle_skip_command(payload, installation_repo)
        except Exception as exc:
            logger.error(
                "skip_command_failed",
                installation_id=installation_id,
                pr_number=pr_number,
                stage="command_dispatch",
                error=str(exc),
            )


async def handle_review_command(
    event: WebhookEvent,
    payload: IssueCommentPayload,
    installation_repo: InstallationRepository,
) -> None:
    """Trigger a full PR review in response to /d1ff review command (FR19)."""
    from d1ff.comments import format_review, post_review  # noqa: PLC0415
    from d1ff.config import AppSettings, get_settings  # noqa: PLC0415
    from d1ff.context import build_review_context  # noqa: PLC0415
    from d1ff.github import GitHubAppClient  # noqa: PLC0415
    from d1ff.pipeline import run_pipeline  # noqa: PLC0415
    from d1ff.providers.models import ProviderConfig  # noqa: PLC0415
    from d1ff.webhook.models import (  # noqa: PLC0415
        InstallationInfo,
        PullRequestInfo,
        PullRequestPayload,
        RepositoryInfo,
    )

    installation_id = event.installation_id
    pr_number = payload.issue.number
    owner, repo = payload.repository.full_name.split("/", 1)

    # Resolve GitHub client
    settings: AppSettings = get_settings()
    github_client = GitHubAppClient(
        app_id=settings.GITHUB_APP_ID,
        private_key=settings.GITHUB_PRIVATE_KEY,
    )

    # Post acknowledgment reply FIRST (FR23) — before pipeline starts
    try:
        gh = await github_client.get_installation_client(installation_id)
        await gh.rest.issues.async_create_comment(
            owner=owner,
            repo=repo,
            issue_number=pr_number,
            body="d1ff review triggered. Results will appear shortly.",
        )
        logger.info(
            "command_acknowledgment_posted",
            installation_id=installation_id,
            pr_number=pr_number,
            stage="command_dispatch",
        )
    except Exception as exc:
        logger.error(
            "acknowledgment_posting_failed",
            installation_id=installation_id,
            pr_number=pr_number,
            stage="command_dispatch",
            error=str(exc),
        )
        # Continue even if acknowledgment fails — still attempt the review

    try:
        # Fetch full PR data from GitHub to construct PullRequestPayload
        gh = await github_client.get_installation_client(installation_id)
        pr_response = await gh.rest.pulls.async_get(
            owner=owner,
            repo=repo,
            pull_number=pr_number,
        )
        pr_data = pr_response.parsed_data

        # Construct PullRequestPayload from API response
        pr_payload = PullRequestPayload(
            action="manual_review",
            pull_request=PullRequestInfo(
                number=pr_data.number,
                title=pr_data.title,
                state=str(pr_data.state),
                draft=pr_data.draft or False,
                user={"login": pr_data.user.login if pr_data.user else "unknown"},
                base={"ref": pr_data.base.ref, "sha": pr_data.base.sha},
                head={"ref": pr_data.head.ref, "sha": pr_data.head.sha},
                html_url=str(pr_data.html_url) if pr_data.html_url else "",
            ),
            repository=RepositoryInfo(
                id=payload.repository.id,
                name=payload.repository.name,
                full_name=payload.repository.full_name,
                private=payload.repository.private,
            ),
            installation=InstallationInfo(
                id=payload.installation.id,
                account=payload.installation.account,
            ),
        )

        # Build review context (AD-9: PullRequestPayload → ReviewContext)
        context = await build_review_context(github_client, pr_payload)

        # Load provider config for this installation from storage
        api_key_data = await get_api_key_config(installation_id)
        if api_key_data is None:
            logger.error(
                "provider_config_not_found",
                installation_id=installation_id,
                pr_number=pr_number,
                stage="manual_review",
            )
            return

        config = ProviderConfig(
            installation_id=installation_id,
            provider=str(api_key_data["provider"]),
            model=str(api_key_data["model"]),
            api_key_encrypted=str(api_key_data["encrypted_key"]),
            custom_endpoint=api_key_data.get("custom_endpoint"),
        )

        # Run the review pipeline (AD-9: ReviewContext → SummaryResult, VerifiedFindings, CostBadge)
        summary_result, verified_findings, cost_badge = await run_pipeline(context, config)

        # Format the review (AD-9: VerifiedFindings → FormattedReview)
        formatted = format_review(
            verified_findings,
            summary_result,
            installation_id=str(installation_id),
        )

        # Post the review to GitHub (AD-9: FormattedReview → GitHubComments, FR36)
        await post_review(formatted, context, github_client, owner, repo, cost_badge=cost_badge)

    except Exception as exc:
        from d1ff.observability import post_error_comment  # noqa: PLC0415

        logger.error(
            "review_pipeline_failed",
            installation_id=installation_id,
            pr_number=pr_number,
            stage="commands",
            error_type=type(exc).__name__,
            # NEVER log exc message — may contain source code or API key (NFR22)
        )
        await post_error_comment(
            github_client=github_client,
            installation_id=installation_id,
            owner=owner,
            repo=repo,
            pr_number=pr_number,
            stage="commands",
            error=exc,
        )
        # Do NOT re-raise — webhook must return 2xx


async def _get_github_client(installation_id: int):  # type: ignore[no-untyped-def]
    """Return an authenticated GitHub installation client."""
    from d1ff.config import AppSettings, get_settings  # noqa: PLC0415
    from d1ff.github import GitHubAppClient  # noqa: PLC0415

    settings: AppSettings = get_settings()
    github_client = GitHubAppClient(
        app_id=settings.GITHUB_APP_ID,
        private_key=settings.GITHUB_PRIVATE_KEY,
    )
    return await github_client.get_installation_client(installation_id)


async def handle_pause_command(
    payload: IssueCommentPayload,
    installation_repo: InstallationRepository,
) -> None:
    """Pause automatic reviews for this PR (FR20)."""
    from d1ff.storage.pr_state_repo import set_pr_state  # noqa: PLC0415

    installation_id = payload.installation.id
    repo_full_name = payload.repository.full_name
    pr_number = payload.issue.number
    owner, repo = repo_full_name.split("/", 1)

    await set_pr_state(installation_id, repo_full_name, pr_number, "paused")
    logger.info(
        "pr_paused",
        installation_id=installation_id,
        pr_number=pr_number,
        stage="command_dispatch",
    )

    gh = await _get_github_client(installation_id)
    await gh.rest.issues.async_create_comment(
        owner=owner,
        repo=repo,
        issue_number=pr_number,
        body="d1ff automatic reviews paused for this PR. Post `/d1ff resume` to re-enable.",
    )
    logger.info(
        "command_acknowledgment_posted",
        installation_id=installation_id,
        pr_number=pr_number,
        command="pause",
        stage="command_dispatch",
    )


async def handle_resume_command(
    payload: IssueCommentPayload,
    installation_repo: InstallationRepository,
) -> None:
    """Resume automatic reviews for this PR (FR21)."""
    from d1ff.storage.pr_state_repo import set_pr_state  # noqa: PLC0415

    installation_id = payload.installation.id
    repo_full_name = payload.repository.full_name
    pr_number = payload.issue.number
    owner, repo = repo_full_name.split("/", 1)

    await set_pr_state(installation_id, repo_full_name, pr_number, "active")
    logger.info(
        "pr_resumed",
        installation_id=installation_id,
        pr_number=pr_number,
        stage="command_dispatch",
    )

    gh = await _get_github_client(installation_id)
    await gh.rest.issues.async_create_comment(
        owner=owner,
        repo=repo,
        issue_number=pr_number,
        body="d1ff automatic reviews resumed for this PR.",
    )
    logger.info(
        "command_acknowledgment_posted",
        installation_id=installation_id,
        pr_number=pr_number,
        command="resume",
        stage="command_dispatch",
    )


async def handle_skip_command(
    payload: IssueCommentPayload,
    installation_repo: InstallationRepository,
) -> None:
    """Skip the current review cycle for this PR (FR22)."""
    installation_id = payload.installation.id
    pr_number = payload.issue.number
    owner, repo = payload.repository.full_name.split("/", 1)
    logger.info(
        "pr_review_skipped",
        installation_id=installation_id,
        pr_number=pr_number,
        stage="command_dispatch",
    )

    gh = await _get_github_client(installation_id)
    await gh.rest.issues.async_create_comment(
        owner=owner,
        repo=repo,
        issue_number=pr_number,
        body="d1ff review skipped for this push.",
    )
    logger.info(
        "command_acknowledgment_posted",
        installation_id=installation_id,
        pr_number=pr_number,
        command="skip",
        stage="command_dispatch",
    )
