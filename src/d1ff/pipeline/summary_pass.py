"""Pass 1 of the LLM pipeline: PR summary generation (FR12)."""

from __future__ import annotations

import time

import structlog

from d1ff.context.models import ReviewContext
from d1ff.pipeline.models import SummaryResult
from d1ff.prompts import load_prompt
from d1ff.providers import call_llm_with_retry, get_provider_family
from d1ff.providers.models import ProviderConfig

logger = structlog.get_logger(__name__)


async def run_summary_pass(context: ReviewContext, config: ProviderConfig) -> SummaryResult:
    """Execute Pass 1: generate a high-level summary of what the PR does (FR12).

    Returns a SummaryResult with the summary text and token cost.
    Exceptions from the LLM call propagate to the caller (orchestrator handles degradation).
    """
    logger.info(
        "summary_pass_start",
        installation_id=config.installation_id,
        stage="summary_pass",
    )

    prompt = load_prompt(get_provider_family(config.provider, config.model), "summary")

    messages = [
        {"role": "system", "content": prompt},
        {
            "role": "user",
            "content": (
                f"PR #{context.pr_metadata.number}: {context.pr_metadata.title}"
                f"\n\nDiff:\n{context.diff}"
            ),
        },
    ]

    start_ms = time.monotonic()
    text, cost = await call_llm_with_retry(config, messages)
    elapsed_ms = int((time.monotonic() - start_ms) * 1000)

    logger.info(
        "summary_pass_complete",
        installation_id=config.installation_id,
        stage="summary_pass",
        duration_ms=elapsed_ms,
        prompt_tokens=cost.prompt_tokens,
    )

    return SummaryResult(summary=text, cost=cost)
