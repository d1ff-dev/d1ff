"""Pydantic contracts for the LLM pipeline stages (AD-9).

These models define the typed data contracts between pipeline stages:
  Pass 1 → SummaryResult
  Pass 2 → ReviewFindings (list of ReviewFinding)
  Pass 3 → VerifiedFindings (filtered, noise-removed findings)
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from d1ff.providers.cost_tracker import CostRecord


class SummaryResult(BaseModel):
    """Output of Pass 1: high-level description of what the PR does (FR12)."""

    model_config = ConfigDict(frozen=True)

    summary: str  # High-level description of what the PR does (FR12)
    cost: CostRecord  # Token usage and cost for Pass 1


class ReviewFinding(BaseModel):
    """A single line-by-line finding from Pass 2 (FR13)."""

    model_config = ConfigDict(frozen=True)

    severity: Literal["critical", "warning", "suggestion", "nitpick"]
    category: Literal["bug", "security", "style", "performance", "logic", "maintainability"]
    confidence: Literal["high", "medium", "low"]
    file: str
    line: int
    message: str
    suggestion: str | None = None  # Optional fix suggestion (FR29)


class ReviewFindings(BaseModel):
    """Output of Pass 2: all line-by-line findings from the review (FR13)."""

    model_config = ConfigDict(frozen=True)

    findings: list[ReviewFinding]  # All line-by-line findings from Pass 2 (FR13)
    cost: CostRecord  # Token usage and cost for Pass 2


class VerifiedFindings(BaseModel):
    """Output of Pass 3: filtered, actionable, non-duplicate findings (FR14)."""

    model_config = ConfigDict(frozen=True)

    findings: list[ReviewFinding]  # Filtered, actionable, non-duplicate findings (FR14)
    cost: CostRecord  # Token usage and cost for Pass 3
    # True if verification failed and unverified findings are used (NFR21)
    was_degraded: bool = False
