import time
import pytest
from cachetools import func as func


def make_counter():
    """Return a simple counter function that records how many times it was called."""
    calls = {"cnt": 0}

    def f(x):
        calls["cnt"] += 1
        # Return a deterministic value based on the input type
        if isinstance(x, str):
            return x * 2
        return x * 2

    f.calls = calls
    return f


def test_fifo_cache_eviction():
    f = make_counter()
    # maxsize 2 FIFO
    cached_f = func.fifo_cache(maxsize=2)(f)

    # Fill cache with two distinct keys
    assert cached_f(1) == 2
    assert cached_f(2) == 4
    # No extra calls yet
    assert f.calls["cnt"] == 2

    # Access first key again – should be cached (no new call)
    assert cached_f(1) == 2
    assert f.calls["cnt"] == 2

    # Insert third key, causing eviction of the *first* inserted key (1)
    assert cached_f(3) == 6
    assert f.calls["cnt"] == 3

    # Now key 1 should be recomputed (evicted)
    assert cached_f(1) == 2
    assert f.calls["cnt"] == 4

    # The cache stores argument tuples as keys
    assert set(cached_f.cache) == {(3,), (1,)}


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

    # Insert new key, should evict 'b' (least recently used)
    assert cached_f("c") == "cc"
    assert f.calls["cnt"] == 3

    # 'b' should be recomputed
    assert cached_f("b") == "bb"
    assert f.calls["cnt"] == 4

    # Cache now holds 'a' and 'b' (as argument tuples)
    assert set(cached_f.cache) == {("a",), ("b",)}


def test_lfu_cache_eviction():
    f = make_counter()
    cached_f = func.lfu_cache(maxsize=2)(f)

    # Insert two keys
    assert cached_f(10) == 20
    assert cached_f(20) == 40
    assert f.calls["cnt"] == 2

    # Access 10 again – frequency of 10 becomes 2
    assert cached_f(10) == 20
    assert f.calls["cnt"] == 2

    # Insert third key, LFU should evict 20 (freq 1)
    assert cached_f(30) == 60
    assert f.calls["cnt"] == 3

    # 20 should be recomputed
    assert cached_f(20) == 40
    assert f.calls["cnt"] == 4

    # Cache now holds 10 and 20 (as argument tuples)
    assert set(cached_f.cache) == {(10,), (20,)}


def test_rr_cache_deterministic_replacement():
    # deterministic choice: always evict the first key in the internal dict order
    def deterministic_choice(seq):
        # seq is a sequence of keys; pick the first
        return seq[0]

    f = make_counter()
    cached_f = func.rr_cache(maxsize=2, choice=deterministic_choice)(f)

    # Fill cache
    assert cached_f("x") == "xx"
    assert cached_f("y") == "yy"
    assert f.calls["cnt"] == 2

    # Insert third key; deterministic_choice will evict the first key according to RRCache's policy
    assert cached_f("z") == "zz"
    assert f.calls["cnt"] == 3

    # 'x' should be recomputed (it was evicted)
    assert cached_f("x") == "xx"
    assert f.calls["cnt"] == 4

    # Cache now contains 'x' and 'z' (as argument tuples)
    assert set(cached_f.cache) == {("x",), ("z",)}


def test_ttl_cache_expiration():
    # Use a controllable timer
    current = [0.0]

    def fake_timer():
        return current[0]

    f = make_counter()
    cached_f = func.ttl_cache(maxsize=2, ttl=1, timer=fake_timer)(f)

    # First call caches the result
    assert cached_f(5) == 10
    assert f.calls["cnt"] == 1

    # Within TTL, should hit cache
    current[0] += 0.5
    assert cached_f(5) == 10
    assert f.calls["cnt"] == 1

    # After TTL expires, should recompute
    current[0] += 0.6
    assert cached_f(5) == 10
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
    cached_f = func.lru_cache(maxsize=None)(f)

    # The wrapper should expose cache_parameters with maxsize None
    params = cached_f.cache_parameters()
    assert params["maxsize"] is None
    assert params["typed"] is False
