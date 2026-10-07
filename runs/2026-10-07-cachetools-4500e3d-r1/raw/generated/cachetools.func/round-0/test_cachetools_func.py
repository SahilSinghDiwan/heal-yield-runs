import random
import time

import pytest

import cachetools.func as func


def make_counter():
    """Return a function that records each call and returns a predictable value."""
    calls = []

    def inner(x):
        calls.append(x)
        # return something that depends on call order to detect recomputation
        return f"{x}-{len(calls)}"

    inner.calls = calls
    return inner


def test_cache_parameters_reflect_arguments():
    @func.lru_cache(maxsize=10, typed=True)
    def foo(x):
        return x

    params = foo.cache_parameters()
    assert params == {"maxsize": 10, "typed": True}


def test_typed_flag_affects_key():
    counter = make_counter()

    @func.lru_cache(maxsize=2, typed=False)
    def f(x):
        return counter(x)

    # First call with int 1
    result1 = f(1)
    # Second call with bool True (hash(True) == 1) should hit the same cache entry
    result2 = f(True)

    assert result1 == result2
    # Only one underlying call recorded
    assert len(counter.calls) == 1

    # Now with typed=True, they should be distinct
    counter2 = make_counter()

    @func.lru_cache(maxsize=2, typed=True)
    def g(x):
        return counter2(x)

    r1 = g(1)
    r2 = g(True)

    assert r1 != r2
    assert len(counter2.calls) == 2


def test_fifo_cache_eviction():
    counter = make_counter()

    @func.fifo_cache(maxsize=2)
    def f(x):
        return counter(x)

    # Fill cache with two entries
    assert f(1) == "1-1"
    assert f(2) == "2-2"
    # Cache is full; next insertion should evict the oldest (key 1)
    assert f(3) == "3-3"
    # Calling 1 again should recompute
    assert f(1) == "1-4"
    # Verify call count matches expected recomputations
    assert len(counter.calls) == 4
    # The cache now contains keys 3 and 1; 2 should have been evicted earlier
    assert f(2) == "2-5"
    assert len(counter.calls) == 5


def test_lru_cache_eviction():
    counter = make_counter()

    @func.lru_cache(maxsize=2)
    def f(x):
        return counter(x)

    # Populate cache
    assert f(1) == "1-1"
    assert f(2) == "2-2"
    # Access 1 to make it most-recently used
    assert f(1) == "1-1"
    # Insert new key, should evict least-recently used (key 2)
    assert f(3) == "3-3"
    # 2 should be recomputed
    assert f(2) == "2-4"
    assert len(counter.calls) == 4


def test_rr_cache_deterministic_eviction():
    # Use a deterministic choice function that always picks the first element
    deterministic_choice = lambda seq: seq[0]

    counter = make_counter()

    @func.rr_cache(maxsize=2, choice=deterministic_choice)
    def f(x):
        return counter(x)

    # Fill cache
    assert f(1) == "1-1"
    assert f(2) == "2-2"
    # Insert third key; deterministic choice evicts the first key (1)
    assert f(3) == "3-3"
    # 1 should be recomputed
    assert f(1) == "1-4"
    assert len(counter.calls) == 4


def test_ttl_cache_expiration():
    class FakeTimer:
        def __init__(self):
            self._t = 0.0

        def __call__(self):
            return self._t

        def advance(self, delta):
            self._t += delta

    timer = FakeTimer()
    ttl_seconds = 5

    counter = make_counter()

    @func.ttl_cache(maxsize=2, ttl=ttl_seconds, timer=timer)
    def f(x):
        return counter(x)

    # First call caches the result
    assert f(1) == "1-1"
    # Second call before TTL expires hits cache
    assert f(1) == "1-1"
    assert len(counter.calls) == 1

    # Advance time beyond TTL
    timer.advance(ttl_seconds + 1)

    # Now the entry should be expired and recomputed
    assert f(1) == "1-2"
    assert len(counter.calls) == 2


def test_unbounded_cache_when_maxsize_none():
    counter = make_counter()

    @func.lru_cache(maxsize=None)
    def f(x):
        return counter(x)

    # Call with many distinct arguments
    for i in range(20):
        assert f(i) == f"{i}-{i+1}"
    # All calls should be cached; no recomputation
    for i in range(20):
        assert f(i) == f"{i}-{i+1}"
    # Call count should equal number of distinct arguments (20)
    assert len(counter.calls) == 20
