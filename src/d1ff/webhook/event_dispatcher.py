"""Dispatch webhook events to the appropriate handlers."""

import structlog

from d1ff.config import AppSettings, get_settings
from d1ff.github import GitHubAppClient
from d1ff.storage.api_key_repo import get_api_key_config
from d1ff.storage.installation_repo import InstallationRepository
from d1ff.webhook.dedup_guard import is_duplicate
from d1ff.webhook.models import (
    PR_REVIEW_ACTIONS,
    InstallationPayload,
    PullRequestPayload,
    PullRequestReviewCommentPayload,
    RepositoryInfo,
    WebhookEvent,
)

logger = structlog.get_logger()


async def dispatch_event(
    event: WebhookEvent,
    installation_repo: InstallationRepository,
    dedup_check: bool = True,
    github_client: GitHubAppClient | None = None,
    settings: AppSettings | None = None,
) -> None:
    """Route a verified webhook event to the appropriate handler.

    Unknown event types are logged at INFO level and silently ignored.
    """
    if dedup_check and event.delivery_id and await is_duplicate(event.delivery_id):
        logger.info(
            "webhook_duplicate_rejected",
            installation_id=event.installation_id,
            delivery_id=event.delivery_id,
            stage="deduplication",
        )
        return

    logger.info(
        "webhook_event_dispatched",
        installation_id=event.installation_id,
        event_type=event.event_type,
        delivery_id=event.delivery_id,
        stage="event_dispatch",
    )

    if event.event_type == "installation":
        await handle_installation_event(event, installation_repo)
    elif event.event_type == "installation_repositories":
        await handle_installation_repositories_event(event, installation_repo)
    elif event.event_type == "pull_request":
        await handle_pull_request_event(
            event, installation_repo, github_client=github_client, settings=settings
        )
    elif event.event_type == "issue_comment":
        await handle_issue_comment_event(event, installation_repo)
    elif event.event_type == "pull_request_review_comment":
        await handle_pr_review_comment_reaction_event(event, installation_repo)
    else:
        logger.info(
            "webhook_event_unknown",
            event_type=event.event_type,
            installation_id=event.installation_id,
            delivery_id=event.delivery_id,
            stage="event_dispatch",
        )


async def handle_installation_event(
    event: WebhookEvent,
    repo: InstallationRepository,
) -> None:
    """Handle installation webhook events (created, deleted, suspend, unsuspend)."""
    payload = InstallationPayload.model_validate(event.payload)
    installation_id = payload.installation.id
    account_login = payload.installation.account.login
    account_type = payload.installation.account.type

    logger.info(
        "handle_installation_event",
        installation_id=installation_id,
        account_login=account_login,
        action=payload.action,
    )

    if payload.action == "created":
        await repo.upsert_installation(installation_id, account_login, account_type)
        if payload.repositories:
            await repo.upsert_repositories(installation_id, payload.repositories)
    elif payload.action == "deleted":
        await repo.delete_installation(installation_id)
    elif payload.action == "suspend":
        await repo.update_installation_status(installation_id, suspended=True)
    elif payload.action == "unsuspend":
        await repo.update_installation_status(installation_id, suspended=False)
    else:
        logger.info(
            "installation_event_unhandled_action",
            action=payload.action,
            installation_id=installation_id,
        )


async def handle_installation_repositories_event(
    event: WebhookEvent,
    repo: InstallationRepository,
) -> None:
    """Handle installation_repositories events (added, removed)."""
    payload = InstallationPayload.model_validate(event.payload)
    installation_id = payload.installation.id
    account_login = payload.installation.account.login

    logger.info(
        "handle_installation_repositories_event",
        installation_id=installation_id,
        account_login=account_login,
        action=payload.action,
    )

    repositories_added: list[RepositoryInfo] = []
    repositories_removed: list[RepositoryInfo] = []

    raw = event.payload
    if payload.action == "added":
        raw_repos = raw.get("repositories_added") or []
        repositories_added = [RepositoryInfo.model_validate(r) for r in raw_repos]
    elif payload.action == "removed":
        raw_repos = raw.get("repositories_removed") or []
        repositories_removed = [RepositoryInfo.model_validate(r) for r in raw_repos]

    if repositories_added:
        await repo.upsert_repositories(installation_id, repositories_added)

    for r in repositories_removed:
        await repo.delete_repository(installation_id, r.id)


