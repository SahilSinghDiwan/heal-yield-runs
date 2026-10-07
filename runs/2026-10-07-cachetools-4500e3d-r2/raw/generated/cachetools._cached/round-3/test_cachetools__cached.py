import threading

import pytest

from cachetools import _cached as cached


# Simple key function: use the first positional argument as the cache key
def simple_key(*args, **kwargs):
    return args[0] if args else None


# Simple info function that returns a tuple (hits, misses)
def info_func(hits, misses):
    return hits, misses


# A cache that raises ValueError when trying to store a value larger than max_value.
# It also raises on setdefault for the same condition.
class ValueErrorCache(dict):
    def __init__(self, max_value):
        super().__init__()
        self.max_value = max_value

    def __setitem__(self, key, value):
        if value > self.max_value:
            raise ValueError("value too large")
        super().__setitem__(key, value)

    def setdefault(self, key, default=None):
        if key in self:
            return self[key]
        # Mimic dict's behaviour but enforce the size check
        if default is not None and default > self.max_value:
            raise ValueError("value too large")
        return super().setdefault(key, default)


def test_unlocked_wrapper_caches_and_clears():
    """_unlocked wrapper should cache results and allow clearing."""
    cache = {}
    calls = []

    def func(x):
        calls.append(x)
        return x * 2

    wrapper = cached._wrapper(func, cache, simple_key)

    # First call – cache miss
    assert wrapper(1) == 2
    assert calls == [1]
    assert cache[1] == 2

    # Second call – cache hit, no new call recorded
    assert wrapper(1) == 2
    assert calls == [1]

    # Clear the cache and ensure the function is called again
    wrapper.cache_clear()
    assert 1 not in cache
    assert wrapper(1) == 2
    assert calls == [1, 1]


def test_locked_wrapper_respects_lock_and_counts():
    """_locked wrapper should respect the lock and report hit/miss counts."""
    lock = threading.Lock()
    cache = {}
    calls = []

    def func(x):
        calls.append(x)
        return x + 5

    wrapper = cached._wrapper(func, cache, simple_key, lock=lock, info=info_func)

    # First call – miss
    assert wrapper(10) == 15
    assert calls == [10]
    hits, misses = wrapper.cache_info()
    assert hits == 0 and misses == 1

    # Second call – hit
    assert wrapper(10) == 15
    assert calls == [10]  # no new call
    hits, misses = wrapper.cache_info()
    assert hits == 1 and misses == 1

    # Clear and verify counters reset
    wrapper.cache_clear()
    hits, misses = wrapper.cache_info()
    assert hits == 0 and misses == 0
    assert 10 not in cache


def test_condition_wrapper_prevents_reentrancy_and_counts():
    """_condition wrapper should prevent re‑entrancy for the same key."""
    lock = threading.Lock()
    cond = threading.Condition(lock)
    cache = {}
    calls = []

    def func(x):
        calls.append(x)
        return x * 3

    wrapper = cached._wrapper(func, cache, simple_key, lock=lock, cond=cond, info=info_func)

    # First call – miss
    assert wrapper(2) == 6
    assert calls == [2]
    hits, misses = wrapper.cache_info()
    assert hits == 0 and misses == 1

    # Second call – hit
    assert wrapper(2) == 6
    assert calls == [2]  # no additional call
    hits, misses = wrapper.cache_info()
    assert hits == 1 and misses == 1

    # Simulate concurrent calls for the same key using threads.
    # Both threads request the same key; the function should execute only once.
    start_evt = threading.Event()
    done_evt = threading.Event()
    concurrent_calls = []

    def thread_target():
        start_evt.wait()
        concurrent_calls.append(wrapper(3))
        done_evt.set()

    t = threading.Thread(target=thread_target)
    t.start()
    # Ensure the thread is ready and then trigger the call
    start_evt.set()
    # While the thread is running, call the same key from the main thread
    main_result = wrapper(3)
    done_evt.wait()
    t.join()

    # The function should have been called only once for key 3
    assert calls.count(3) == 1
    # Both results should be identical
    assert concurrent_calls[0] == main_result == 9


def test_uncached_with_info_counts_misses_only():
    """When no cache is supplied but info is, only misses should be counted."""
    calls = []

    def func(x):
        calls.append(x)
        return x - 1

    wrapper = cached._wrapper(func, cache=None, key=simple_key, info=info_func)

    # Both calls are misses
    assert wrapper(5) == 4
    assert wrapper(6) == 5
    assert calls == [5, 6]

    hits, misses = wrapper.cache_info()
    assert hits == 0 and misses == 2

    # cache_clear should reset the miss counter
    wrapper.cache_clear()
    hits, misses = wrapper.cache_info()
    assert hits == 0 and misses == 0


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
    # The value should not be stored because the cache raised ValueError.
    assert 3 not in cache
    # The function should have been called exactly once.
    assert calls == [3]


def test_wrapper_exposes_expected_attributes():
    """All wrappers should expose cache, key, lock, and condition attributes."""
    lock = threading.Lock()
    cond = threading.Condition(lock)
    cache = {}

    def func(x):
        return x

    # Unlocked, no info
    w1 = cached._wrapper(func, cache, simple_key)
    assert w1.cache is cache
    assert w1.cache_key is simple_key
    assert w1.cache_lock is None
    assert w1.cache_condition is None

    # Locked, no info
    w2 = cached._wrapper(func, cache, simple_key, lock=lock)
    assert w2.cache_lock is lock
    assert w2.cache_condition is None

    # Condition, no info
    w3 = cached._wrapper(func, cache, simple_key, lock=lock, cond=cond)
    assert w3.cache_lock is lock
    assert w3.cache_condition is cond

    # Unlocked with info
    w4 = cached._wrapper(func, cache, simple_key, info=info_func)
    assert w4.cache_lock is None
    assert w4.cache_condition is None

    # Locked with info
    w5 = cached._wrapper(func, cache, simple_key, lock=lock, info=info_func)
    assert w5.cache_lock is lock
    assert w5.cache_condition is None

    # Condition with info
    w6 = cached._wrapper(func, cache, simple_key, lock=lock, cond=cond, info=info_func)
    assert w6.cache_lock is lock
    assert w6.cache_condition is cond
