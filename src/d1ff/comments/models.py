"""Pydantic models for formatted review comments (AD-9).

These models define the output contract of the comment formatting stage:
  VerifiedFindings → FormattedReview (this module)
  FormattedReview → review_poster.py (Story 3.8)
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class InlineComment(BaseModel):
    """Single inline comment to post on a specific file line."""

    model_config = ConfigDict(frozen=True)

    file: str
    line: int
    # Formatted markdown body: severity label, category, confidence, suggestion block
    body: str


class ReviewSummary(BaseModel):
    """Top-level summary comment body (posted as review summary)."""

    model_config = ConfigDict(frozen=True)

    # Full markdown: PR description (SummaryResult), severity breakdown,
    # grouped suggestions/nitpicks, optional disclaimer
    body: str


class FormattedReview(BaseModel):
    """Complete formatted review ready for posting."""

    model_config = ConfigDict(frozen=True)

    inline_comments: list[InlineComment]  # critical + warning findings only (FR28)
    # Contains PR summary + severity breakdown + grouped suggestion/nitpick findings
    summary: ReviewSummary
    # Passed through from VerifiedFindings.was_degraded (NFR21 disclaimer)
    was_degraded: bool


class CostBadge(BaseModel):
    """Formatted cost badge for appending to the review summary comment (FR36)."""

    model_config = ConfigDict(frozen=True)

    total_tokens: int
    prompt_tokens: int
    completion_tokens: int
    estimated_cost_usd: float
    model: str

    def format(self) -> str:
        """Return the formatted badge string for GitHub comment."""
        total_fmt = f"{self.total_tokens:,}"
        cost_fmt = f"${self.estimated_cost_usd:.4f}"
        return (
            f"📊 {total_fmt} tokens "
            f"({self.prompt_tokens:,} in · {self.completion_tokens:,} out) · {cost_fmt}"
        )
