import threading
import types

import pytest

import cachetools._cached as cached


def test_uncached_wrapper_calls_function_each_time():
    calls = []

    def func(x):
        calls.append(x)
        return x * 2

    wrapper = cached._wrapper(func, cache=None, key=lambda x: x)
    assert wrapper(1) == 2
    assert wrapper(1) == 2
    assert calls == [1, 1]  # function called each time


def test_unlocked_wrapper_caches_and_counts_hits_misses():
    calls = []

    def func(x):
        calls.append(x)
        return x + 1

    cache = {}
    wrapper = cached._wrapper(
        func,
        cache=cache,
        key=lambda x: x,
        info=lambda hits, misses: (hits, misses),
    )
    # first call: miss
    assert wrapper(1) == 2
    # second call: hit
    assert wrapper(1) == 2
    # third call with new key: miss
    assert wrapper(2) == 3
    assert calls == [1, 2]
    # cache_info should reflect 1 hit, 2 misses
    assert wrapper.cache_info() == (1, 2)
    # clear cache and stats
    wrapper.cache_clear()
    assert wrapper.cache_info() == (0, 0)
    # after clear, cache miss again
    assert wrapper(1) == 2
    assert wrapper.cache_info() == (0, 1)


def test_locked_wrapper_behaves_like_unlocked():
    # locked version should behave the same as unlocked for single-threaded use
    calls = []

    def func(x):
        calls.append(x)
        return x * x

    cache = {}
    lock = threading.Lock()
    wrapper = cached._wrapper(
        func,
        cache=cache,
        key=lambda x: x,
        lock=lock,
        info=lambda hits, misses: (hits, misses),
    )
    assert wrapper(3) == 9
    assert wrapper(3) == 9
    assert calls == [3]  # only one call to underlying function
    assert wrapper.cache_info() == (1, 1)  # one hit, one miss


def test_condition_wrapper_with_info_counts_hits_and_misses():
    calls = []

    def func(x):
        calls.append(x)
        return x * 10

    cache = {}
    lock = threading.Lock()
    cond = threading.Condition(lock)
    wrapper = cached._wrapper(
        func,
        cache=cache,
        key=lambda x: x,
        lock=lock,
        cond=cond,
        info=lambda hits, misses: {"hits": hits, "misses": misses},
    )
    # first call: miss
    assert wrapper(5) == 50
    # second call: hit
    assert wrapper(5) == 50
    # third call with new key: miss
    assert wrapper(6) == 60
    assert calls == [5, 6]
    assert wrapper.cache_info() == {"hits": 1, "misses": 2}
    # clear and verify stats reset
    wrapper.cache_clear()
    assert wrapper.cache_info() == {"hits": 0, "misses": 0}
    # after clear, miss again
    assert wrapper(5) == 50
    assert wrapper.cache_info() == {"hits": 0, "misses": 1}


def test_uncached_info_wrapper_counts_misses():
    calls = []

    def func():
        calls.append(1)
        return "result"

    wrapper = cached._wrapper(
        func,
        cache=None,
        key=lambda: None,
        info=lambda hits, misses: (hits, misses),
    )
    # each call increments misses
    assert wrapper() == "result"
    assert wrapper() == "result"
    assert calls == [1, 1]
    assert wrapper.cache_info() == (0, 2)
    wrapper.cache_clear()
    assert wrapper.cache_info() == (0, 0)


def test_wrapper_attribute_exposure():
    def func(x):
        return x

    cache = {}
    lock = threading.Lock()
    cond = threading.Condition(lock)
    wrapper = cached._wrapper(
        func,
        cache=cache,
        key=lambda x: x,
        lock=lock,
        cond=cond,
        info=lambda h, m: (h, m),
    )
    # attributes should be set correctly
    assert wrapper.cache is cache
    assert wrapper.cache_key(10) == 10
    assert wrapper.cache_lock is lock
    assert wrapper.cache_condition is cond
    # __name__ and __doc__ are preserved
    assert wrapper.__name__ == func.__name__
    assert wrapper.__doc__ == func.__doc__


def test_cache_setitem_raises_value_error_unlocked():
    """When the cache raises ValueError on setitem, the wrapper should still
    return the computed value and not store it."""
    class BadCache(dict):
        def __setitem__(self, key, value):
            raise ValueError("too large")

    calls = []

    def func(x):
        calls.append(x)
        return x * 3

    cache = BadCache()
    wrapper = cached._wrapper(
        func,
        cache=cache,
        key=lambda x: x,
        info=lambda h, m: (h, m),
    )
    # first call: miss, ValueError on setitem, value still returned
    assert wrapper(2) == 6
    # second call: still a miss because value wasn't stored
    assert wrapper(2) == 6
    assert calls == [2, 2]
    # cache should remain empty
    assert dict(cache) == {}


def test_cache_setitem_raises_value_error_locked():
    """When the cache raises ValueError on setdefault, the wrapper should
    return the computed value."""
    class BadCache(dict):
        def setdefault(self, key, default):
            raise ValueError("too large")

    calls = []

    def func(x):
        calls.append(x)
        return x + 5

    cache = BadCache()
    lock = threading.Lock()
    wrapper = cached._wrapper(
        func,
        cache=cache,
        key=lambda x: x,
        lock=lock,
        info=lambda h, m: (h, m),
    )
    # first call: miss, ValueError on setdefault, value returned
    assert wrapper(1) == 6
    # second call: still a miss because value wasn't stored
    assert wrapper(1) == 6
    assert calls == [1, 1]
    # cache should remain empty
    assert dict(cache) == {}


def test_condition_wrapper_cache_clear_resets_stats():
    """Ensure that cache_clear on a condition+info wrapper resets hit/miss counters."""
    calls = []

    def func(x):
        calls.append(x)
        return x * 2

    cache = {}
    lock = threading.Lock()
    cond = threading.Condition(lock)
    wrapper = cached._wrapper(
        func,
        cache=cache,
        key=lambda x: x,
        lock=lock,
        cond=cond,
        info=lambda h, m: {"hits": h, "misses": m},
    )
    # generate one hit and one miss
    assert wrapper(7) == 14  # miss
    assert wrapper(7) == 14  # hit
    assert wrapper.cache_info() == {"hits": 1, "misses": 1}
    # clear should reset both counters
    wrapper.cache_clear()
    assert wrapper.cache_info() == {"hits": 0, "misses": 0}
    # after clear, another miss
    assert wrapper(8) == 16
    assert wrapper.cache_info() == {"hits": 0, "misses": 1}
