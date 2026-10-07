import threading

import pytest

from cachetools import _cached


def make_counter_func():
    """Return a callable that counts how many times it was invoked."""
    calls = {"count": 0}

    def func(x):
        calls["count"] += 1
        return x * 2

    func.calls = calls
    return func


def simple_key(x):
    """Cache key based on the first positional argument."""
    return x


def info_func(hits, misses):
    """Return a tuple that mirrors the hits/misses counters."""
    return hits, misses


def test_uncached_wrapper_calls_function_each_time():
    func = make_counter_func()
    wrapper = _cached._wrapper(func, cache=None, key=simple_key)

    # No caching – each call should invoke the original function.
    assert wrapper(1) == 2
    assert wrapper(2) == 4
    assert func.calls["count"] == 2

    # cache_clear exists but does nothing; calling it should not raise.
    wrapper.cache_clear()
    assert func.calls["count"] == 2

    # cache_info is explicitly set to None for uncached wrappers.
    assert wrapper.cache_info is None


def test_unlocked_wrapper_caches_and_counts_hits_misses():
    cache = {}
    func = make_counter_func()
    wrapper = _cached._wrapper(func, cache=cache, key=simple_key, info=info_func)

    # First call – miss, function executed.
    assert wrapper(10) == 20
    assert func.calls["count"] == 1
    assert cache[10] == 20
    assert wrapper.cache_info() == (0, 1)  # 0 hits, 1 miss

    # Second call – hit, function not executed again.
    assert wrapper(10) == 20
    assert func.calls["count"] == 1  # unchanged
    assert wrapper.cache_info() == (1, 1)  # 1 hit, 1 miss

    # Clear cache – counters reset.
    wrapper.cache_clear()
    assert cache == {}
    assert wrapper.cache_info() == (0, 0)


def test_locked_wrapper_behaves_like_unlocked():
    cache = {}
    lock = threading.Lock()
    func = make_counter_func()
    wrapper = _cached._wrapper(func, cache=cache, key=simple_key, lock=lock, info=info_func)

    # First call – miss.
    assert wrapper(5) == 10
    assert func.calls["count"] == 1
    assert wrapper.cache_info() == (0, 1)

    # Second call – hit.
    assert wrapper(5) == 10
    assert func.calls["count"] == 1
    assert wrapper.cache_info() == (1, 1)

    # Verify that wrapper attributes are wired correctly.
    assert wrapper.cache is cache
    assert wrapper.cache_key is simple_key
    # When a lock is supplied, cache_lock should be that lock.
    assert wrapper.cache_lock is lock
    assert wrapper.cache_condition is None


def test_condition_wrapper_with_info_counts_hits_and_misses():
    cache = {}
    lock = threading.Lock()
    cond = threading.Condition(lock)
    func = make_counter_func()
    wrapper = _cached._wrapper(
        func,
        cache=cache,
        key=simple_key,
        lock=lock,
        cond=cond,
        info=info_func,
    )

    # First call – miss.
    assert wrapper(3) == 6
    assert func.calls["count"] == 1
    assert wrapper.cache_info() == (0, 1)

    # Second call – hit.
    assert wrapper(3) == 6
    assert func.calls["count"] == 1
    assert wrapper.cache_info() == (1, 1)

    # Call with a different key – another miss.
    assert wrapper(7) == 14
    assert func.calls["count"] == 2
    assert wrapper.cache_info() == (1, 2)

    # Clear and ensure counters reset.
    wrapper.cache_clear()
    assert cache == {}
    assert wrapper.cache_info() == (0, 0)


def test_uncached_info_wrapper_counts_misses():
    func = make_counter_func()
    wrapper = _cached._wrapper(func, cache=None, key=simple_key, info=info_func)

    # No caching – each call is a miss.
    assert wrapper(1) == 2
    assert wrapper(2) == 4
    assert wrapper.cache_info() == (0, 2)  # 0 hits, 2 misses

    # Clear miss counter.
    wrapper.cache_clear()
    assert wrapper.cache_info() == (0, 0)


def test_wrapper_attribute_exposure():
    cache = {}
    lock = threading.Lock()
    cond = threading.Condition(lock)

    func = make_counter_func()
    wrapper = _cached._wrapper(
        func,
        cache=cache,
        key=simple_key,
        lock=lock,
        cond=cond,
        info=info_func,
    )

    # All public attributes should be present and correctly reference the objects passed.
    assert wrapper.cache is cache
    assert wrapper.cache_key is simple_key
    assert wrapper.cache_lock is lock
    assert wrapper.cache_condition is cond

    # The wrapper should preserve the original function's metadata.
    assert wrapper.__name__ == func.__name__
    assert wrapper.__doc__ == func.__doc__
