"""Feedback collection package (FR38–FR40)."""

from d1ff.feedback.models import FeedbackReaction
from d1ff.feedback.reaction_collector import get_reaction_summary, record_reaction

__all__ = ["FeedbackReaction", "get_reaction_summary", "record_reaction"]
