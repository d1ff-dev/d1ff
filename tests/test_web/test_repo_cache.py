"""Tests for in-memory repository cache."""

import time

from d1ff.web.repo_cache import RepoCache


def test_get_returns_none_for_missing_key() -> None:
    cache = RepoCache(ttl_seconds=300)
    assert cache.get(user_id=1) is None


def test_set_and_get() -> None:
    cache = RepoCache(ttl_seconds=300)
    repos = [{"name": "repo1", "full_name": "org/repo1", "installation_id": 1, "private": False}]
    cache.set(user_id=1, repos=repos)
    result = cache.get(user_id=1)
    assert result == repos


def test_expired_entry_returns_none() -> None:
    cache = RepoCache(ttl_seconds=0)  # immediate expiry
    cache.set(user_id=1, repos=[{"name": "repo1"}])
    time.sleep(0.01)
    assert cache.get(user_id=1) is None


def test_invalidate() -> None:
    cache = RepoCache(ttl_seconds=300)
    cache.set(user_id=1, repos=[{"name": "repo1"}])
    cache.invalidate(user_id=1)
    assert cache.get(user_id=1) is None
