"""Pipeline orchestrator: runs Pass 1+2 in parallel, then Pass 3 sequentially (FR15, AD-14)."""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

import structlog

from d1ff.config import get_settings
from d1ff.context.models import ReviewContext
from d1ff.pipeline.models import ReviewFindings, SummaryResult, VerifiedFindings
from d1ff.pipeline.review_pass import run_review_pass
from d1ff.pipeline.summary_pass import run_summary_pass
from d1ff.pipeline.verification_pass import run_verification_pass
from d1ff.providers import CostRecord, PassTokens, aggregate_costs
from d1ff.providers.models import ProviderConfig

if TYPE_CHECKING:
    from d1ff.comments.models import CostBadge

logger = structlog.get_logger(__name__)

# Module-level semaphore (lazy initialization — created on first use, not at import time)
_review_semaphore: asyncio.Semaphore | None = None


def get_review_semaphore() -> asyncio.Semaphore:
    """Return (or lazily create) the module-level concurrency semaphore (AD-14, NFR15)."""
    global _review_semaphore
    if _review_semaphore is None:
        _review_semaphore = asyncio.Semaphore(get_settings().MAX_CONCURRENT_REVIEWS)
    return _review_semaphore


async def run_pipeline(
    context: ReviewContext, config: ProviderConfig
) -> tuple[SummaryResult | None, VerifiedFindings, CostBadge | None]:
    """Run Pass 1+2 in parallel then Pass 3 sequentially, bounded by the global semaphore.

    Returns (summary_result, verified_findings, cost_badge) 3-tuple.
    cost_badge is a CostBadge instance or None if cost tracking failed.

    Graceful degradation (FR15, AD-14, NFR21):
    - Pass 1 failure → returns (None, verified_findings, cost_badge); no summary posted.
    - Pass 2 failure → re-raises; caller (webhook handler) posts an error comment.
    - Pass 3 failure → returns unverified findings with was_degraded=True; review continues.
    """
    from d1ff.comments.models import CostBadge  # noqa: PLC0415 — lazy import to avoid circular

    logger.info(
        "pipeline_start",
        installation_id=config.installation_id,
        stage="pipeline",
        pr_number=context.pr_metadata.number,
    )

    start_ms = time.monotonic()

    async with get_review_semaphore():
        summary_task = asyncio.create_task(run_summary_pass(context, config))
        review_task = asyncio.create_task(run_review_pass(context, config))
        results = await asyncio.gather(summary_task, review_task, return_exceptions=True)

    summary_result = results[0]
    review_result = results[1]

    # Pass 2 failure is fatal — re-raise so caller can post an error comment (AD-10)
    if isinstance(review_result, BaseException):
        logger.error(
            "review_pass_failed",
            installation_id=config.installation_id,
            stage="review_pass",
            error=str(review_result),
        )
        raise review_result

    review_findings: ReviewFindings = review_result

    # Pass 1 failure is non-fatal — post review without summary (AD-10)
    if isinstance(summary_result, BaseException):
        logger.error(
            "summary_pass_failed",
            installation_id=config.installation_id,
            stage="summary_pass",
            error=str(summary_result),
        )
        summary: SummaryResult | None = None
        summary_cost = CostRecord(
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            estimated_cost_usd=0.0,
            model=config.model,
        )
    else:
        summary = summary_result
        summary_cost = summary_result.cost

    # Pass 3: verification (sequential — depends on Pass 2 output)
    try:
        verified_findings = await run_verification_pass(review_findings, context, config)
    except Exception as exc:
        logger.error(
            "verification_pass_failed",
            installation_id=config.installation_id,
            stage="verification_pass",
            error=str(exc),
        )
        # NFR21: post unverified findings with disclaimer
        verified_findings = VerifiedFindings(
            findings=review_findings.findings,
            cost=CostRecord(
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                estimated_cost_usd=0.0,
                model=config.model,
            ),
            was_degraded=True,
        )

    elapsed_ms = int((time.monotonic() - start_ms) * 1000)

    logger.info(
        "pipeline_verification_stats",
        installation_id=config.installation_id,
        pr_number=context.pr_metadata.number,
        stage="pipeline_verification",
        pre_verification_count=len(review_findings.findings),
        post_verification_count=len(verified_findings.findings),
        filtered_count=len(review_findings.findings) - len(verified_findings.findings),
        was_degraded=verified_findings.was_degraded,
    )

    # Aggregate token counts across all three passes and build cost badge (FR36, FR37)
    model_string = f"{config.provider}/{config.model}"
    pass_tokens = [
        PassTokens(
            pass_name="summary",
            prompt_tokens=summary_cost.prompt_tokens,
            completion_tokens=summary_cost.completion_tokens,
        ),
        PassTokens(
            pass_name="review",
            prompt_tokens=review_findings.cost.prompt_tokens,
            completion_tokens=review_findings.cost.completion_tokens,
        ),
        PassTokens(
            pass_name="verification",
            prompt_tokens=verified_findings.cost.prompt_tokens,
            completion_tokens=verified_findings.cost.completion_tokens,
        ),
    ]

    cost_badge: CostBadge | None
    try:
        review_cost = aggregate_costs(pass_tokens, model=model_string)
        cost_badge = CostBadge(
            total_tokens=review_cost.total_tokens,
            prompt_tokens=review_cost.total_prompt_tokens,
            completion_tokens=review_cost.total_completion_tokens,
            estimated_cost_usd=review_cost.estimated_cost_usd,
            model=review_cost.model,
        )
        logger.info(
            "review_pipeline_complete",
            installation_id=config.installation_id,
            pr_number=context.pr_metadata.number,
            stage="pipeline_complete",
            total_tokens=review_cost.total_tokens,
            estimated_cost_usd=review_cost.estimated_cost_usd,
            model=review_cost.model,
            duration_ms=elapsed_ms,
        )
    except Exception as exc:
        logger.warning(
            "cost_tracking_failed",
            installation_id=config.installation_id,
            pr_number=context.pr_metadata.number,
            error=str(exc),
            stage="cost_tracking",
        )
        cost_badge = None
        logger.info(
            "pipeline_complete",
            installation_id=config.installation_id,
            stage="pipeline",
            pr_number=context.pr_metadata.number,
            duration_ms=elapsed_ms,
        )

    return (summary, verified_findings, cost_badge)
