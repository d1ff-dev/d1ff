"""In-memory cache for repository listings with TTL."""

import time
from typing import Any


class RepoCache:
    def __init__(self, ttl_seconds: int = 300) -> None:
        self._ttl = ttl_seconds
        self._store: dict[int, tuple[float, list[dict[str, Any]]]] = {}

    def get(self, user_id: int) -> list[dict[str, Any]] | None:
        entry = self._store.get(user_id)
        if entry is None:
            return None
        timestamp, repos = entry
        if time.monotonic() - timestamp >= self._ttl:
            del self._store[user_id]
            return None
        return repos

    def set(self, user_id: int, repos: list[dict[str, Any]]) -> None:
        self._store[user_id] = (time.monotonic(), repos)

    def invalidate(self, user_id: int) -> None:
        self._store.pop(user_id, None)
