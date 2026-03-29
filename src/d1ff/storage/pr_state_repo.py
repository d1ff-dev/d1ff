"""PR pause/resume state repository (PostgreSQL)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from d1ff.storage.schema import pr_states


async def set_pr_state(
    installation_id: int,
    repo_full_name: str,
    pr_number: int,
    state: str,
) -> None:
    from d1ff.storage.database import get_connection

    now = datetime.now(UTC)
    async with get_connection() as conn:
        stmt = (
            insert(pr_states)
            .values(
                installation_id=installation_id,
                repo_full_name=repo_full_name,
                pr_number=pr_number,
                state=state,
                updated_at=now,
            )
            .on_conflict_do_update(
                constraint=pr_states.primary_key,
                set_={"state": state, "updated_at": now},
            )
        )
        await conn.execute(stmt)
        await conn.commit()


async def get_pr_state(
    installation_id: int,
    repo_full_name: str,
    pr_number: int,
) -> str:
    from d1ff.storage.database import get_connection

    async with get_connection() as conn:
        result = await conn.execute(
            select(pr_states.c.state).where(
                (pr_states.c.installation_id == installation_id)
                & (pr_states.c.repo_full_name == repo_full_name)
                & (pr_states.c.pr_number == pr_number)
            )
        )
        row = result.first()
        return row[0] if row else "active"
