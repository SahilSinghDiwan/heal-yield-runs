import threading
import types

import pytest

import cachetools._cached as cached


def simple_key(*args, **kwargs):
    """Simple key function that returns the first positional argument."""
    return args[0] if args else None


def info_tuple(hits, misses):
    """Return a tuple of hits and misses for testing cache_info."""
    return (hits, misses)


def test_unlocked_wrapper_caches_and_counts_hits_misses():
    """_unlocked_info should cache results and correctly count hits and misses."""
    cache = {}
    call_counter = {"count": 0}

    def func(x):
        call_counter["count"] += 1
        return x * 2

    wrapper = cached._wrapper(
        func=func,
        cache=cache,
        key=simple_key,
        lock=None,
        cond=None,
        info=info_tuple,
    )

    # First call: miss, function executed
    assert wrapper(3) == 6
    assert call_counter["count"] == 1
    assert cache[3] == 6
    assert wrapper.cache_info() == (0, 1)  # 0 hits, 1 miss

    # Second call with same argument: hit, function not executed again
    assert wrapper(3) == 6
    assert call_counter["count"] == 1
    assert wrapper.cache_info() == (1, 1)  # 1 hit, 1 miss

    # Clear cache and counters
    wrapper.cache_clear()
    assert cache == {}
    assert wrapper.cache_info() == (0, 0)


def test_locked_wrapper_behaves_like_unlocked():
    """_locked_info should behave like _unlocked_info but with a lock."""
    lock = threading.Lock()
    cache = {}
    call_counter = {"count": 0}

    def func(x):
        call_counter["count"] += 1
        return x + 5

    wrapper = cached._wrapper(
        func=func,
        cache=cache,
        key=simple_key,
        lock=lock,
        cond=None,
        info=info_tuple,
    )

    # First call: miss
    assert wrapper(10) == 15
    assert call_counter["count"] == 1
    assert wrapper.cache_info() == (0, 1)

    # Second call: hit
    assert wrapper(10) == 15
    assert call_counter["count"] == 1
    assert wrapper.cache_info() == (1, 1)

    # Different argument: miss again
    assert wrapper(7) == 12
    assert call_counter["count"] == 2
    assert wrapper.cache_info() == (1, 2)

    wrapper.cache_clear()
    assert wrapper.cache_info() == (0, 0)


def test_condition_wrapper_with_info_counts_hits_and_misses():
    """_condition_info should correctly handle pending set and count hits/misses."""
    lock = threading.Lock()
    cond = threading.Condition(lock)
    cache = {}
    call_counter = {"count": 0}

    def func(x):
        call_counter["count"] += 1
        return x * x

    wrapper = cached._wrapper(
        func=func,
        cache=cache,
        key=simple_key,
        lock=lock,
        cond=cond,
        info=info_tuple,
    )

    # First call: miss
    assert wrapper(4) == 16
    assert call_counter["count"] == 1
    assert wrapper.cache_info() == (0, 1)

    # Second call: hit
    assert wrapper(4) == 16
    assert call_counter["count"] == 1
    assert wrapper.cache_info() == (1, 1)

    # Different argument: miss
    assert wrapper(5) == 25
    assert call_counter["count"] == 2
    assert wrapper.cache_info() == (1, 2)

    wrapper.cache_clear()
    assert wrapper.cache_info() == (0, 0)


def test_uncached_info_wrapper_counts_misses():
    """_uncached_info should count misses even though it doesn't cache."""
    call_counter = {"count": 0}

    def func(x):
        call_counter["count"] += 1
        return x - 1

    wrapper = cached._wrapper(
        func=func,
        cache=None,
        key=simple_key,
        lock=None,
        cond=None,
        info=info_tuple,
    )

    # Call several times; each should increment miss count
    for i in range(3):
        assert wrapper(i) == i - 1
    assert call_counter["count"] == 3
    # cache_info should report 0 hits and 3 misses
    assert wrapper.cache_info() == (0, 3)

    wrapper.cache_clear()
    assert wrapper.cache_info() == (0, 0)


def test_wrapper_attribute_exposure():
    """All wrappers should expose the expected attributes."""
    lock = threading.Lock()
    cond = threading.Condition()
    cache = {}

    # Original function to be wrapped
    func = lambda x: x

    wrapper = cached._wrapper(
        func=func,
        cache=cache,
        key=simple_key,
        lock=lock,
        cond=cond,
        info=info_tuple,
    )

    # Standard function attributes
    assert isinstance(wrapper, types.FunctionType)
    # The wrapper should preserve the original function's name via update_wrapper
    assert wrapper.__name__ == func.__name__
    assert wrapper.__doc__ == func.__doc__
    assert wrapper.__module__ == func.__module__

    # Cache-related attributes
    assert wrapper.cache is cache
    assert wrapper.cache_key is simple_key
    # When both lock and condition are provided, cache_lock should be the lock
    assert wrapper.cache_lock is lock
    assert wrapper.cache_condition is cond

    # Ensure the wrapper has cache management methods
    assert callable(wrapper.cache_clear)
    # cache_info should be present because info was supplied
    assert callable(wrapper.cache_info)
