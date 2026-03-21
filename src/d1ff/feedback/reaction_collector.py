"""Collect and store GitHub reaction feedback (FR38, FR39)."""

from __future__ import annotations

from d1ff.feedback.models import FeedbackReaction
from d1ff.storage.database import get_connection


async def record_reaction(
    reaction: FeedbackReaction,
    database_url: str | None = None,
) -> None:
    """Persist a developer reaction to the feedback_reactions table."""
    from d1ff.config import get_settings  # noqa: PLC0415

    url = database_url or get_settings().DATABASE_URL
    async with get_connection(url) as db:
        await db.execute(
            """
            INSERT INTO feedback_reactions
                (comment_id, reaction_type, installation_id, pr_number, repo_full_name, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                reaction.comment_id,
                reaction.reaction_type,
                reaction.installation_id,
                reaction.pr_number,
                reaction.repo_full_name,
                reaction.created_at,
            ),
        )
        await db.commit()


async def get_reaction_summary(
    installation_id: int,
    repo_full_name: str,
    database_url: str | None = None,
) -> list[dict[str, object]]:
    """Return aggregate reaction counts per comment_id for an installation/repo.

    Returns list of dicts: {comment_id, thumbs_up, thumbs_down}
    Used for AC2: aggregate signal on comment quality.
    """
    from d1ff.config import get_settings  # noqa: PLC0415

    url = database_url or get_settings().DATABASE_URL
    async with get_connection(url) as db, db.execute(
        """
        SELECT
            comment_id,
            SUM(CASE WHEN reaction_type = '+1' THEN 1 ELSE 0 END) AS thumbs_up,
            SUM(CASE WHEN reaction_type = '-1' THEN 1 ELSE 0 END) AS thumbs_down
        FROM feedback_reactions
        WHERE installation_id = ? AND repo_full_name = ?
        GROUP BY comment_id
        """,
        (installation_id, repo_full_name),
    ) as cursor:
        rows = await cursor.fetchall()
        return [
            {"comment_id": row[0], "thumbs_up": row[1], "thumbs_down": row[2]}
            for row in rows
        ]
