import time
import types

import pytest

import cachetools.func as cachefunc


def test_basic_caching_decorator():
    """A simple function should be cached after the first call."""
    calls = {"count": 0}

    @cachefunc.lru_cache(maxsize=2)
    def inc(x):
        calls["count"] += 1
        return x + 1

    # First call computes the result
    assert inc(1) == 2
    assert calls["count"] == 1

    # Second call with same argument uses cache
    assert inc(1) == 2
    assert calls["count"] == 1

    # Different argument computes again
    assert inc(2) == 3
    assert calls["count"] == 2


def test_maxsize_eviction_lru():
    """LRU cache should evict the least‑recently used entry when full."""
    calls = {"order": []}

    @cachefunc.lru_cache(maxsize=2)
    def f(x):
        calls["order"].append(x)
        return x * 2

    # Fill cache
    assert f(1) == 2
    assert f(2) == 4
    # Cache is full now; order list has two entries
    assert calls["order"] == [1, 2]

    # Access 1 to make it most‑recently used
    assert f(1) == 2
    # Call a new key, causing eviction of 2 (the LRU)
    assert f(3) == 6
    # Now calling 2 should recompute
    assert f(2) == 4
    # The order list should reflect the recomputations
    assert calls["order"] == [1, 2, 1, 3, 2]


def test_typed_flag_separates_int_and_bool():
    """When typed=True, int 1 and bool True are cached separately."""
    calls = {"count": 0}

    @cachefunc.lru_cache(maxsize=2, typed=True)
    def identity(x):
        calls["count"] += 1
        return x

    # int 1
    assert identity(1) == 1
    # bool True (different type) should cause a new call
    assert identity(True) is True
    # Both calls should have been made
    assert calls["count"] == 2

    # Re‑calling int 1 uses cache
    assert identity(1) == 1
    # Count unchanged
    assert calls["count"] == 2


def test_fifo_eviction_order():
    """FIFO cache should evict entries in insertion order."""
    calls = {"order": []}

    @cachefunc.fifo_cache(maxsize=2)
    def g(x):
        calls["order"].append(x)
        return x * 10

    # Insert two items
    assert g(1) == 10
    assert g(2) == 20
    assert calls["order"] == [1, 2]

    # Cache is full; next insertion evicts the first (1)
    assert g(3) == 30
    # Calling 1 again should recompute
    assert g(1) == 10
    assert calls["order"] == [1, 2, 3, 1]


def test_rr_cache_with_deterministic_choice():
    """RR cache with a deterministic choice function should evict predictably."""
    # Deterministic choice: always pick the first key in the list
    deterministic_choice = lambda seq: seq[0]

    calls = {"order": []}

    @cachefunc.rr_cache(maxsize=2, choice=deterministic_choice)
    def h(x):
        calls["order"].append(x)
        return x - 5

    # Fill cache
    assert h(10) == 5
    assert h(20) == 15
    assert calls["order"] == [10, 20]

    # Next insertion triggers eviction of the first key (10)
    assert h(30) == 25
    # Re‑calling 10 should recompute
    assert h(10) == 5
    assert calls["order"] == [10, 20, 30, 10]


def test_ttl_cache_expiration():
    """TTL cache should expire entries after the given ttl."""
    # Use a mutable timer to control time flow
    current_time = [0.0]

    def fake_timer():
        return current_time[0]

    calls = {"count": 0}

    @cachefunc.ttl_cache(maxsize=2, ttl=5, timer=fake_timer)
    def square(x):
        calls["count"] += 1
        return x * x

    # First call caches result
    assert square(3) == 9
    assert calls["count"] == 1

    # Within ttl, cached result is used
    current_time[0] += 3
    assert square(3) == 9
    assert calls["count"] == 1

    # After ttl expires, recompute
    current_time[0] += 3  # total 6 > ttl
    assert square(3) == 9
    assert calls["count"] == 2


def test_none_maxsize_disables_caching():
    """When maxsize=None, the decorator should still cache (no size limit)."""
    calls = {"count": 0}

    @cachefunc.lru_cache(maxsize=None)
    def double(x):
        calls["count"] += 1
        return x * 2

    # First call computes
    assert double(5) == 10
    assert calls["count"] == 1

    # Second call with same argument uses the cache
    assert double(5) == 10
    # Since caching is still active, count remains 1
    assert calls["count"] == 1
