"""In-memory webhook delivery ID deduplication with TTL eviction."""
from __future__ import annotations

import asyncio
import time

import structlog

logger = structlog.get_logger()


class DedupGuard:
    """Guards against duplicate webhook processing within a 5-minute TTL window."""

    TTL_SECONDS: float = 300.0  # 5 minutes per AD-3

    def __init__(self) -> None:
        self._seen: dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def is_duplicate(self, delivery_id: str) -> bool:
        """Check if delivery_id was already seen within TTL.

        Registers the ID if not a duplicate.
        Returns True if duplicate (should be rejected), False if new (should be processed).
        """
        if not delivery_id:
            return False
        async with self._lock:
            self._evict_expired()
            if delivery_id in self._seen:
                logger.debug(
                    "dedup_duplicate_detected",
                    delivery_id=delivery_id,
                )
                return True
            self._seen[delivery_id] = time.monotonic()
            return False

    def _evict_expired(self) -> None:
        """Remove expired entries. Call inside lock only."""
        now = time.monotonic()
        self._seen = {
            k: v for k, v in self._seen.items()
            if now - v <= self.TTL_SECONDS
        }


_guard = DedupGuard()


async def is_duplicate(delivery_id: str) -> bool:
    """Module-level proxy for the singleton DedupGuard."""
    return await _guard.is_duplicate(delivery_id)
