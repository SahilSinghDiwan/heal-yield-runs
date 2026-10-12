import threading
import types

import pytest

from cachetools import _cached


def identity_key(*args, **kwargs):
    """Simple key function that returns the first positional argument."""
    return args[0] if args else None


def make_counter_func():
    """Factory that returns a function counting its calls and returning its argument."""
    calls = {"count": 0}

    def func(x):
        calls["count"] += 1
        return f"result-{x}"
    func.calls = calls
    return func


class BadCache(dict):
    """Cache that raises ValueError on any attempt to store a value."""

    def __setitem__(self, key, value):
        raise ValueError("value too large")


def test_uncached_wrapper_behaviour():
    func = make_counter_func()
    wrapper = _cached._wrapper(func, cache=None, key=identity_key)

    # No caching – the function should be called every time
    assert wrapper(1) == "result-1"
    assert wrapper(1) == "result-1"
    assert func.calls["count"] == 2

    # cache_* attributes are set as expected
    assert wrapper.cache is None
    assert wrapper.cache_key is identity_key
    assert wrapper.cache_lock is None
    assert wrapper.cache_condition is None
    # cache_info is explicitly set to None for uncached wrappers
    assert wrapper.cache_info is None
    # cache_clear exists and does nothing
    assert wrapper.cache_clear() is None


def test_unlocked_wrapper_caches_without_lock():
    func = make_counter_func()
    cache = {}
    wrapper = _cached._wrapper(func, cache=cache, key=identity_key)

    # First call stores the result
    assert wrapper(2) == "result-2"
    assert func.calls["count"] == 1
    assert cache[2] == "result-2"

    # Second call hits the cache, function not called again
    assert wrapper(2) == "result-2"
    assert func.calls["count"] == 1

    # cache_* attributes
    assert wrapper.cache is cache
    assert wrapper.cache_key is identity_key
    assert isinstance(wrapper.cache_lock, threading.Condition)  # lock is a Condition when none supplied
    assert wrapper.cache_condition is None


def test_locked_wrapper_uses_threading_lock():
    func = make_counter_func()
    cache = {}
    lock = threading.Lock()
    wrapper = _cached._wrapper(func, cache=cache, key=identity_key, lock=lock)

    # First call stores the result
    assert wrapper(3) == "result-3"
    assert func.calls["count"] == 1
    assert cache[3] == "result-3"

    # Second call hits the cache
    assert wrapper(3) == "result-3"
    assert func.calls["count"] == 1

    # lock attribute should be the lock we passed
    assert wrapper.cache_lock is lock
    assert wrapper.cache_condition is None


def test_unlocked_info_counts_hits_and_misses():
    func = make_counter_func()
    cache = {}
    info = lambda hits, misses: (hits, misses)
    wrapper = _cached._wrapper(func, cache=cache, key=identity_key, info=info)

    # Miss on first call
    assert wrapper(4) == "result-4"
    # Hit on second call
    assert wrapper(4) == "result-4"
    # Miss on a new key
    assert wrapper(5) == "result-5"

    hits, misses = wrapper.cache_info()
    assert hits == 1  # one hit for key 4
    assert misses == 2  # two distinct keys (4 and 5) missed initially


def test_locked_info_counts_with_threading_lock():
    func = make_counter_func()
    cache = {}
    lock = threading.Lock()
    info = lambda hits, misses: {"hits": hits, "misses": misses}
    wrapper = _cached._wrapper(func, cache=cache, key=identity_key, lock=lock, info=info)

    # Misses
    assert wrapper(6) == "result-6"
    assert wrapper(7) == "result-7"
    # Hits
    assert wrapper(6) == "result-6"
    assert wrapper(7) == "result-7"

    stats = wrapper.cache_info()
    assert stats["hits"] == 2
    assert stats["misses"] == 2


def test_condition_info_counts_and_pending_behavior():
    func = make_counter_func()
    cache = {}
    lock = threading.Lock()
    cond = threading.Condition(lock)
    info = lambda hits, misses: (hits, misses)
    wrapper = _cached._wrapper(
        func, cache=cache, key=identity_key, lock=lock, cond=cond, info=info
    )

    # First call for key 8 (miss)
    assert wrapper(8) == "result-8"
    # Second call for same key (hit)
    assert wrapper(8) == "result-8"
    # New key 9 (miss)
    assert wrapper(9) == "result-9"

    hits, misses = wrapper.cache_info()
    assert hits == 1  # one hit for key 8
    assert misses == 2  # keys 8 and 9 missed initially

    # Ensure pending set is empty after calls (indirectly by calling again without deadlock)
    assert wrapper(8) == "result-8"
    assert wrapper(9) == "result-9"


def test_uncached_info_counts_misses_only():
    func = make_counter_func()
    info = lambda hits, misses: (hits, misses)
    wrapper = _cached._wrapper(func, cache=None, key=identity_key, info=info)

    # Call several times with different arguments
    assert wrapper(10) == "result-10"
    assert wrapper(11) == "result-11"
    assert wrapper(10) == "result-10"

    hits, misses = wrapper.cache_info()
    assert hits == 0  # uncached wrapper never records hits
    assert misses == 3  # three calls counted as misses


def test_bad_cache_does_not_propagate_value_error():
    func = make_counter_func()
    bad_cache = BadCache()
    wrapper = _cached._wrapper(func, cache=bad_cache, key=identity_key)

    # Even though BadCache raises ValueError on set, wrapper should return the computed value
    assert wrapper(12) == "result-12"
    # Subsequent call should still compute because the value was never stored
    assert wrapper(12) == "result-12"
    assert func.calls["count"] == 2


def test_wrapper_attribute_exposure():
    func = make_counter_func()
    cache = {}
    lock = threading.Lock()
    cond = threading.Condition(lock)
    info = lambda h, m: (h, m)

    # Unlocked with info
    w1 = _cached._wrapper(func, cache=cache, key=identity_key, info=info)
    assert w1.cache is cache
    assert w1.cache_key is identity_key
    assert isinstance(w1.cache_lock, threading.Condition)
    assert w1.cache_condition is None

    # Locked with info
    w2 = _cached._wrapper(func, cache=cache, key=identity_key, lock=lock, info=info)
    assert w2.cache_lock is lock
    assert w2.cache_condition is None

    # Condition with info
    w3 = _cached._wrapper(func, cache=cache, key=identity_key, lock=lock, cond=cond, info=info)
    assert w3.cache_lock is lock
    assert w3.cache_condition is cond

    # Uncached without info
    w4 = _cached._wrapper(func, cache=None, key=identity_key)
    assert w4.cache is None
    assert w4.cache_key is identity_key
    assert w4.cache_lock is None
    assert w4.cache_condition is None
    assert w4.cache_info is None
