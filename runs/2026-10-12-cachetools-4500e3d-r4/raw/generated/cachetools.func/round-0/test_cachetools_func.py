import builtins
import types

import pytest

# Import the module under test
import cachetools.func as cachefunc


def test_fifo_cache_eviction():
    """FIFO cache should evict the oldest entry when maxsize is exceeded."""
    calls = {"cnt": 0}

    @cachefunc.fifo_cache(maxsize=2)
    def f(x):
        calls["cnt"] += 1
        return calls["cnt"]

    # Fill the cache with two distinct keys
    assert f(1) == 1  # first call, computes
    assert f(2) == 2  # second call, computes
    # Cached results should be returned without extra calls
    assert f(1) == 1
    assert f(2) == 2
    assert calls["cnt"] == 2  # no extra calls

    # Insert a third key, causing eviction of the oldest (key 1)
    assert f(3) == 3
    assert calls["cnt"] == 3

    # Key 1 was evicted, so it must be recomputed
    assert f(1) == 4
    assert calls["cnt"] == 4

    # Key 2 should still be cached
    assert f(2) == 2
    assert calls["cnt"] == 4


def test_lru_cache_eviction():
    """LRU cache should evict the least‑recently used entry."""
    calls = {"cnt": 0}

    @cachefunc.lru_cache(maxsize=2)
    def f(x):
        calls["cnt"] += 1
        return calls["cnt"]

    # Populate cache
    assert f(1) == 1
    assert f(2) == 2
    assert calls["cnt"] == 2

    # Access key 1 to make it most‑recently used
    assert f(1) == 1
    assert calls["cnt"] == 2

    # Adding a new key should evict key 2 (least recently used)
    assert f(3) == 3
    assert calls["cnt"] == 3

    # Key 2 must be recomputed
    assert f(2) == 4
    assert calls["cnt"] == 4

    # Key 1 is still cached
    assert f(1) == 1
    assert calls["cnt"] == 4


def test_lfu_cache_eviction():
    """LFU cache should evict the least‑frequently used entry."""
    calls = {"cnt": 0}

    @cachefunc.lfu_cache(maxsize=2)
    def f(x):
        calls["cnt"] += 1
        return calls["cnt"]

    # Populate cache
    assert f(1) == 1
    assert f(2) == 2
    assert calls["cnt"] == 2

    # Access key 1 twice more (frequency 3) and key 2 once (frequency 2)
    assert f(1) == 1
    assert f(1) == 1
    assert f(2) == 2
    assert calls["cnt"] == 2  # no new calls

    # Insert a new key, causing eviction of the least‑frequently used (key 2)
    assert f(3) == 3
    assert calls["cnt"] == 3

    # Key 2 must be recomputed
    assert f(2) == 4
    assert calls["cnt"] == 4

    # Key 1 remains cached
    assert f(1) == 1
    assert calls["cnt"] == 4


def test_rr_cache_deterministic_eviction():
    """RR cache with a deterministic choice function should evict predictably."""
    calls = {"cnt": 0}
    # deterministic choice: always pick the first element
    deterministic_choice = lambda seq: seq[0]

    @cachefunc.rr_cache(maxsize=2, choice=deterministic_choice)
    def f(x):
        calls["cnt"] += 1
        return calls["cnt"]

    # Fill cache
    assert f(1) == 1
    assert f(2) == 2
    assert calls["cnt"] == 2

    # Adding a third key evicts the first key (1) because deterministic_choice picks it
    assert f(3) == 3
    assert calls["cnt"] == 3

    # Key 1 must be recomputed
    assert f(1) == 4
    assert calls["cnt"] == 4

    # Key 2 should still be cached
    assert f(2) == 2
    assert calls["cnt"] == 4


def test_ttl_cache_expiration():
    """TTL cache should expire entries after the given ttl."""
    calls = {"cnt": 0}
    fake_time = [0.0]

    def timer():
        return fake_time[0]

    @cachefunc.ttl_cache(maxsize=2, ttl=5, timer=timer)
    def f(x):
        calls["cnt"] += 1
        return calls["cnt"]

    # First call caches the result
    assert f(1) == 1
    assert calls["cnt"] == 1

    # Within ttl, result is cached
    fake_time[0] += 4.9
    assert f(1) == 1
    assert calls["cnt"] == 1

    # After ttl expires, entry is recomputed
    fake_time[0] += 0.2  # total 5.1 > ttl
    assert f(1) == 2
    assert calls["cnt"] == 2

    # Verify that other keys are independent
    assert f(2) == 3
    assert calls["cnt"] == 3
    fake_time[0] += 5
    assert f(2) == 4
    assert calls["cnt"] == 4


def test_typed_cache_distinguishes_types():
    """When typed=True, arguments of different types are cached separately."""
    calls = {"cnt": 0}

    @cachefunc.lru_cache(maxsize=4, typed=True)
    def f(x):
        calls["cnt"] += 1
        return (x, type(x), calls["cnt"])

    # int and float with same numeric value should be distinct
    result_int = f(1)
    result_float = f(1.0)

    assert result_int[0] == 1
    assert result_float[0] == 1.0
    assert result_int[2] != result_float[2]  # different call counts
    assert calls["cnt"] == 2

    # Re‑calling with same types should hit cache
    assert f(1) == result_int
    assert f(1.0) == result_float
    assert calls["cnt"] == 2  # no extra calls


def test_decorator_without_parentheses():
    """Passing a callable as the first argument should behave like using the decorator without parentheses."""
    calls = {"cnt": 0}

    @cachefunc.lru_cache
    def f(x):
        calls["cnt"] += 1
        return calls["cnt"]

    # The default maxsize is 128, so caching works
    assert f(10) == 1
    assert f(10) == 1
    assert calls["cnt"] == 1

    # Different argument triggers a new computation
    assert f(20) == 2
    assert calls["cnt"] == 2


def test_unbounded_cache_behaviour():
    """When maxsize=None the cache should be unbounded (no eviction)."""
    calls = {"cnt": 0}

    @cachefunc.lru_cache(maxsize=None)
    def f(x):
        calls["cnt"] += 1
        return calls["cnt"]

    # Populate with more entries than a typical bounded size
    for i in range(10):
        assert f(i) == i + 1

    # All entries should still be cached
    for i in range(10):
        assert f(i) == i + 1

    # Only the first 10 calls should have been made
    assert calls["cnt"] == 10