async def handle_pull_request_event(
    event: WebhookEvent,
    installation_repo: InstallationRepository,
    github_client: GitHubAppClient | None = None,
    settings: AppSettings | None = None,
) -> None:
    """Dispatch pull_request events to the review pipeline (FR7)."""
    payload = PullRequestPayload.model_validate(event.payload)
    pr_number = payload.pull_request.number

    if payload.action not in PR_REVIEW_ACTIONS:
        logger.info(
            "pull_request_action_skipped",
            installation_id=event.installation_id,
            pr_number=pr_number,
            action=payload.action,
            stage="event_dispatch",
        )
        return

    from d1ff.webhook.pr_filter import is_draft_pr, is_large_pr, truncate_diff  # noqa: PLC0415

    if is_draft_pr(payload.pull_request.draft):
        logger.info(
            "pull_request_draft_skipped",
            installation_id=event.installation_id,
            pr_number=pr_number,
            stage="event_dispatch",
        )
        return

    # Check for d1ff:skip label — skip this review cycle (Story 4.2, FR22)
    skip_labels = {label.name for label in payload.pull_request.labels}
    if "d1ff:skip" in skip_labels:
        logger.info(
            "pr_review_skipped_label",
            installation_id=event.installation_id,
            pr_number=pr_number,
            stage="event_dispatch",
        )
        return

    # Check if PR is paused — do NOT trigger automatic review (Story 4.2, FR20)
    from d1ff.storage.pr_state_repo import get_pr_state  # noqa: PLC0415

    repo_full_name = payload.repository.full_name
    pr_state = await get_pr_state(event.installation_id, repo_full_name, pr_number)
    if pr_state == "paused":
        logger.info(
            "pr_review_skipped_paused",
            installation_id=event.installation_id,
            pr_number=pr_number,
            stage="event_dispatch",
        )
        return

    logger.info(
        "pull_request_dispatched_to_pipeline",
        installation_id=event.installation_id,
        pr_number=pr_number,
        action=payload.action,
        draft=payload.pull_request.draft,
        stage="event_dispatch",
    )

    # Resolve github_client and settings if not provided (allows DI for tests)
    resolved_settings = settings or get_settings()
    resolved_client = github_client or GitHubAppClient(
        app_id=resolved_settings.GITHUB_APP_ID,
        private_key=resolved_settings.GITHUB_PRIVATE_KEY,
    )

    # Extract owner and repo from repository full_name (e.g., "owner/repo")
    parts = payload.repository.full_name.split("/", 1)
    owner = parts[0]
    repo = parts[1]

    # Lazy imports to avoid circular import (comments → context → webhook → event_dispatcher)
    from d1ff.comments import format_review, post_review  # noqa: PLC0415
    from d1ff.context import build_review_context  # noqa: PLC0415
    from d1ff.observability import post_error_comment  # noqa: PLC0415
    from d1ff.pipeline import run_pipeline  # noqa: PLC0415
    from d1ff.providers.models import ProviderConfig  # noqa: PLC0415

    # Build review context (AD-9: WebhookEvent → ReviewContext)
    try:
        context = await build_review_context(resolved_client, payload)
    except Exception as exc:
        logger.error(
            "context_build_failed",
            installation_id=event.installation_id,
            pr_number=pr_number,
            stage="context_build",
            error_type=type(exc).__name__,
            # NEVER log exc message — may contain source code or API key (NFR22)
        )
        await post_error_comment(
            github_client=resolved_client,
            installation_id=event.installation_id,
            owner=owner,
            repo=repo,
            pr_number=pr_number,
            stage="context_build",
            error=exc,
        )
        return

    # Large-PR truncation (NFR3): truncate diff if PR exceeds threshold
    if is_large_pr(context.lines_changed):
        logger.warning(
            "large_pr_detected",
            installation_id=event.installation_id,
            pr_number=pr_number,
            lines_changed=context.lines_changed,
            stage="event_dispatch",
        )
        from d1ff.webhook.large_pr_notifier import post_large_pr_notice  # noqa: PLC0415

        await post_large_pr_notice(
            resolved_client, event.installation_id, owner, repo, pr_number, context.lines_changed
        )
        context = context.model_copy(update={"diff": truncate_diff(context.diff)})

    # Load provider config for this installation from storage (api_key_repo)
    api_key_data = await get_api_key_config(event.installation_id)
    if api_key_data is None:
        logger.error(
            "provider_config_not_found",
            installation_id=event.installation_id,
            pr_number=pr_number,
            stage="event_dispatch",
        )
        return

    config = ProviderConfig(
        installation_id=event.installation_id,
        provider=str(api_key_data["provider"]),
        model=str(api_key_data["model"]),
        api_key_encrypted=str(api_key_data["encrypted_key"]),
        custom_endpoint=api_key_data.get("custom_endpoint"),
    )

    # Run the review pipeline (AD-9: ReviewContext → [SummaryResult, VerifiedFindings, CostBadge])
    try:
        summary_result, verified_findings, cost_badge = await run_pipeline(context, config)

        # Format the review (AD-9: VerifiedFindings → FormattedReview)
        formatted = format_review(
            verified_findings,
            summary_result,
            installation_id=str(event.installation_id),
        )

        # Post the review to GitHub (AD-9: FormattedReview → GitHubComments, FR29, FR30, FR36)
        await post_review(formatted, context, resolved_client, owner, repo, cost_badge=cost_badge)
    except Exception as exc:
        logger.error(
            "review_pipeline_failed",
            installation_id=event.installation_id,
            pr_number=pr_number,
            stage="pipeline",
            error_type=type(exc).__name__,
            # NEVER log exc message — may contain source code or API key (NFR22)
        )
        await post_error_comment(
            github_client=resolved_client,
            installation_id=event.installation_id,
            owner=owner,
            repo=repo,
            pr_number=pr_number,
            stage="pipeline",
            error=exc,
        )
        # Do NOT re-raise — webhook must return 200 to GitHub (GitHub retries on non-2xx)


