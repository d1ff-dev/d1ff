"""PR pause/resume state repository (FR20, FR21)."""

from __future__ import annotations

from datetime import UTC, datetime

from d1ff.storage.database import get_connection


async def set_pr_state(
    installation_id: int,
    repo_full_name: str,
    pr_number: int,
    state: str,  # "active" | "paused"
    database_url: str | None = None,
) -> None:
    """Insert or update PR state via UPSERT."""
    from d1ff.config import get_settings  # noqa: PLC0415

    url = database_url or get_settings().DATABASE_URL
    updated_at = datetime.now(UTC).isoformat()
    async with get_connection(url) as db:
        await db.execute(
            """
            INSERT INTO pr_states (installation_id, repo_full_name, pr_number, state, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (installation_id, repo_full_name, pr_number)
            DO UPDATE SET state = excluded.state, updated_at = excluded.updated_at
            """,
            (installation_id, repo_full_name, pr_number, state, updated_at),
        )
        await db.commit()


async def get_pr_state(
    installation_id: int,
    repo_full_name: str,
    pr_number: int,
    database_url: str | None = None,
) -> str:
    """Return PR state: 'paused' or 'active' (default if no row exists)."""
    from d1ff.config import get_settings  # noqa: PLC0415

    url = database_url or get_settings().DATABASE_URL
    async with get_connection(url) as db, db.execute(
        "SELECT state FROM pr_states"
        " WHERE installation_id = ? AND repo_full_name = ? AND pr_number = ?",
        (installation_id, repo_full_name, pr_number),
    ) as cursor:
        row = await cursor.fetchone()
        return str(row["state"]) if row else "active"
