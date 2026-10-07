import threading
import types

import pytest
from cachetools import _cached as cached


# Helper to create a simple key function
def first_arg_key(*args, **kwargs):
    # ignore kwargs for simplicity
    return args[0] if args else None


# Simple info collector that just returns the hits and misses tuple
def simple_info(hits, misses):
    return (hits, misses)


class BadCache(dict):
    """A dict that raises ValueError for a specific sentinel value."""

    def __setitem__(self, key, value):
        if value == "bad":
            raise ValueError("value too large")
        super().__setitem__(key, value)


def test_unlocked_wrapper_caches_and_clears():
    calls = []

    def func(x):
        calls.append(x)
        return x * 2

    cache = {}
    wrapper = cached._wrapper(
        func,
        cache=cache,
        key=first_arg_key,
        lock=None,
        cond=None,
        info=None,
    )

    # First call computes
    assert wrapper(3) == 6
    assert calls == [3]
    assert cache[3] == 6

    # Second call hits cache, no new computation
    assert wrapper(3) == 6
    assert calls == [3]  # unchanged

    # Clear cache and ensure recomputation
    wrapper.cache_clear()
    assert cache == {}
    assert wrapper(3) == 6
    assert calls == [3, 3]


def test_locked_wrapper_respects_lock_and_counts():
    calls = []

    def func(x):
        calls.append(x)
        return x + 1

    cache = {}
    lock = threading.Lock()
    wrapper = cached._wrapper(
        func,
        cache=cache,
        key=first_arg_key,
        lock=lock,
        cond=None,
        info=simple_info,
    )

    # No hits yet
    assert wrapper.cache_info() == (0, 0)

    # First call: miss
    assert wrapper(10) == 11
    assert wrapper.cache_info() == (0, 1)

    # Second call: hit
    assert wrapper(10) == 11
    assert wrapper.cache_info() == (1, 1)

    # Clear and verify counts reset
    wrapper.cache_clear()
    assert wrapper.cache_info() == (0, 0)
    assert calls == [10]  # only one actual computation


def test_condition_wrapper_prevents_reentrancy_and_counts():
    # Simulate a function that would be called recursively if not guarded
    call_order = []

    def func(x):
        call_order.append(f"enter-{x}")
        # Simulate some work
        result = x * x
        call_order.append(f"exit-{x}")
        return result

    cache = {}
    lock = threading.Lock()
    cond = threading.Condition(lock)

    wrapper = cached._wrapper(
        func,
        cache=cache,
        key=first_arg_key,
        lock=lock,
        cond=cond,
        info=simple_info,
    )

    # First call: miss
    assert wrapper(4) == 16
    assert wrapper.cache_info() == (0, 1)
    assert cache[4] == 16
    assert call_order == ["enter-4", "exit-4"]

    # Second call: hit, no extra function calls
    call_order.clear()
    assert wrapper(4) == 16
    assert wrapper.cache_info() == (1, 1)
    assert call_order == []


def test_uncached_with_info_counts_misses_only():
    calls = []

    def func(x):
        calls.append(x)
        return x - 1

    wrapper = cached._wrapper(
        func,
        cache=None,
        key=first_arg_key,
        lock=None,
        cond=None,
        info=simple_info,
    )

    # No cache, each call is a miss
    assert wrapper(5) == 4
    assert wrapper.cache_info() == (0, 1)
    assert wrapper(5) == 4
    assert wrapper.cache_info() == (0, 2)
    assert calls == [5, 5]

    # cache_clear should reset miss count
    wrapper.cache_clear()
    assert wrapper.cache_info() == (0, 0)


def test_bad_cache_value_is_not_stored_but_returned():
    calls = []

    def func(x):
        calls.append(x)
        return "bad" if x == 1 else "good"

    cache = BadCache()
    wrapper = cached._wrapper(
        func,
        cache=cache,
        key=first_arg_key,
        lock=None,
        cond=None,
        info=simple_info,
    )

    # First call with value that triggers ValueError on setitem
    assert wrapper(1) == "bad"
    # The key should not be stored because of the exception
    assert 1 not in cache

    # Subsequent call should recompute (calls list grows)
    assert wrapper(1) == "bad"
    assert calls == [1, 1]

    # Normal value should be cached
    assert wrapper(2) == "good"
    assert cache[2] == "good"
    # Second call hits cache, no extra function call
    calls_before = len(calls)
    assert wrapper(2) == "good"
    assert len(calls) == calls_before


def test_wrapper_exposes_expected_attributes():
    def func(x):
        return x

    cache = {}
    lock = threading.Lock()
    cond = threading.Condition(lock)

    wrapper = cached._wrapper(
        func,
        cache=cache,
        key=first_arg_key,
        lock=lock,
        cond=cond,
        info=simple_info,
    )

    # Verify that the wrapper carries the metadata attributes
    assert wrapper.cache is cache
    assert wrapper.cache_key is first_arg_key
    # When both lock and cond are provided, cache_lock should be the lock
    assert wrapper.cache_lock is lock
    assert wrapper.cache_condition is cond
    # The wrapper should preserve the original function's name and docstring
    assert wrapper.__name__ == func.__name__
    assert wrapper.__doc__ == func.__doc__
