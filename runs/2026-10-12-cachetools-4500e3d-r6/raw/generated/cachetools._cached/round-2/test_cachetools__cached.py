import threading
import types

import pytest

from cachetools import _cached


def identity(x):
    """Simple function to be wrapped."""
    return x


def test_uncached_wrapper_calls_function_and_has_no_info():
    # No cache, no info, no lock/condition
    wrapper = _cached._wrapper(
        func=identity,
        cache=None,
        key=lambda *a, **kw: a[0],
        lock=None,
        cond=None,
        info=None,
    )
    # Function should be called and result returned unchanged
    assert wrapper(42) == 42
    # No cache related attributes should be set to anything meaningful
    assert wrapper.cache is None
    assert wrapper.cache_key is not None
    assert wrapper.cache_lock is None
    assert wrapper.cache_condition is None
    # cache_info should be explicitly set to None by _wrapper
    assert wrapper.cache_info is None
    # cache_clear should be a callable that does nothing (no error)
    wrapper.cache_clear()


def test_uncached_info_counts_misses_and_clears():
    info = lambda hits, misses: (hits, misses)
    wrapper = _cached._wrapper(
        func=identity,
        cache=None,
        key=lambda *a, **kw: a[0],
        lock=None,
        cond=None,
        info=info,
    )
    # Each call counts as a miss
    assert wrapper.cache_info() == (0, 0)
    assert wrapper(1) == 1
    assert wrapper.cache_info() == (0, 1)
    assert wrapper(2) == 2
    assert wrapper.cache_info() == (0, 2)
    # cache_clear resets the miss counter
    wrapper.cache_clear()
    assert wrapper.cache_info() == (0, 0)


def test_locked_wrapper_caches_and_counts_hits_and_misses():
    lock = threading.Lock()
    cache = {}
    info = lambda hits, misses: (hits, misses)

    wrapper = _cached._wrapper(
        func=lambda x: x * 2,
        cache=cache,
        key=lambda *a, **kw: a[0],
        lock=lock,
        cond=None,
        info=info,
    )

    # First call is a miss and stores the result
    assert wrapper(3) == 6
    assert cache[3] == 6
    assert wrapper.cache_info() == (0, 1)

    # Second call with same key hits the cache
    assert wrapper(3) == 6
    assert wrapper.cache_info() == (1, 1)

    # Different key is another miss
    assert wrapper(4) == 8
    assert wrapper.cache_info() == (1, 2)

    # Clear resets counters and cache
    wrapper.cache_clear()
    assert wrapper.cache_info() == (0, 0)
    assert cache == {}


def test_locked_info_handles_value_error_on_setdefault():
    """When the cache raises ValueError on setdefault, the wrapper should
    return the freshly computed value and not store it."""
    class BadSetDefault(dict):
        def setdefault(self, key, default=None):
            raise ValueError

    lock = threading.Lock()
    cache = BadSetDefault()
    info = lambda hits, misses: (hits, misses)

    wrapper = _cached._wrapper(
        func=lambda x: x + 10,
        cache=cache,
        key=lambda *a, **kw: a[0],
        lock=lock,
        cond=None,
        info=info,
    )

    # First call: cache miss, ValueError on setdefault, result returned
    assert wrapper(5) == 15
    # The key should NOT be stored because setdefault failed
    assert 5 not in cache
    # Miss count should be 1, hits 0
    assert wrapper.cache_info() == (0, 1)

    # Second call with same argument: another miss (since not cached)
    assert wrapper(5) == 15
    assert wrapper.cache_info() == (0, 2)


def test_condition_wrapper_blocks_and_caches():
    lock = threading.Lock()
    cond = threading.Condition(lock)
    cache = {}
    call_counter = {"count": 0}

    def func(x):
        call_counter["count"] += 1
        return x * 3

    wrapper = _cached._wrapper(
        func=func,
        cache=cache,
        key=lambda *a, **kw: a[0],
        lock=lock,
        cond=cond,
        info=None,
    )

    # Run two threads that call the wrapper with the same argument
    results = []

    def target():
        results.append(wrapper(7))

    t1 = threading.Thread(target=target)
    t2 = threading.Thread(target=target)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # Both should receive the same result
    assert results == [21, 21]
    # The underlying function should have been called exactly once
    assert call_counter["count"] == 1
    # The value should now be cached
    assert cache[7] == 21


def test_condition_info_counts_and_clears():
    lock = threading.Lock()
    cond = threading.Condition(lock)
    cache = {}
    info = lambda hits, misses: (hits, misses)
    call_counter = {"count": 0}

    def func(x):
        call_counter["count"] += 1
        return x + 5

    wrapper = _cached._wrapper(
        func=func,
        cache=cache,
        key=lambda *a, **kw: a[0],
        lock=lock,
        cond=cond,
        info=info,
    )

    # First call: miss
    assert wrapper(2) == 7
    assert wrapper.cache_info() == (0, 1)
    # Second call: hit
    assert wrapper(2) == 7
    assert wrapper.cache_info() == (1, 1)
    # Clear resets counters and cache
    wrapper.cache_clear()
    assert wrapper.cache_info() == (0, 0)
    assert cache == {}
    # After clear, a new call is a miss again
    assert wrapper(2) == 7
    assert wrapper.cache_info() == (0, 1)


def test_wrapper_attribute_exposure():
    lock = threading.Lock()
    cache = {}
    key_func = lambda *a, **kw: a[0]
    info = lambda h, m: (h, m)

    wrapper = _cached._wrapper(
        func=lambda x: x,
        cache=cache,
        key=key_func,
        lock=lock,
        cond=None,
        info=info,
    )

    # Verify that the wrapper exposes the expected attributes
    assert wrapper.cache is cache
    assert wrapper.cache_key is key_func
    assert wrapper.cache_lock is lock
    assert wrapper.cache_condition is None
    # The wrapper should preserve the original function's metadata
    assert wrapper.__name__ == (lambda x: x).__name__
    assert isinstance(wrapper, types.FunctionType)
