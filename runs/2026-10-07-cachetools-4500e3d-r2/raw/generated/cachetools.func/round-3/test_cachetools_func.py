import time

import pytest

import cachetools.func as func


def test_fifo_cache_basic_eviction():
    """FIFO cache should evict the oldest entry when maxsize is exceeded."""
    @func.fifo_cache(maxsize=3)
    def square(x):
        return x * x

    # Fill the cache to its limit
    assert square(0) == 0
    assert square(1) == 1
    assert square(2) == 4

    # Cache should now contain three entries
    assert len(square.cache) == 3
    assert (0,) in square.cache
    assert (1,) in square.cache
    assert (2,) in square.cache

    # Adding a fourth entry should evict the first (key 0)
    assert square(3) == 9
    assert len(square.cache) == 3
    assert (0,) not in square.cache
    assert (1,) in square.cache
    assert (2,) in square.cache
    assert (3,) in square.cache


def test_unbounded_cache_grows_without_limit():
    """When maxsize=None the cache should grow without bound."""
    @func.fifo_cache(maxsize=None)
    def identity(x):
        return x

    # Populate with several distinct keys
    for i in range(10):
        assert identity(i) == i

    # The underlying cache should contain all inserted keys
    assert len(identity.cache) == 10
    # Ensure all tuple-keys are present (cachetools stores args as a tuple)
    for i in range(10):
        assert (i,) in identity.cache


def test_typed_cache_distinguishes_int_and_float():
    """Typed caches must treat int and float arguments as distinct keys."""
    @func.fifo_cache(maxsize=4, typed=True)
    def echo(x):
        return x

    # Call with int and float that are numerically equal
    assert echo(1) == 1
    assert echo(1.0) == 1.0

    # Both should be cached separately
    assert len(echo.cache) == 2
    assert (1,) in echo.cache          # int key
    assert (1.0,) in echo.cache        # float key


def test_lru_cache_eviction_order():
    """LRU cache should evict the least-recently-used entry."""
    @func.lru_cache(maxsize=2)
    def double(x):
        return 2 * x

    # Populate cache
    assert double(1) == 2  # cached
    assert double(2) == 4  # cached

    # Access 1 to make 2 the LRU
    assert double(1) == 2

    # Insert a new key, causing eviction of 2
    assert double(3) == 6

    # Verify eviction
    assert (2,) not in double.cache
    assert (1,) in double.cache
    assert (3,) in double.cache


def test_ttl_cache_respects_time_to_live():
    """TTL cache should expire entries after the specified TTL."""
    # Use a controllable timer instead of real time.sleep
    current = [0.0]

    def fake_timer():
        return current[0]

    call_counter = {"count": 0}

    @func.ttl_cache(maxsize=2, ttl=0.5, timer=fake_timer)
    def compute(x):
        call_counter["count"] += 1
        return x * 10

    # First call caches the result
    assert compute(1) == 10
    assert call_counter["count"] == 1
    assert (1,) in compute.cache

    # Advance time within TTL; result should be cached
    current[0] += 0.3
    assert compute(1) == 10
    assert call_counter["count"] == 1  # no recompute

    # Advance time beyond TTL; cache entry should be considered expired
    current[0] += 0.3
    assert compute(1) == 10
    assert call_counter["count"] == 2  # recomputed after expiry


def test_rr_cache_deterministic_eviction():
    """RR cache with a deterministic choice function should evict predictably."""
    # Deterministic choice: always pick the first element
    deterministic_choice = lambda seq: seq[0]

    @func.rr_cache(maxsize=2, choice=deterministic_choice)
    def triple(x):
        return 3 * x

    # Fill cache
    assert triple(1) == 3
    assert triple(2) == 6

    # Insert a third key; deterministic choice should evict key (1,)
    assert triple(3) == 9

    assert (1,) not in triple.cache
    assert (2,) in triple.cache
    assert (3,) in triple.cache


def test_decorator_without_parentheses_uses_default_parameters():
    """Using a cache decorator without parentheses should apply default settings."""
    @func.lru_cache
    def inc(x):
        return x + 1

    # Call a few times; caching should work
    assert inc(5) == 6
    assert inc(5) == 6  # cached result

    # Verify default maxsize (128) is reported
    params = inc.cache_parameters()
    assert params["maxsize"] == 128
    assert params["typed"] is False
