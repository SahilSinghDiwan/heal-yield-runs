import threading
import types

import pytest
from cachetools import _cached


def simple_key(*args, **kwargs):
    """Key function that uses the first positional argument."""
    return args[0] if args else None


def info_func(hits, misses):
    """Info function that just returns a tuple."""
    return hits, misses


class ValueErrorCache(dict):
    """A dict that raises ValueError when trying to store a specific sentinel."""

    def __setitem__(self, key, value):
        if value == "too_large":
            raise ValueError("value too large")
        super().__setitem__(key, value)

    def setdefault(self, key, default=None):
        if default == "too_large":
            raise ValueError("value too large")
        return super().setdefault(key, default)


def test_unlocked_cache_basic():
    """Test the unlocked wrapper without lock or info."""
    cache = {}
    calls = []

    def func(x):
        calls.append(x)
        return x * 2

    wrapper = _cached._wrapper(func, cache, simple_key)
    # First call computes
    assert wrapper(3) == 6
    assert calls == [3]
    # Second call hits cache
    assert wrapper(3) == 6
    assert calls == [3]  # no new call
    # Cache contains the result
    assert cache[3] == 6
    # cache_info should be None when no info supplied
    assert wrapper.cache_info is None
    # cache_clear should empty the cache
    wrapper.cache_clear()
    assert cache == {}


def test_locked_cache_hits_and_misses():
    """Test the locked wrapper with a lock and info."""
    lock = threading.Lock()
    cache = {}
    calls = []

    def func(x):
        calls.append(x)
        return x + 1

    wrapper = _cached._wrapper(func, cache, simple_key, lock=lock, info=info_func)
    # First call: miss
    assert wrapper(10) == 11
    assert calls == [10]
    assert wrapper.cache_info() == (0, 1)  # 0 hits, 1 miss
    # Second call: hit
    assert wrapper(10) == 11
    assert calls == [10]  # no new call
    assert wrapper.cache_info() == (1, 1)  # 1 hit, 1 miss
    # Clear resets counts and cache
    wrapper.cache_clear()
    assert wrapper.cache_info() == (0, 0)
    assert cache == {}
    # After clear, another miss
    assert wrapper(20) == 21
    assert wrapper.cache_info() == (0, 1)


def test_condition_cache_with_pending():
    """Test the condition wrapper with lock, condition, and info."""
    lock = threading.Lock()
    cond = threading.Condition(lock)
    cache = {}
    calls = []

    def func(x):
        calls.append(x)
        return x * x

    wrapper = _cached._wrapper(
        func, cache, simple_key, lock=lock, cond=cond, info=info_func
    )
    # First call: miss
    assert wrapper(4) == 16
    assert calls == [4]
    assert wrapper.cache_info() == (0, 1)
    # Second call: hit
    assert wrapper(4) == 16
    assert calls == [4]  # no new call
    assert wrapper.cache_info() == (1, 1)
    # Clear resets everything
    wrapper.cache_clear()
    assert wrapper.cache_info() == (0, 0)
    assert cache == {}
    # After clear, another miss
    assert wrapper(5) == 25
    assert wrapper.cache_info() == (0, 1)


def test_uncached_with_info_counts_misses():
    """Test the uncached wrapper that still provides cache_info."""
    calls = []

    def func(x):
        calls.append(x)
        return x - 1

    wrapper = _cached._wrapper(func, cache=None, key=simple_key, info=info_func)
    # Call several times, each should be a miss
    for i in range(3):
        assert wrapper(i) == i - 1
    assert calls == [0, 1, 2]
    # cache_info should report 0 hits and 3 misses
    assert wrapper.cache_info() == (0, 3)
    # cache_clear resets miss count
    wrapper.cache_clear()
    assert wrapper.cache_info() == (0, 0)


def test_uncached_without_info_has_no_cache_info():
    """Test the uncached wrapper without info returns None for cache_info."""
    def func():
        return "value"

    wrapper = _cached._wrapper(func, cache=None, key=simple_key)
    assert wrapper() == "value"
    assert wrapper.cache_info is None
    # cache_clear should be a no‑op lambda
    wrapper.cache_clear()  # should not raise


def test_wrapper_attributes_are_set_correctly():
    """Verify that wrapper attributes reflect the passed parameters."""
    lock = threading.Lock()
    cond = threading.Condition(lock)
    cache = {}
    def func(x):
        return x

    # With lock and condition
    w1 = _cached._wrapper(func, cache, simple_key, lock=lock, cond=cond, info=info_func)
    assert w1.cache is cache
    assert w1.cache_key is simple_key
    assert w1.cache_lock is lock
    assert w1.cache_condition is cond

    # With only lock
    w2 = _cached._wrapper(func, cache, simple_key, lock=lock, info=info_func)
    assert w2.cache_lock is lock
    assert w2.cache_condition is None

    # With only condition (treated as lock for cache_lock)
    w3 = _cached._wrapper(func, cache, simple_key, cond=cond, info=info_func)
    assert w3.cache_lock is cond
    assert w3.cache_condition is cond

    # Without lock/cond
    w4 = _cached._wrapper(func, cache, simple_key, info=info_func)
    assert w4.cache_lock is None
    assert w4.cache_condition is None


def test_value_error_on_cache_set_is_handled_gracefully():
    """When the cache raises ValueError on set, the wrapper still returns the value."""
    cache = ValueErrorCache()
    lock = threading.Lock()
    calls = []

    def func(x):
        calls.append(x)
        return "too_large" if x == 1 else x * 2

    # Use the locked wrapper with info to observe hits/misses
    wrapper = _cached._wrapper(func, cache, simple_key, lock=lock, info=info_func)

    # First call with a value that triggers ValueError
    assert wrapper(1) == "too_large"
    # The value should not be stored in the cache
    assert 1 not in cache
    # Miss count should be 1, hits 0
    assert wrapper.cache_info() == (0, 1)

    # Subsequent call with same argument should recompute (still a miss)
    assert wrapper(1) == "too_large"
    assert wrapper.cache_info() == (0, 2)

    # Normal value should be cached
    assert wrapper(2) == 4
    assert cache[2] == 4
    assert wrapper.cache_info() == (0, 3)  # miss for 2
    # Second call hits cache
    assert wrapper(2) == 4
    assert wrapper.cache_info() == (1, 3)  # one hit now
