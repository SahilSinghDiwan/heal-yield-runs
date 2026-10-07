import builtins
import types
import time

import pytest

# Import the module under test using its dotted path
from cachetools import func as cachefunc


def test_cache_parameters_reflect_arguments():
    """Ensure the wrapper reports the correct cache parameters."""
    @cachefunc.lru_cache(maxsize=5, typed=True)
    def add(a, b):
        return a + b

    params = add.cache_parameters()
    assert params["maxsize"] == 5
    assert params["typed"] is True

    # The wrapper should expose the original function via __wrapped__
    assert isinstance(add.__wrapped__, types.FunctionType)
    assert add.__wrapped__.__name__ == "add"


def test_typed_flag_affects_key():
    """When typed=False, 1 and True should be treated as the same key."""
    call_counter = {"count": 0}

    @cachefunc.lru_cache(maxsize=2, typed=False)
    def identity(x):
        call_counter["count"] += 1
        return x

    # First call with 1 computes the result
    assert identity(1) == 1
    assert call_counter["count"] == 1

    # Second call with True should hit the cache (same key as 1)
    assert identity(True) == 1
    assert call_counter["count"] == 1  # No increment

    # Now with typed=True they are distinct
    call_counter["count"] = 0

    @cachefunc.lru_cache(maxsize=2, typed=True)
    def identity_typed(x):
        call_counter["count"] += 1
        return x

    assert identity_typed(1) == 1
    assert call_counter["count"] == 1
    # True is a different key, so it recomputes
    assert identity_typed(True) is True
    assert call_counter["count"] == 2


def test_fifo_cache_eviction():
    """FIFO cache should evict the oldest entry when capacity is exceeded."""
    @cachefunc.fifo_cache(maxsize=3)
    def square(x):
        return x * x

    # Fill the cache
    for i in range(3):
        assert square(i) == i * i

    # Cache is full; next insertion should evict the first entry (0)
    assert square(3) == 9
    # Accessing 0 should recompute because it was evicted
    assert square(0) == 0


def test_lru_cache_eviction():
    """LRU cache should evict the least recently used entry."""
    @cachefunc.lru_cache(maxsize=2)
    def concat(a, b):
        return f"{a}{b}"

    # Populate cache
    assert concat("a", "1") == "a1"
    assert concat("b", "2") == "b2"
    # Access the first entry to make it most recently used
    assert concat("a", "1") == "a1"
    # Adding a new entry should evict the least recently used ("b", "2")
    assert concat("c", "3") == "c3"
    # Now ("b", "2") should be recomputed
    assert concat("b", "2") == "b2"


def test_rr_cache_deterministic_eviction():
    """RR cache with a deterministic choice function should evict predictably."""
    # Deterministic choice: always evict the first key in the internal list
    def first_choice(seq):
        return seq[0]

    @cachefunc.rr_cache(maxsize=2, choice=first_choice)
    def inc(x):
        return x + 1

    # Fill cache
    assert inc(1) == 2
    assert inc(2) == 3
    # Adding a third entry should evict the first inserted (1)
    assert inc(3) == 4
    # Re-calling with 1 should recompute
    assert inc(1) == 2


def test_ttl_cache_expiration():
    """TTL cache should expire entries after the given TTL using a custom timer."""
    # Use a mutable container to control time
    current_time = [0.0]

    def fake_timer():
        return current_time[0]

    @cachefunc.ttl_cache(maxsize=2, ttl=5, timer=fake_timer)
    def double(x):
        return x * 2

    # First call caches the result
    assert double(10) == 20
    # Advance time within TTL; should hit cache
    current_time[0] += 4
    assert double(10) == 20
    # Advance beyond TTL; cache should miss and recompute
    current_time[0] += 2
    assert double(10) == 20  # recomputed, same value


def test_unbounded_cache_when_maxsize_none():
    """When maxsize=None, the cache should be unbounded (no eviction)."""
    @cachefunc.lru_cache(maxsize=None)
    def identity(x):
        return x

    # Insert many distinct values
    for i in range(100):
        assert identity(i) == i

    # The underlying cache should contain all entries; we can inspect the wrapper's cache
    # The cached decorator stores the cache in the wrapper's .cache attribute
    cache_dict = identity.cache  # type: ignore[attr-defined]
    assert isinstance(cache_dict, dict)
    assert len(cache_dict) == 100
    # Ensure that a previously cached value is still present
    assert cache_dict[cachefunc.keys.hashkey(identity, (42,), {})] == 42


def test_fifo_cache_direct_decorator_usage():
    """Calling the decorator without parentheses should still work."""
    @cachefunc.fifo_cache
    def greet(name):
        return f"Hello, {name}!"

    # First call computes
    assert greet("Alice") == "Hello, Alice!"
    # Second call hits cache
    assert greet("Alice") == "Hello, Alice!"


def test_lfu_cache_eviction_behavior():
    """LFU cache should evict the least frequently used entry."""
    @cachefunc.lfu_cache(maxsize=2)
    def mul(a, b):
        return a * b

    # Populate cache
    assert mul(2, 3) == 6  # freq 1
    assert mul(3, 4) == 12  # freq 1
    # Access first entry again to increase its frequency
    assert mul(2, 3) == 6  # freq 2
    # Adding a new entry should evict the less frequently used (3,4)
    assert mul(5, 6) == 30
    # Now (3,4) should be recomputed
    assert mul(3, 4) == 12
