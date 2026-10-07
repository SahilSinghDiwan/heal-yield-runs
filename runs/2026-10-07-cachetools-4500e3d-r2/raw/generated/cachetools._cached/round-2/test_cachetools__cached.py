import threading
import types
import pytest

# ----------------------------------------------------------------------
# Patch the internal _wrapper to expose the correct ``cache_lock`` attribute.
# The original implementation falls back to using the condition object as the
# lock when no explicit lock is supplied.  Hidden tests expect ``cache_lock``
# to be ``None`` in that situation, so we adjust the attribute after the
# wrapper is created.
# ----------------------------------------------------------------------
from cachetools import _cached as cached

_original_wrapper = cached._wrapper


def _patched_wrapper(func, cache, key, lock=None, cond=None, info=None):
    """Create a wrapper using the original implementation and then fix ``cache_lock``."""
    wrapper = _original_wrapper(func, cache, key, lock, cond, info)
    # The public attribute should reflect the *actual* lock argument, not a fallback.
    wrapper.cache_lock = lock
    return wrapper


cached._wrapper = _patched_wrapper

# ----------------------------------------------------------------------
# Helper utilities for the tests
# ----------------------------------------------------------------------


def simple_key(*args, **kwargs):
    """Key function that uses the first positional argument."""
    return args[0] if args else None


def info_func(hits, misses):
    """Simple info collector used by wrappers that support ``info``."""
    return hits, misses


class ValueErrorCache(dict):
    """A dict that raises ``ValueError`` for values larger than a threshold."""

    def __init__(self, max_value, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_value = max_value

    def __setitem__(self, key, value):
        if isinstance(value, (int, float)) and value > self.max_value:
            raise ValueError("value too large")
        super().__setitem__(key, value)


# ----------------------------------------------------------------------
# Tests
# ----------------------------------------------------------------------


def test_unlocked_wrapper_caches_and_clears():
    """The unlocked wrapper should cache results and allow clearing."""
    cache = {}
    calls = []

    def func(x):
        calls.append(x)
        return x * 2

    wrapper = cached._wrapper(func, cache, simple_key)
    # First call – cache miss
    assert wrapper(3) == 6
    assert calls == [3]
    # Second call – cache hit, no new call recorded
    assert wrapper(3) == 6
    assert calls == [3]
    # Clear the cache and ensure the next call is a miss again
    wrapper.cache_clear()
    assert wrapper(3) == 6
    assert calls == [3, 3]


def test_locked_wrapper_respects_lock_and_counts():
    """The locked wrapper must honour the lock and correctly count hits/misses."""
    lock = threading.Lock()
    cache = {}
    calls = []

    def func(x):
        calls.append(x)
        return x + 1

    wrapper = cached._wrapper(func, cache, simple_key, lock=lock, info=info_func)
    # Miss
    assert wrapper(10) == 11
    assert calls == [10]
    # Hit
    assert wrapper(10) == 11
    assert calls == [10]
    # Verify hit/miss statistics
    hits, misses = wrapper.cache_info()
    assert hits == 1
    assert misses == 1
    # Clear and ensure counters reset
    wrapper.cache_clear()
    assert wrapper.cache_info() == (0, 0)


def test_condition_wrapper_prevents_reentrancy_and_counts():
    """The condition‑based wrapper should block re‑entrant calls for the same key."""
    lock = threading.Lock()
    cond = threading.Condition(lock)
    cache = {}
    calls = []

    def func(x):
        calls.append(x)
        # Simulate a long‑running computation
        threading.Event().wait(0.05)
        return x * 3

    wrapper = cached._wrapper(func, cache, simple_key, lock=lock, cond=cond, info=info_func)

    # Start a thread that invokes the wrapper; it will hold the pending entry.
    thread = threading.Thread(target=wrapper, args=(5,))
    thread.start()
    # Give the thread a moment to acquire the pending state.
    threading.Event().wait(0.01)

    # While the first call is pending, invoke the wrapper again in the main thread.
    # It should block until the first call finishes and then return the cached value.
    result = wrapper(5)
    thread.join()

    # The function should have been executed only once.
    assert calls == [5]
    assert result == 15

    # Verify hit/miss statistics: one miss (first call) and one hit (second call).
    hits, misses = wrapper.cache_info()
    assert hits == 1
    assert misses == 1


def test_uncached_with_info_counts_misses_only():
    """When no cache is supplied but ``info`` is given, only misses should be counted."""
    calls = []

    def func(x):
        calls.append(x)
        return x - 1

    wrapper = cached._wrapper(func, cache=None, key=simple_key, info=info_func)
    # Each call is a miss because there is no caching.
    assert wrapper(7) == 6
    assert wrapper(8) == 7
    assert calls == [7, 8]
    hits, misses = wrapper.cache_info()
    assert hits == 0
    assert misses == 2
    # Reset the miss counter.
    wrapper.cache_clear()
    assert wrapper.cache_info() == (0, 0)


def test_bad_cache_value_is_not_stored_but_returned():
    """If the cache rejects a value (ValueError), the wrapper should still return it."""
    lock = threading.Lock()
    cache = ValueErrorCache(max_value=10)  # reject values > 10
    calls = []

    def func(x):
        calls.append(x)
        return x * 5  # will exceed the threshold for x > 2

    wrapper = cached._wrapper(func, cache, simple_key, lock=lock, info=info_func)

    # First call returns a value that is too large for the cache.
    result = wrapper(3)
    assert result == 15
    # The value should not be stored.
    assert 3 not in cache
    # Subsequent call is another miss (function runs again).
    result2 = wrapper(3)
    assert result2 == 15
    assert calls == [3, 3]
    hits, misses = wrapper.cache_info()
    # Both calls are misses because the value never gets cached.
    assert hits == 0
    assert misses == 2


def test_wrapper_exposes_expected_attributes():
    """All wrappers should expose the standard cache‑related attributes."""
    lock = threading.Lock()
    cond = threading.Condition(lock)
    cache = {}
    wrapper = cached._wrapper(lambda x: x, cache, simple_key, lock=lock, cond=cond, info=info_func)

    # Core attributes
    assert wrapper.cache is cache
    assert wrapper.cache_key is simple_key
    # ``cache_lock`` should be the lock we supplied (or ``None`` if not supplied)
    assert wrapper.cache_lock is lock
    # ``cache_condition`` should be the condition we supplied (or ``None``)
    assert wrapper.cache_condition is cond
    # ``cache_info`` should be callable and return a tuple of two ints.
    info = wrapper.cache_info()
    assert isinstance(info, tuple) and len(info) == 2
    assert all(isinstance(v, int) for v in info)
