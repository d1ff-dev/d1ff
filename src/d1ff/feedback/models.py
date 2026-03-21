"""Feedback reaction models (FR38, FR39)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class FeedbackReaction(BaseModel):
    """A developer's reaction to a d1ff review comment."""

    model_config = ConfigDict(frozen=True)

    comment_id: int
    reaction_type: str  # '+1' | '-1'
    installation_id: int
    pr_number: int
    repo_full_name: str
    created_at: str  # ISO 8601 UTC
