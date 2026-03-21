"""Tests for DedupGuard — in-memory webhook delivery ID deduplication with TTL eviction."""
import time

from d1ff.webhook.dedup_guard import DedupGuard


async def test_first_delivery_not_duplicate() -> None:
    """First time a delivery_id is seen, it is NOT a duplicate."""
    guard = DedupGuard()
    result = await guard.is_duplicate("abc-123")
    assert result is False


async def test_second_delivery_is_duplicate() -> None:
    """Second call with same delivery_id returns True (duplicate)."""
    guard = DedupGuard()
    first = await guard.is_duplicate("abc-123")
    second = await guard.is_duplicate("abc-123")
    assert first is False
    assert second is True


async def test_different_delivery_ids_not_duplicate() -> None:
    """Different delivery IDs are both not duplicates."""
    guard = DedupGuard()
    result1 = await guard.is_duplicate("id-1")
    result2 = await guard.is_duplicate("id-2")
    assert result1 is False
    assert result2 is False


async def test_expired_delivery_not_duplicate() -> None:
    """Delivery ID past TTL is treated as fresh (not a duplicate)."""
    guard = DedupGuard()
    # Register the ID first
    await guard.is_duplicate("old-id")
    # Manually set timestamp to past TTL
    guard._seen["old-id"] = time.monotonic() - 301
    # Should not be a duplicate — expired
    result = await guard.is_duplicate("old-id")
    assert result is False


async def test_within_ttl_is_duplicate() -> None:
    """Delivery ID within TTL is still a duplicate."""
    guard = DedupGuard()
    # Register the ID
    await guard.is_duplicate("fresh-id")
    # Manually set timestamp to just within TTL
    guard._seen["fresh-id"] = time.monotonic() - 299
    # Should still be a duplicate
    result = await guard.is_duplicate("fresh-id")
    assert result is True


async def test_eviction_removes_expired_entries() -> None:
    """Calling is_duplicate evicts expired entries from _seen."""
    guard = DedupGuard()
    # Populate with 3 entries
    await guard.is_duplicate("id-a")
    await guard.is_duplicate("id-b")
    await guard.is_duplicate("id-c")
    # Expire 2 of them
    guard._seen["id-a"] = time.monotonic() - 301
    guard._seen["id-b"] = time.monotonic() - 310
    # Trigger eviction by calling is_duplicate on any entry
    await guard.is_duplicate("id-c")
    # Only id-c should remain (plus the just-checked one is already there)
    assert "id-a" not in guard._seen
    assert "id-b" not in guard._seen
    assert "id-c" in guard._seen


async def test_empty_delivery_id_not_registered() -> None:
    """Empty delivery_id returns False and is NOT stored in _seen."""
    guard = DedupGuard()
    result = await guard.is_duplicate("")
    assert result is False
    assert "" not in guard._seen
