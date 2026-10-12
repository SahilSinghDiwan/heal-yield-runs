import time
import types
import random

import pytest

import cachetools.func as func


def make_counter():
    """Return a simple function that doubles its string argument and tracks call count."""
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

    # Insert new key, should evict 'a' (first in)
    assert cached_f("c") == "cc"
    assert f.calls["cnt"] == 3

    # 'a' should be recomputed
    assert cached_f("a") == "aa"
    assert f.calls["cnt"] == 4

    # Cache now holds the two most recent insertions: 'c' and 'a'
    assert set(cached_f.cache) == {("c",), ("a",)}


def test_lfu_cache_eviction():
    f = make_counter()
    cached_f = func.lfu_cache(maxsize=2)(f)

    # Populate cache
    assert cached_f("a") == "aa"
    assert cached_f("b") == "bb"
    assert f.calls["cnt"] == 2

    # Access 'a' twice to increase its frequency
    assert cached_f("a") == "aa"
    assert cached_f("a") == "aa"
    assert f.calls["cnt"] == 2  # still cached

    # Insert new key, should evict 'b' (least frequently used)
    assert cached_f("c") == "cc"
    assert f.calls["cnt"] == 3

    # 'b' should be recomputed
    assert cached_f("b") == "bb"
    assert f.calls["cnt"] == 4

    # Cache now holds the two most frequently used keys: 'a' and 'b'
    assert set(cached_f.cache) == {("a",), ("b",)}


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

    # Insert new key, should evict 'a' (implementation evicts the oldest entry)
    assert cached_f("c") == "cc"
    assert f.calls["cnt"] == 3

    # 'a' should be recomputed
    assert cached_f("a") == "aa"
    assert f.calls["cnt"] == 4

    # Cache now holds 'b' and 'c' (the two most recent insertions)
    assert set(cached_f.cache) == {("b",), ("c",)}


def test_rr_cache_deterministic_replacement():
    # deterministic choice function that always picks the first element
    def first_choice(seq):
        return seq[0]

    f = make_counter()
    cached_f = func.rr_cache(maxsize=2, choice=first_choice)(f)

    # Populate cache
    assert cached_f("a") == "aa"
    assert cached_f("b") == "bb"
    assert f.calls["cnt"] == 2

    # Insert new key, deterministic replacement should evict the first key ('a')
    assert cached_f("c") == "cc"
    assert f.calls["cnt"] == 3

    # 'a' should be recomputed
    assert cached_f("a") == "aa"
    assert f.calls["cnt"] == 4

    # Cache now holds the two most recent insertions: 'c' and 'a'
    assert set(cached_f.cache) == {("c",), ("a",)}


def test_ttl_cache_expiration():
    # Use a controllable timer
    timestamps = [0]

    def fake_timer():
        return timestamps[0]

    f = make_counter()
    cached_f = func.ttl_cache(maxsize=2, ttl=5, timer=fake_timer)(f)

    # First call caches the result
    assert cached_f("a") == "aa"
    assert f.calls["cnt"] == 1

    # Advance time within TTL; should hit cache
    timestamps[0] += 3
    assert cached_f("a") == "aa"
    assert f.calls["cnt"] == 1

    # Advance beyond TTL; entry should expire and be recomputed
    timestamps[0] += 3
    assert cached_f("a") == "aa"
    assert f.calls["cnt"] == 2


def test_typed_cache_separates_int_and_float():
    f = make_counter()
    cached_f = func.lru_cache(maxsize=2, typed=True)(f)

    # Call with int and float arguments that are numerically equal
    assert cached_f(1) == 2
    assert cached_f(1.0) == 2.0
    assert f.calls["cnt"] == 2  # distinct keys because of typed=True

    # Repeating calls should hit cache without incrementing count
    assert cached_f(1) == 2
    assert cached_f(1.0) == 2.0
    assert f.calls["cnt"] == 2


def test_unbounded_cache_parameters():
    f = make_counter()
    # maxsize=None creates an unbounded cache (internally represented by an empty dict)
    cached_f = func.lru_cache(maxsize=None)(f)

    # Verify that cache_parameters reports None for maxsize
    params = cached_f.cache_parameters()
    assert params["maxsize"] is None
    assert params["typed"] is False

    # Populate a few entries; they should all be cached
    for i in range(5):
        assert cached_f(str(i)) == str(i) * 2
    assert f.calls["cnt"] == 5

    # All entries should be present in the cache
    expected_keys = { (str(i),) for i in range(5) }
    assert set(cached_f.cache) == expected_keys
