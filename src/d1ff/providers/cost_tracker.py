"""Token counting and cost estimation for LLM provider calls (FR36, FR37)."""

from __future__ import annotations

from typing import Any

import litellm
import structlog
from pydantic import BaseModel, ConfigDict

logger = structlog.get_logger(__name__)


class CostRecord(BaseModel):
    """Immutable record of token usage and cost for a single LLM call."""

    model_config = ConfigDict(frozen=True)

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    model: str


class PassTokens(BaseModel):
    """Immutable record of token usage for a single pipeline pass (FR37)."""

    model_config = ConfigDict(frozen=True)

    pass_name: str  # e.g. "summary", "review", "verification"
    prompt_tokens: int
    completion_tokens: int


class ReviewCost(BaseModel):
    """Aggregated token usage and cost estimate across all pipeline passes (FR36, FR37)."""

    model_config = ConfigDict(frozen=True)

    total_prompt_tokens: int
    total_completion_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    model: str  # e.g. "claude-3-5-haiku-20241022"


def aggregate_costs(pass_results: list[PassTokens], model: str) -> ReviewCost:
    """Aggregate token counts across all passes and calculate total USD cost.

    If LiteLLM cost calculation fails (unknown model, custom endpoint), cost defaults
    to 0.0 — pipeline must never be blocked by cost tracking failure.

    Args:
        pass_results: Token counts from each pipeline pass (summary, review, verification).
        model: LiteLLM model string (e.g. "anthropic/claude-3-5-haiku-20241022").

    Returns:
        ReviewCost with aggregated totals and estimated USD cost.
    """
    total_prompt = sum(p.prompt_tokens for p in pass_results)
    total_completion = sum(p.completion_tokens for p in pass_results)
    total = total_prompt + total_completion

    try:
        cost_usd = litellm.completion_cost(
            model=model,
            prompt_tokens=total_prompt,
            completion_tokens=total_completion,
        )
    except Exception as exc:
        logger.warning(
            "cost_calculation_failed",
            model=model,
            error=str(exc),
            stage="cost_tracking",
        )
        cost_usd = 0.0

    return ReviewCost(
        total_prompt_tokens=total_prompt,
        total_completion_tokens=total_completion,
        total_tokens=total,
        estimated_cost_usd=cost_usd,
        model=model,
    )


def extract_cost_record(response: Any, model: str) -> CostRecord:
    """Extract token usage and cost estimate from a litellm response.

    If cost calculation fails (unknown model, malformed response), defaults to 0.0.
    """
    usage = response.usage
    try:
        cost_usd = litellm.completion_cost(completion_response=response)
    except Exception:
        cost_usd = 0.0
    return CostRecord(
        prompt_tokens=usage.prompt_tokens,
        completion_tokens=usage.completion_tokens,
        total_tokens=usage.total_tokens,
        estimated_cost_usd=cost_usd,
        model=model,
    )
