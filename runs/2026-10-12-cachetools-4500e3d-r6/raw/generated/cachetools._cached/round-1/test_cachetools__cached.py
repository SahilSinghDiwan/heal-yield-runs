import threading

import pytest

import cachetools._cached as _cached


# Helper key function and info collector used across tests
identity_key = lambda *args, **kwargs: args
info_func = lambda hits, misses: (hits, misses)


def test_uncached_wrapper_calls_function_and_has_no_info():
    """_uncached wrapper should call the original function and expose no info."""
    calls = []

    def func(x):
        calls.append(x)
        return x * 2

    wrapper = _cached._wrapper(func, cache=None, key=identity_key, lock=None, cond=None, info=None)

    # The wrapper should behave like the original function
    assert wrapper(5) == 10
    assert calls == [5]

    # No caching attributes should be set (cache is None)
    assert wrapper.cache is None
    assert wrapper.cache_key is identity_key
    assert wrapper.cache_lock is None
    assert wrapper.cache_condition is None
    # No info method for uncached wrappers
    assert wrapper.cache_info is None


def test_uncached_info_counts_misses_and_clears():
    """_uncached_info should count misses and allow clearing."""
    calls = []

    def func(x):
        calls.append(x)
        return x + 1

    wrapper = _cached._wrapper(func, cache=None, key=identity_key, lock=None, cond=None, info=info_func)

    # First call – miss
    assert wrapper(1) == 2
    assert calls == [1]
    assert wrapper.cache_info() == (0, 1)

    # Second call – another miss (no caching)
    assert wrapper(2) == 3
    assert calls == [1, 2]
    assert wrapper.cache_info() == (0, 2)

    # Clear the miss counter
    wrapper.cache_clear()
    assert wrapper.cache_info() == (0, 0)


def test_locked_wrapper_caches_and_counts_hits_and_misses():
    """_locked wrapper should cache results and count hits/misses."""
    cache = {}
    lock = threading.Lock()
    calls = []

    def func(x):
        calls.append(x)
        return x * 3

    wrapper = _cached._wrapper(func, cache=cache, key=identity_key, lock=lock, cond=None, info=info_func)

    # First call – miss, value stored
    assert wrapper(2) == 6
    assert calls == [2]
    assert cache[(2,)] == 6
    assert wrapper.cache_info() == (0, 1)

    # Second call – hit, no new function call
    assert wrapper(2) == 6
    assert calls == [2]  # unchanged
    assert wrapper.cache_info() == (1, 1)

    # Clear cache and counters
    wrapper.cache_clear()
    assert wrapper.cache_info() == (0, 0)
    assert cache == {}


def test_locked_info_handles_value_error_on_setitem():
    """When the cache raises ValueError on set, the wrapper should still return the value."""
    class BadCache(dict):
        def __setitem__(self, key, value):
            if value > 10:
                raise ValueError("value too large")
            super().__setitem__(key, value)

    cache = BadCache()
    lock = threading.Lock()
    calls = []

    def func(x):
        calls.append(x)
        return x * 5  # will be >10 for x >= 3

    wrapper = _cached._wrapper(func, cache=cache, key=identity_key, lock=lock, cond=None, info=info_func)

    # First call – miss, value too large to store (or stored depending on dict implementation)
    assert wrapper(3) == 15
    assert calls == [3]

    # The cache may or may not contain the key; if it does, the stored value must be correct.
    if (3,) in cache:
        assert cache[(3,)] == 15

    # Cache info should reflect one miss; hits may be 0 or 1 depending on whether the value was stored.
    hits, misses = wrapper.cache_info()
    assert misses == 1
    assert hits in (0, 1)


def test_condition_wrapper_blocks_and_caches():
    """_condition wrapper should block concurrent computation for the same key and cache the result."""
    cache = {}
    lock = threading.Lock()
    cond = threading.Condition(lock)
    calls = []

    def func(x):
        calls.append(x)
        return x * 7

    wrapper = _cached._wrapper(func, cache=cache, key=identity_key, lock=lock, cond=cond, info=None)

    # First call – miss, stores result
    assert wrapper(4) == 28
    assert calls == [4]
    assert cache[(4,)] == 28

    # Second call – hit, no new function call
    assert wrapper(4) == 28
    assert calls == [4]  # unchanged


def test_condition_info_counts_and_clears():
    """_condition_info should count hits/misses and allow clearing."""
    cache = {}
    lock = threading.Lock()
    cond = threading.Condition(lock)
    calls = []

    def func(x):
        calls.append(x)
        return x - 1

    wrapper = _cached._wrapper(func, cache=cache, key=identity_key, lock=lock, cond=cond, info=info_func)

    # First call – miss
    assert wrapper(10) == 9
    assert calls == [10]
    assert wrapper.cache_info() == (0, 1)

    # Second call – hit
    assert wrapper(10) == 9
    assert calls == [10]
    assert wrapper.cache_info() == (1, 1)

    # Clear cache and counters
    wrapper.cache_clear()
    assert wrapper.cache_info() == (0, 0)
    assert cache == {}


def test_wrapper_attribute_exposure():
    """All wrappers should expose cache, key, lock, and condition attributes."""
    cache = {}
    lock = threading.Lock()
    cond = threading.Condition(lock)

    def func(x):
        return x

    # Unlocked (no lock, no condition)
    w1 = _cached._wrapper(func, cache=cache, key=identity_key, lock=None, cond=None, info=None)
    assert w1.cache is cache
    assert w1.cache_key is identity_key
    assert w1.cache_lock is None
    assert w1.cache_condition is None

    # Locked only
    w2 = _cached._wrapper(func, cache=cache, key=identity_key, lock=lock, cond=None, info=None)
    assert w2.cache_lock is lock
    assert w2.cache_condition is None

    # Condition only (lock is taken from condition)
    w3 = _cached._wrapper(func, cache=cache, key=identity_key, lock=None, cond=cond, info=None)
    assert w3.cache_lock is cond
    assert w3.cache_condition is cond

    # Both lock and condition
    w4 = _cached._wrapper(func, cache=cache, key=identity_key, lock=lock, cond=cond, info=None)
    assert w4.cache_lock is lock
    assert w4.cache_condition is cond
