import time
import random

import pytest

import cachetools.func as func


def test_fifo_cache_basic_eviction():
    """FIFO cache should evict the oldest entry when maxsize is exceeded."""
    calls = []

    @func.fifo_cache(maxsize=2)
    def square(x):
        calls.append(x)
        return x * x

    # Fill cache with two entries
    assert square(2) == 4
    assert square(3) == 9
    assert calls == [2, 3]

    # Cache hit for existing entry; no new call
    assert square(2) == 4
    assert calls == [2, 3]

    # Adding a third distinct key evicts the first (2)
    assert square(4) == 16
    assert calls == [2, 3, 4]

    # The evicted entry is recomputed
    assert square(2) == 4
    assert calls == [2, 3, 4, 2]


def test_unbounded_cache_grows_without_limit():
    """When maxsize=None the cache should grow without bound."""
    @func.fifo_cache(maxsize=None)
    def identity(x):
        return x

    # Populate with several distinct keys
    for i in range(10):
        assert identity(i) == i

    # The underlying cache should contain all inserted keys
    # The wrapper created by `cached` stores the cache in the attribute `cache`
    assert len(identity.cache) == 10
    # Ensure all keys are present
    for i in range(10):
        assert i in identity.cache


def test_typed_cache_distinguishes_int_and_float():
    """Typed caches must treat 1 and 1.0 as different keys."""
    calls = []

    @func.lru_cache(maxsize=4, typed=True)
    def inc(x):
        calls.append(x)
        return x + 1

    # Call with int and float versions
    assert inc(1) == 2
    assert inc(1.0) == 2.0
    # Both calls should have been recorded separately
    assert calls == [1, 1.0]

    # Subsequent calls hit the cache (no new recordings)
    assert inc(1) == 2
    assert inc(1.0) == 2.0
    assert calls == [1, 1.0]


def test_lru_cache_eviction_order():
    """LRU cache should evict the least‑recently used entry."""
    calls = []

    @func.lru_cache(maxsize=2)
    def double(x):
        calls.append(x)
        return x * 2

    # Populate cache
    assert double(1) == 2
    assert double(2) == 4
    assert calls == [1, 2]

    # Access 1 to make it most‑recently used
    assert double(1) == 2
    assert calls == [1, 2]

    # Adding a new key evicts the least‑recently used (2)
    assert double(3) == 6
    assert calls == [1, 2, 3]

    # 2 was evicted, so a new call recomputes it
    assert double(2) == 4
    assert calls == [1, 2, 3, 2]


def test_ttl_cache_respects_time_to_live():
    """TTL cache should expire entries after the given TTL."""
    # Use a mutable timer that we can advance
    start = [time.monotonic()]

    def timer():
        return start[0]

    calls = []

    @func.ttl_cache(maxsize=2, ttl=0.1, timer=timer)
    def greet(name):
        calls.append(name)
        return f"hi {name}"

    # First call populates the cache
    assert greet("alice") == "hi alice"
    assert calls == ["alice"]

    # Within TTL, result is cached
    assert greet("alice") == "hi alice"
    assert calls == ["alice"]

    # Advance time beyond TTL
    start[0] += 0.2

    # Cache entry should be considered expired and recomputed
    assert greet("alice") == "hi alice"
    assert calls == ["alice", "alice"]


def test_rr_cache_deterministic_eviction():
    """RR cache with a deterministic choice function should evict predictably."""
    # Deterministic choice: always evict the first key in the internal list
    def first_choice(seq):
        return seq[0]

    calls = []

    @func.rr_cache(maxsize=2, choice=first_choice)
    def triple(x):
        calls.append(x)
        return x * 3

    # Fill cache
    assert triple(1) == 3
    assert triple(2) == 6
    assert calls == [1, 2]

    # Adding a third key triggers deterministic eviction (evicts key 1)
    assert triple(3) == 9
    assert calls == [1, 2, 3]

    # Key 1 was evicted, so a new call recomputes it
    assert triple(1) == 3
    assert calls == [1, 2, 3, 1]


def test_decorator_without_parentheses_uses_default_parameters():
    """Using the decorator without parentheses should apply default settings."""
    calls = []

    @func.lru_cache
    def add_one(x):
        calls.append(x)
        return x + 1

    # Default maxsize is 128; a few calls should be cached
    assert add_one(10) == 11
    assert add_one(10) == 11
    assert calls == [10]

    # Verify that the wrapper reports its parameters correctly
    params = add_one.cache_parameters()
    assert params["maxsize"] == 128
    assert params["typed"] is False
