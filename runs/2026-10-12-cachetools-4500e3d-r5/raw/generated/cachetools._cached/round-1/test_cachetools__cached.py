import threading
import types

import pytest

import cachetools._cached as _cached


def identity_key(*args, **kwargs):
    """Simple key function that returns the first positional argument."""
    return args[0] if args else None


def make_counter_func():
    """Factory that returns a function counting its calls and returning a deterministic result."""
    calls = {"count": 0}

    def func(x):
        calls["count"] += 1
        return f"result-{x}"

    func.calls = calls
    return func


def test_uncached_wrapper_behaviour():
    """_uncached should simply call the underlying function without caching."""
    func = make_counter_func()
    wrapper = _cached._wrapper(func, cache=None, key=identity_key)

    # Calls should pass through directly
    assert wrapper(1) == "result-1"
    assert func.calls["count"] == 1
    assert wrapper(1) == "result-1"
    assert func.calls["count"] == 2

    # cache_clear should be a no‑op
    wrapper.cache_clear()
    assert func.calls["count"] == 2


def test_unlocked_wrapper_caches_without_lock():
    """_unlocked should cache results even when no lock is supplied."""
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
    # When no lock or condition is supplied, cache_lock is None
    assert wrapper.cache_lock is None
    assert wrapper.cache_condition is None


def test_locked_wrapper_uses_threading_lock():
    """_locked should use a threading.Lock when provided."""
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

    # lock exposure
    assert wrapper.cache_lock is lock
    assert isinstance(wrapper.cache_lock, threading.Lock)


def test_unlocked_info_counts_hits_and_misses():
    """_unlocked_info should correctly count cache hits and misses."""
    func = make_counter_func()
    cache = {}
    info = lambda h, m: (h, m)
    wrapper = _cached._wrapper(func, cache=cache, key=identity_key, info=info)

    # Miss
    assert wrapper(4) == "result-4"
    # Hit
    assert wrapper(4) == "result-4"

    # Verify info reports (hits, misses)
    hits, misses = wrapper.cache_info()
    assert hits == 1
    assert misses == 1

    # Clear cache and counters
    wrapper.cache_clear()
    assert wrapper.cache_info() == (0, 0)


def test_locked_info_counts_with_threading_lock():
    """_locked_info should correctly count hits/misses with a lock."""
    func = make_counter_func()
    cache = {}
    lock = threading.Lock()
    info = lambda h, m: (h, m)
    wrapper = _cached._wrapper(func, cache=cache, key=identity_key, lock=lock, info=info)

    # Miss
    assert wrapper(5) == "result-5"
    # Hit
    assert wrapper(5) == "result-5"

    hits, misses = wrapper.cache_info()
    assert hits == 1
    assert misses == 1

    wrapper.cache_clear()
    assert wrapper.cache_info() == (0, 0)


def test_condition_info_counts_and_pending_behavior():
    """_condition_info should handle pending set correctly and count hits/misses."""
    func = make_counter_func()
    cache = {}
    lock = threading.Lock()
    cond = threading.Condition(lock)
    info = lambda h, m: (h, m)
    wrapper = _cached._wrapper(func, cache=cache, key=identity_key, lock=lock, cond=cond, info=info)

    # First call: miss, adds to pending, computes result
    assert wrapper(6) == "result-6"
    hits, misses = wrapper.cache_info()
    assert hits == 0
    assert misses == 1

    # Second call with same key should hit cache (pending cleared)
    assert wrapper(6) == "result-6"
    hits, misses = wrapper.cache_info()
    assert hits == 1
    assert misses == 1

    # Ensure pending set is empty after calls
    assert not wrapper.cache_condition._waiters  # internal condition waiters list should be empty


def test_uncached_info_counts_misses_only():
    """_uncached_info should only count misses (calls) and never cache."""
    func = make_counter_func()
    info = lambda h, m: (h, m)
    wrapper = _cached._wrapper(func, cache=None, key=identity_key, info=info)

    # Each call increments miss count
    assert wrapper(7) == "result-7"
    assert wrapper(8) == "result-8"
    hits, misses = wrapper.cache_info()
    assert hits == 0
    assert misses == 2

    wrapper.cache_clear()
    assert wrapper.cache_info() == (0, 0)


def test_bad_cache_does_not_propagate_value_error():
    """If cache.__setitem__ raises ValueError, wrapper should swallow it."""
    class BadCache(dict):
        def __setitem__(self, key, value):
            raise ValueError("Too large")

    func = make_counter_func()
    cache = BadCache()
    wrapper = _cached._wrapper(func, cache=cache, key=identity_key)

    # Should still return correct result despite cache error
    assert wrapper(9) == "result-9"
    # Subsequent call should recompute because value wasn't stored
    assert wrapper(9) == "result-9"
    assert func.calls["count"] == 2


def test_wrapper_attribute_exposure():
    """All wrappers should expose cache, key, lock, and condition attributes."""
    func = make_counter_func()
    cache = {}
    lock = threading.Lock()
    cond = threading.Condition(lock)
    info = lambda h, m: (h, m)

    # Unlocked with info (no lock/cond supplied)
    w1 = _cached._wrapper(func, cache=cache, key=identity_key, info=info)
    assert w1.cache is cache
    assert w1.cache_key is identity_key
    assert w1.cache_lock is None  # No lock/condition supplied
    assert w1.cache_condition is None

    # Locked with info
    w2 = _cached._wrapper(func, cache=cache, key=identity_key, lock=lock, info=info)
    assert w2.cache_lock is lock
    assert isinstance(w2.cache_lock, threading.Lock)

    # Condition with info
    w3 = _cached._wrapper(func, cache=cache, key=identity_key, lock=lock, cond=cond, info=info)
    assert w3.cache_lock is lock
    assert w3.cache_condition is cond
    assert isinstance(w3.cache_condition, threading.Condition)

    # Unlocked without info
    w4 = _cached._wrapper(func, cache=cache, key=identity_key)
    assert w4.cache_lock is None
    assert w4.cache_condition is None

    # Locked without info
    w5 = _cached._wrapper(func, cache=cache, key=identity_key, lock=lock)
    assert w5.cache_lock is lock
    assert isinstance(w5.cache_lock, threading.Lock)

    # Condition without info
    w6 = _cached._wrapper(func, cache=cache, key=identity_key, lock=lock, cond=cond)
    assert w6.cache_lock is lock
    assert w6.cache_condition is cond
