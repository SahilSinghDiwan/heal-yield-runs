import builtins
import types
import pytest
import time

from cachetools import func


def make_counter():
    """Return a function that counts how many times it has been called."""
    calls = {"cnt": 0}

    def inner(x):
        calls["cnt"] += 1
        return x * 2

    inner.calls = calls
    return inner


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

    # The cache should contain keys 3 and 1 (most recent two)
    assert set(cached_f.cache) == {3, 1}


def test_lru_cache_eviction():
    f = make_counter()
    cached_f = func.lru_cache(maxsize=2)(f)

    # Populate cache
    assert cached_f('a') == 'aa'
    assert cached_f('b') == 'bb'
    assert f.calls["cnt"] == 2

    # Access 'a' to make it most-recently used
    assert cached_f('a') == 'aa'
    assert f.calls["cnt"] == 2  # still cached

    # Insert new key, should evict 'b' (least recently used)
    assert cached_f('c') == 'cc'
    assert f.calls["cnt"] == 3

    # 'b' should be recomputed
    assert cached_f('b') == 'bb'
    assert f.calls["cnt"] == 4

    # Cache now holds 'a' and 'b'
    assert set(cached_f.cache) == {'a', 'b'}


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

    # Cache now holds 10 and 20
    assert set(cached_f.cache) == {10, 20}


def test_rr_cache_deterministic_replacement():
    # deterministic choice: always evict the first key in the internal dict order
    def deterministic_choice(seq):
        # seq is a sequence of keys; pick the first
        return seq[0]

    f = make_counter()
    cached_f = func.rr_cache(maxsize=2, choice=deterministic_choice)(f)

    # Fill cache
    assert cached_f('x') == 'xx'
    assert cached_f('y') == 'yy'
    assert f.calls["cnt"] == 2

    # Insert third key; deterministic_choice will evict the first key ('x')
    assert cached_f('z') == 'zz'
    assert f.calls["cnt"] == 3

    # 'x' should be recomputed
    assert cached_f('x') == 'xx'
    assert f.calls["cnt"] == 4

    # Cache now contains 'y' and 'x' (order may vary, but both present)
    assert set(cached_f.cache) == {'y', 'x'}


def test_ttl_cache_expiration():
    # Custom timer that we can control
    class Timer:
        def __init__(self):
            self.now = 0.0

        def __call__(self):
            return self.now

        def advance(self, seconds):
            self.now += seconds

    timer = Timer()
    f = make_counter()
    # ttl = 5 seconds, maxsize 2
    cached_f = func.ttl_cache(maxsize=2, ttl=5, timer=timer)(f)

    # First call caches result
    assert cached_f(5) == 10
    assert f.calls["cnt"] == 1

    # Within ttl, should be cached
    timer.advance(3)
    assert cached_f(5) == 10
    assert f.calls["cnt"] == 1

    # After ttl expires, should recompute
    timer.advance(3)  # total 6 > ttl
    assert cached_f(5) == 10
    assert f.calls["cnt"] == 2

    # Ensure other key is cached independently
    assert cached_f(7) == 14
    assert f.calls["cnt"] == 3
    timer.advance(4)
    # 7 still within ttl (4 < 5)
    assert cached_f(7) == 14
    assert f.calls["cnt"] == 3


def test_typed_cache_separates_int_and_float():
    f = make_counter()
    cached_f = func.lru_cache(maxsize=2, typed=True)(f)

    # Call with int and float that are numerically equal
    assert cached_f(1) == 2
    assert cached_f(1.0) == 2.0
    # Two separate calls should have been made because of typed=True
    assert f.calls["cnt"] == 2

    # Repeating the same types should hit cache
    assert cached_f(1) == 2
    assert cached_f(1.0) == 2.0
    assert f.calls["cnt"] == 2

    # Cache should contain both keys (int 1 and float 1.0)
    # The underlying cache keys are the raw arguments; we just check size
    assert len(cached_f.cache) == 2


def test_unbounded_cache_parameters():
    # maxsize=None returns a wrapper with unbounded cache
    f = make_counter()
    cached_f = func.lru_cache(maxsize=None)(f)

    # The wrapper should expose cache_parameters reflecting None maxsize
    params = cached_f.cache_parameters()
    assert params["maxsize"] is None
    assert params["typed"] is False

    # Calls should be cached indefinitely (no eviction)
    for i in range(5):
        assert cached_f(i) == i * 2
    # Only 5 calls to underlying function
    assert f.calls["cnt"] == 5

    # Repeating the same arguments should not increase call count
    for i in range(5):
        assert cached_f(i) == i * 2
    assert f.calls["cnt"] == 5