async def handle_issue_comment_event(
    event: WebhookEvent,
    installation_repo: InstallationRepository,
) -> None:
    """Route issue_comment events to command handler (FR19-FR23, Epic 4)."""
    from d1ff.webhook.commands import handle_issue_comment_event as _handle  # noqa: PLC0415

    await _handle(event, installation_repo)


async def handle_pr_review_comment_reaction_event(
    event: WebhookEvent,
    installation_repo: InstallationRepository,
) -> None:
    """Collect developer reactions on d1ff review comments (FR38, FR39).

    GitHub does not send reaction webhooks. This handler fires on any
    pull_request_review_comment event and fetches reactions for the
    specific comment that triggered the webhook. Only records '+1' and '-1'
    reactions (thumbs-up/thumbs-down).
    """
    from datetime import UTC, datetime  # noqa: PLC0415

    from d1ff.feedback.models import FeedbackReaction  # noqa: PLC0415
    from d1ff.feedback.reaction_collector import record_reaction  # noqa: PLC0415
    from d1ff.github import GitHubAppClient  # noqa: PLC0415

    try:
        payload = PullRequestReviewCommentPayload.model_validate(event.payload)
        installation_id = event.installation_id
        comment_id = payload.comment.id
        pr_number = payload.pull_request.number
        repo_full_name = payload.repository.full_name
        owner, repo = repo_full_name.split("/", 1)

        resolved_settings = get_settings()
        github_client = GitHubAppClient(
            app_id=resolved_settings.GITHUB_APP_ID,
            private_key=resolved_settings.GITHUB_PRIVATE_KEY,
        )
        gh = await github_client.get_installation_client(installation_id)
        resp = await gh.rest.reactions.async_list_for_pull_request_review_comment(
            owner=owner,
            repo=repo,
            comment_id=comment_id,
        )
        reactions = resp.parsed_data

        for rxn in reactions:
            if rxn.content not in ("+1", "-1"):
                continue
            feedback = FeedbackReaction(
                comment_id=comment_id,
                reaction_type=rxn.content,
                installation_id=installation_id,
                pr_number=pr_number,
                repo_full_name=repo_full_name,
                created_at=datetime.now(UTC).isoformat(),
            )
            await record_reaction(feedback)
            logger.info(
                "reaction_recorded",
                installation_id=installation_id,
                pr_number=pr_number,
                comment_id=comment_id,
                reaction_type=rxn.content,
                stage="feedback_collection",
            )
    except Exception as exc:
        logger.error(
            "reaction_collection_failed",
            installation_id=event.installation_id,
            error=str(exc),
            stage="feedback_collection",
        )
