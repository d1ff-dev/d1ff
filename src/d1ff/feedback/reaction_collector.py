"""Collect and store GitHub reaction feedback (PostgreSQL)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import case, func, select

from d1ff.feedback.models import FeedbackReaction
from d1ff.storage.schema import feedback_reactions


async def record_reaction(reaction: FeedbackReaction) -> None:
    from d1ff.storage.database import get_connection

    created_at = datetime.fromisoformat(reaction.created_at)

    async with get_connection() as conn:
        await conn.execute(
            feedback_reactions.insert().values(
                comment_id=reaction.comment_id,
                reaction_type=reaction.reaction_type,
                installation_id=reaction.installation_id,
                pr_number=reaction.pr_number,
                repo_full_name=reaction.repo_full_name,
                created_at=created_at,
            )
        )
        await conn.commit()


async def get_reaction_summary(
    installation_id: int,
    repo_full_name: str,
) -> list[dict[str, object]]:
    from d1ff.storage.database import get_connection

    async with get_connection() as conn:
        stmt = (
            select(
                feedback_reactions.c.comment_id,
                func.sum(case((feedback_reactions.c.reaction_type == "+1", 1), else_=0)).label(
                    "thumbs_up"
                ),
                func.sum(case((feedback_reactions.c.reaction_type == "-1", 1), else_=0)).label(
                    "thumbs_down"
                ),
            )
            .where(
                (feedback_reactions.c.installation_id == installation_id)
                & (feedback_reactions.c.repo_full_name == repo_full_name)
            )
            .group_by(feedback_reactions.c.comment_id)
        )
        result = await conn.execute(stmt)
        return [
            {"comment_id": row[0], "thumbs_up": row[1], "thumbs_down": row[2]}
            for row in result.fetchall()
        ]
