import time
import random

import pytest

import cachetools.func as func


def make_counter():
    """Utility to create a simple counter function that records call count."""
    calls = {"cnt": 0}

    def f(x):
        calls["cnt"] += 1
        return x * 2

    f.calls = calls
    return f


def test_fifo_cache_eviction():
    f = make_counter()
    cached_f = func.fifo_cache(maxsize=2)(f)

    # Populate cache
    assert cached_f("a") == "aa"
    assert cached_f("b") == "bb"
    assert f.calls["cnt"] == 2

    # Insert new key, should evict the oldest entry ('a')
    assert cached_f("c") == "cc"
    assert f.calls["cnt"] == 3

    # 'a' should be recomputed because it was evicted
    assert cached_f("a") == "aa"
    assert f.calls["cnt"] == 4


def test_lru_cache_eviction():
    f = make_counter()
    cached_f = func.lru_cache(maxsize=2)(f)

    # Populate cache
    assert cached_f("a") == "aa"
    assert cached_f("b") == "bb"
    assert f.calls["cnt"] == 2

    # Access 'a' to make it most-recently used
    assert cached_f("a") == "aa"
    assert f.calls["cnt"] == 2  # still cached

    # Insert new key, should evict the *least* recently used entry ('b')
    assert cached_f("c") == "cc"
    assert f.calls["cnt"] == 3

    # 'b' should be recomputed because it was evicted
    assert cached_f("b") == "bb"
    assert f.calls["cnt"] == 4


def test_lfu_cache_eviction():
    f = make_counter()
    cached_f = func.lfu_cache(maxsize=2)(f)

    # Populate cache
    assert cached_f("a") == "aa"
    assert cached_f("b") == "bb"
    assert f.calls["cnt"] == 2

    # Access 'a' again to increase its frequency
    assert cached_f("a") == "aa"
    assert f.calls["cnt"] == 2

    # Insert new key, should evict the least frequently used entry ('b')
    assert cached_f("c") == "cc"
    assert f.calls["cnt"] == 3

    # 'b' should be recomputed because it was evicted
    assert cached_f("b") == "bb"
    assert f.calls["cnt"] == 4


def test_rr_cache_deterministic_replacement():
    # deterministic choice: always pick the first key in the internal list
    def deterministic_choice(seq):
        return seq[0]

    f = make_counter()
    cached_f = func.rr_cache(maxsize=2, choice=deterministic_choice)(f)

    # Populate cache
    assert cached_f("a") == "aa"
    assert cached_f("b") == "bb"
    assert f.calls["cnt"] == 2

    # Insert new key; deterministic_choice will evict the first inserted key ('a')
    assert cached_f("c") == "cc"
    assert f.calls["cnt"] == 3

    # 'a' should be recomputed because it was evicted
    assert cached_f("a") == "aa"
    assert f.calls["cnt"] == 4


def test_ttl_cache_expiration():
    # Use a controllable timer
    start = time.monotonic()
    timer = lambda: start + timer.offset
    timer.offset = 0.0

    f = make_counter()
    cached_f = func.ttl_cache(maxsize=2, ttl=1, timer=timer)(f)

    # First call caches the result
    assert cached_f("a") == "aa"
    assert f.calls["cnt"] == 1

    # Within TTL, result should be cached
    timer.offset = 0.5
    assert cached_f("a") == "aa"
    assert f.calls["cnt"] == 1

    # After TTL expires, result should be recomputed
    timer.offset = 1.5
    assert cached_f("a") == "aa"
    assert f.calls["cnt"] == 2


def test_typed_cache_separates_int_and_float():
    f = make_counter()
    cached_f = func.lru_cache(maxsize=2, typed=True)(f)

    # int and float with same numeric value should be cached separately
    assert cached_f(1) == 2
    assert cached_f(1.0) == 2.0
    assert f.calls["cnt"] == 2

    # Repeating calls should not increase count
    assert cached_f(1) == 2
    assert cached_f(1.0) == 2.0
    assert f.calls["cnt"] == 2


def test_unbounded_cache_parameters():
    f = make_counter()
    # maxsize=None creates an unbounded cache (no eviction)
    cached_f = func.lru_cache(maxsize=None)(f)

    # Verify that cache_parameters reports None for maxsize
    params = cached_f.cache_parameters()
    assert params["maxsize"] is None
    assert params["typed"] is False

    # Populate many entries without eviction
    for i in range(100):
        assert cached_f(i) == i * 2
    assert f.calls["cnt"] == 100
