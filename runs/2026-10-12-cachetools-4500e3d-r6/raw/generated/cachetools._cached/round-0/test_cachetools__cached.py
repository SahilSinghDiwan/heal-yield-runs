import threading
import time

import pytest
from cachetools import _cached


def identity_key(*args, **kwargs):
    """Simple key function that returns the positional arguments as a tuple."""
    return args


def info_func(hits, misses):
    """Info function used in wrappers – just returns a tuple."""
    return hits, misses


def test_uncached_wrapper_calls_function_and_has_no_info():
    """_uncached should simply call the function and expose no cache_info."""
    calls = []

    def func(x):
        calls.append(x)
        return x * 2

    wrapper = _cached._wrapper(func, cache=None, key=identity_key, lock=None, cond=None, info=None)

    assert wrapper(3) == 6
    assert wrapper(4) == 8
    # function should have been called for each invocation
    assert calls == [3, 4]
    # cache related attributes
    assert wrapper.cache is None
    assert wrapper.cache_key is identity_key
    assert wrapper.cache_lock is None
    assert wrapper.cache_condition is None
    # cache_info is explicitly set to None for uncached wrappers
    assert wrapper.cache_info is None


def test_uncached_info_counts_misses_and_clears():
    """_uncached_info should count misses and be resettable."""
    calls = []

    def func(x):
        calls.append(x)
        return x + 1

    wrapper = _cached._wrapper(func, cache=None, key=identity_key, lock=None, cond=None, info=info_func)

    # two calls – both are misses
    assert wrapper(1) == 2
    assert wrapper(2) == 3
    assert calls == [1, 2]
    assert wrapper.cache_info() == (0, 2)  # hits always 0 for uncached

    # clear the miss counter
    wrapper.cache_clear()
    assert wrapper.cache_info() == (0, 0)
    # calling again increments misses again
    assert wrapper(3) == 4
    assert wrapper.cache_info() == (0, 1)


def test_locked_wrapper_caches_and_counts_hits_and_misses():
    """_locked (and _locked_info) should cache results and track hits/misses."""
    cache = {}
    lock = threading.Lock()
    calls = []

    def func(x):
        calls.append(x)
        return x * x

    wrapper = _cached._wrapper(func, cache=cache, key=identity_key, lock=lock, cond=None, info=info_func)

    # first call – miss
    assert wrapper(3) == 9
    assert calls == [3]
    assert cache == {(3,): 9}
    # second call – hit
    assert wrapper(3) == 9
    assert calls == [3]  # no new call
    # different argument – miss again
    assert wrapper(4) == 16
    assert calls == [3, 4]
    # verify hit/miss counts
    assert wrapper.cache_info() == (1, 2)  # 1 hit, 2 misses

    # clear cache and counters
    wrapper.cache_clear()
    assert wrapper.cache_info() == (0, 0)
    assert cache == {}
    # after clear, a call is a miss again
    assert wrapper(3) == 9
    assert wrapper.cache_info() == (0, 1)


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
        return x * 5  # will be >10 for x>=3

    wrapper = _cached._wrapper(func, cache=cache, key=identity_key, lock=lock, cond=None, info=info_func)

    # first call – miss, but value too large to store
    assert wrapper(3) == 15
    assert calls == [3]
    assert  (3,) not in cache  # not stored
    # second call – still a miss because not cached
    assert wrapper(3) == 15
    assert calls == [3, 3]
    # hit/miss counters reflect two misses, zero hits
    assert wrapper.cache_info() == (0, 2)


def test_condition_wrapper_blocks_and_caches():
    """_condition should block concurrent calls for the same key until the first finishes."""
    lock = threading.Lock()
    cond = threading.Condition(lock)
    cache = {}
    call_counter = 0
    start_event = threading.Event()
    finish_event = threading.Event()

    def func(x):
        nonlocal call_counter
        call_counter += 1
        start_event.set()          # signal that the function has started
        finish_event.wait(1)       # wait a bit (or until test releases)
        return x * 10

    wrapper = _cached._wrapper(func, cache=cache, key=identity_key, lock=lock, cond=cond, info=None)

    # Thread 1 will start the computation
    t1 = threading.Thread(target=lambda: wrapper(2))
    t1.start()
    # Wait until func has started (so key is in pending)
    assert start_event.wait(1), "func did not start in time"

    # Thread 2 calls with the same key while the first is pending
    result_holder = {}

    def call_in_thread():
        result_holder['value'] = wrapper(2)

    t2 = threading.Thread(target=call_in_thread)
    t2.start()
    # Give a tiny moment to ensure t2 is blocked on the condition
    time.sleep(0.05)
    # At this point, call_counter should still be 1 (t2 hasn't called func)
    assert call_counter == 1

    # Release the first computation
    finish_event.set()
    t1.join()
    t2.join()

    # Both threads should have received the same result
    assert result_holder['value'] == 20
    # func should have been called only once
    assert call_counter == 1
    # The result should now be cached
    assert cache == {(2,): 20}


def test_condition_info_counts_and_clears():
    """_condition_info should count hits/misses and be resettable."""
    lock = threading.Lock()
    cond = threading.Condition(lock)
    cache = {}
    calls = []

    def func(x):
        calls.append(x)
        return x + 100

    wrapper = _cached._wrapper(func, cache=cache, key=identity_key,
                              lock=lock, cond=cond, info=info_func)

    # First call – miss
    assert wrapper(5) == 105
    assert calls == [5]
    # Second call – hit
    assert wrapper(5) == 105
    assert calls == [5]  # no new call
    # Verify hit/miss counts
    assert wrapper.cache_info() == (1, 1)

    # Clear cache and counters
    wrapper.cache_clear()
    assert wrapper.cache_info() == (0, 0)
    assert cache == {}
    # After clear, a call is a miss again
    assert wrapper(5) == 105
    assert wrapper.cache_info() == (0, 1)


def test_wrapper_attribute_exposure():
    """All wrappers should expose cache, cache_key, cache_lock, and cache_condition attributes."""
    cache = {}
    lock = threading.Lock()
    cond = threading.Condition(lock)

    def func(x):
        return x

    # No lock, no condition, with cache
    w1 = _cached._wrapper(func, cache=cache, key=identity_key, lock=None, cond=None, info=None)
    assert w1.cache is cache
    assert w1.cache_key is identity_key
    assert w1.cache_lock is None
    assert w1.cache_condition is None

    # With lock only
    w2 = _cached._wrapper(func, cache=cache, key=identity_key, lock=lock, cond=None, info=None)
    assert w2.cache_lock is lock
    assert w2.cache_condition is None

    # With condition only (lock is None, cond provided)
    w3 = _cached._wrapper(func, cache=cache, key=identity_key, lock=None, cond=cond, info=None)
    # In this case the implementation passes cond as both lock and cond
    assert w3.cache_lock is cond
    assert w3.cache_condition is cond

    # With both lock and condition
    w4 = _cached._wrapper(func, cache=cache, key=identity_key, lock=lock, cond=cond, info=None)
    assert w4.cache_lock is lock
    assert w4.cache_condition is cond
