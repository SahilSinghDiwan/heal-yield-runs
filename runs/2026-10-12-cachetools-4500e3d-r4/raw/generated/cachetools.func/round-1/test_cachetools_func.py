import pytest
import cachetools.func as cachefunc


def test_fifo_cache_eviction():
    """FIFO cache should evict entries when maxsize is exceeded."""
    calls = {"cnt": 0}

    @cachefunc.fifo_cache(maxsize=2)
    def f(x):
        calls["cnt"] += 1
        return calls["cnt"]

    # Fill the cache with two distinct keys
    assert f(1) == 1  # first call, computes
    assert f(2) == 2  # second call, computes
    assert calls["cnt"] == 2  # no extra calls

    # Cached results should be returned without extra calls
    assert f(1) == 1
    assert f(2) == 2
    assert calls["cnt"] == 2

    # Insert a third key, causing eviction (implementation may evict any entry)
    assert f(3) == 3
    assert calls["cnt"] == 3

    # Both previous keys may have been evicted; ensure they recompute
    prev_cnt = calls["cnt"]
    f(1)
    assert calls["cnt"] == prev_cnt + 1
    prev_cnt = calls["cnt"]
    f(2)
    assert calls["cnt"] == prev_cnt + 1


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

    # Access key 1 twice to make it more frequent
    assert f(1) == 1
    assert f(1) == 1
    assert calls["cnt"] == 2

    # Adding a new key should evict key 2 (least frequently used)
    assert f(3) == 3
    assert calls["cnt"] == 3

    # Key 2 must be recomputed
    assert f(2) == 4
    assert calls["cnt"] == 4

    # Key 1 should still be cached
    assert f(1) == 1
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

    # Key 1 may have been evicted depending on implementation; ensure recompute works
    prev_cnt = calls["cnt"]
    f(1)
    assert calls["cnt"] == prev_cnt + 1


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

    # Adding a third key evicts one of the existing keys (deterministic_choice picks first)
    assert f(3) == 3
    assert calls["cnt"] == 3

    # Both previous keys may have been evicted; ensure they recompute
    prev_cnt = calls["cnt"]
    f(1)
    assert calls["cnt"] == prev_cnt + 1
    prev_cnt = calls["cnt"]
    f(2)
    assert calls["cnt"] == prev_cnt + 1


def test_ttl_cache_expiration():
    """TTL cache should expire entries after the given TTL."""
    calls = {"cnt": 0}
    fake_time = [0.0]

    def timer():
        return fake_time[0]

    @cachefunc.ttl_cache(maxsize=2, ttl=5, timer=timer)
    def f(x):
        calls["cnt"] += 1
        return calls["cnt"]

    # Populate cache
    assert f(1) == 1
    assert f(2) == 2
    assert calls["cnt"] == 2

    # Within TTL, cached values are returned
    assert f(1) == 1
    assert f(2) == 2
    assert calls["cnt"] == 2

    # Advance time beyond TTL
    fake_time[0] += 6

    # Values should be recomputed after expiration
    assert f(1) == 3
    assert f(2) == 4
    assert calls["cnt"] == 4


def test_typed_cache_distinguishes_types():
    """Typed cache should treat arguments of different types as distinct keys."""
    calls = {"cnt": 0}

    @cachefunc.lru_cache(maxsize=2, typed=True)
    def f(x):
        calls["cnt"] += 1
        return calls["cnt"]

    assert f(1) == 1          # int
    assert f(1.0) == 2        # float, distinct because typed=True
    assert f(1) == 1          # cached int
    assert f(1.0) == 2        # cached float
    assert calls["cnt"] == 2


def test_decorator_without_parentheses():
    """Cache decorators should work when used without parentheses."""
    calls = {"cnt": 0}

    @cachefunc.lru_cache
    def f(x):
        calls["cnt"] += 1
        return calls["cnt"]

    assert f(1) == 1
    assert f(1) == 1
    assert calls["cnt"] == 1


def test_unbounded_cache_behaviour():
    """Unbounded cache (maxsize=None) should store all entries."""
    calls = {"cnt": 0}

    @cachefunc.lru_cache(maxsize=None)
    def f(x):
        calls["cnt"] += 1
        return calls["cnt"]

    for i in range(5):
        assert f(i) == i + 1
    # No evictions should have occurred
    assert calls["cnt"] == 5
    # All values should still be cached
    for i in range(5):
        assert f(i) == i + 1
    assert calls["cnt"] == 5
