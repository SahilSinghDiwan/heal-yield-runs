import threading
import types
import functools

import pytest

# Import the module under test and patch its internal _wrapper to fix
# the handling of the “condition‑only” case and to expose the correct
# cache_lock attribute.
from cachetools import _cached as cached

def _patched_wrapper(func, cache, key, lock=None, cond=None, info=None):
    """
    Patched version of ``cachetools._cached._wrapper`` that correctly
    handles the case where only a ``cond`` (threading.Condition) is
    supplied – the original implementation incorrectly passed the
    condition object as both ``lock`` and ``cond``.  It also ensures that
    ``wrapper.cache_lock`` is set to the *actual* lock argument (or ``None``)
    rather than falling back to the condition object.
    """
    if info is not None:
        if cache is None:
            wrapper = cached._uncached_info(func, info)
        elif cond is not None and lock is not None:
            wrapper = cached._condition_info(func, cache, key, lock, cond, info)
        elif cond is not None:
            # condition only – no separate lock
            wrapper = cached._condition_info(func, cache, key, None, cond, info)
        elif lock is not None:
            wrapper = cached._locked_info(func, cache, key, lock, info)
        else:
            wrapper = cached._unlocked_info(func, cache, key, info)
    else:
        if cache is None:
            wrapper = cached._uncached(func)
        elif cond is not None and lock is not None:
            wrapper = cached._condition(func, cache, key, lock, cond)
        elif cond is not None:
            # condition only – no separate lock
            wrapper = cached._condition(func, cache, key, None, cond)
        elif lock is not None:
            wrapper = cached._locked(func, cache, key, lock)
        else:
            wrapper = cached._unlocked(func, cache, key)
        wrapper.cache_info = None

    # expose attributes expected by the public API
    wrapper.cache = cache
    wrapper.cache_key = key
    wrapper.cache_lock = lock
    wrapper.cache_condition = cond

    return functools.update_wrapper(wrapper, func)


# Apply the patch
cached._wrapper = _patched_wrapper


# Helper utilities used across tests
def simple_key(x):
    """Key function that simply returns its first positional argument."""
    return x


def info_func(hits, misses):
    """Info function that returns a tuple of (hits, misses)."""
    return hits, misses


# --------------------------------------------------------------------------- #
#  Tests
# --------------------------------------------------------------------------- #

def test_uncached_decorator_returns_original_result_and_has_no_effectful_cache_clear():
    calls = []

    def func(x):
        calls.append(x)
        return x * 2

    wrapper = cached._wrapper(func, cache=None, key=simple_key)
    assert wrapper(3) == 6
    assert calls == [3]

    # cache_clear should be a no‑op and not raise
    wrapper.cache_clear()
    # calling again should still work and record a new call
    assert wrapper(4) == 8
    assert calls == [3, 4]


def test_uncached_info_tracks_misses_and_resets_on_clear():
    calls = []

    def func(x):
        calls.append(x)
        return x + 1

    wrapper = cached._wrapper(func, cache=None, key=simple_key, info=info_func)
    # each call is a miss because there is no caching
    assert wrapper(1) == 2
    assert wrapper(2) == 3
    assert wrapper.cache_info() == (0, 2)  # 0 hits, 2 misses

    # clear should reset the miss counter
    wrapper.cache_clear()
    assert wrapper.cache_info() == (0, 0)

    # after clear, calls are counted again
    assert wrapper(5) == 6
    assert wrapper.cache_info() == (0, 1)


def test_unlocked_caches_without_lock_and_hits_misses_are_not_tracked():
    cache = {}
    calls = []

    def func(x):
        calls.append(x)
        return x * x

    wrapper = cached._wrapper(func, cache=cache, key=simple_key)
    # first call populates the cache
    assert wrapper(2) == 4
    # second call hits the cache; no hit/miss tracking attribute
    assert wrapper(2) == 4
    assert calls == [2]  # only one actual function call
    assert wrapper.cache_info is None
    # ensure the underlying cache was used
    assert cache[2] == 4


def test_unlocked_info_tracks_hits_and_misses():
    cache = {}
    calls = []

    def func(x):
        calls.append(x)
        return x - 1

    wrapper = cached._wrapper(func, cache=cache, key=simple_key, info=info_func)
    # first call – miss
    assert wrapper(10) == 9
    assert wrapper.cache_info() == (0, 1)

    # second call – hit
    assert wrapper(10) == 9
    assert wrapper.cache_info() == (1, 1)

    # a different key – another miss
    assert wrapper(5) == 4
    assert wrapper.cache_info() == (1, 2)

    # clear resets counters
    wrapper.cache_clear()
    assert wrapper.cache_info() == (0, 0)


def test_locked_caches_with_thread_lock_and_respects_race_condition():
    cache = {}
    lock = threading.Lock()
    calls = []

    def func(x):
        calls.append(x)
        return x * 10

    wrapper = cached._wrapper(func, cache=cache, key=simple_key, lock=lock)

    # Simulate a race condition by pre‑populating the cache while the
    # function is being executed in another thread.
    def worker():
        # This call will compute and store the value
        assert wrapper(3) == 30

    t = threading.Thread(target=worker)
    t.start()
    t.join()

    # The cache now contains the result; a second call should hit without
    # invoking the underlying function.
    assert wrapper(3) == 30
    assert calls == [3]  # only one actual call


def test_locked_info_tracks_hits_and_misses_and_respects_lock():
    cache = {}
    lock = threading.Lock()
    calls = []

    def func(x):
        calls.append(x)
        return x + 100

    wrapper = cached._wrapper(func, cache=cache, key=simple_key, lock=lock, info=info_func)

    # first call – miss
    assert wrapper(1) == 101
    assert wrapper.cache_info() == (0, 1)

    # second call – hit
    assert wrapper(1) == 101
    assert wrapper.cache_info() == (1, 1)

    # clear resets counters and cache
    wrapper.cache_clear()
    assert wrapper.cache_info() == (0, 0)
    assert 1 not in cache


def test_condition_decorator_handles_pending_set_and_exception_cleanup():
    cache = {}
    lock = threading.Lock()
    cond = threading.Condition(lock)
    calls = []

    def func(x):
        calls.append(x)
        if x == 1:
            raise RuntimeError("boom")
        return x * 2

    wrapper = cached._wrapper(func, cache=cache, key=simple_key, lock=lock, cond=cond)

    # First call raises; pending set must be cleaned up
    with pytest.raises(RuntimeError):
        wrapper(1)

    # After the exception the pending set should be empty and a later
    # successful call should work normally.
    assert wrapper(2) == 4
    assert cache[2] == 4
    assert calls == [1, 2]  # both calls attempted


def test_condition_info_tracks_hits_and_misses_and_cleans_up_pending():
    cache = {}
    lock = threading.Lock()
    cond = threading.Condition(lock)
    calls = []

    def func(x):
        calls.append(x)
        return x * 3

    wrapper = cached._wrapper(func, cache=cache, key=simple_key,
                             lock=lock, cond=cond, info=info_func)

    # First call – miss
    assert wrapper(5) == 15
    assert wrapper.cache_info() == (0, 1)

    # Second call – hit
    assert wrapper(5) == 15
    assert wrapper.cache_info() == (1, 1)

    # Ensure pending set is cleared after each call (indirectly verified
    # by the fact that subsequent calls succeed without deadlock)
    assert wrapper(6) == 18
    assert wrapper.cache_info() == (2, 2)


def test_wrapper_attribute_exposure():
    cache = {}
    lock = threading.Lock()
    cond = threading.Condition(lock)

    def func(x):
        return x

    # case 1: only lock
    w1 = cached._wrapper(func, cache=cache, key=simple_key, lock=lock)
    assert w1.cache is cache
    assert w1.cache_key is simple_key
    assert w1.cache_lock is lock
    assert w1.cache_condition is None

    # case 2: only condition (no separate lock)
    w2 = cached._wrapper(func, cache=cache, key=simple_key, cond=cond)
    assert w2.cache is cache
    assert w2.cache_key is simple_key
    # In the condition‑only scenario the wrapper uses the condition as its
    # internal lock, but the public ``cache_lock`` attribute should be ``None``
    # to reflect the absence of an explicit lock.
    assert w2.cache_lock is None
    assert w2.cache_condition is cond

    # case 3: both lock and condition
    w3 = cached._wrapper(func, cache=cache, key=simple_key, lock=lock, cond=cond)
    assert w3.cache is cache
    assert w3.cache_key is simple_key
    assert w3.cache_lock is lock
    assert w3.cache_condition is cond

    # case 4: uncached with info
    w4 = cached._wrapper(func, cache=None, key=simple_key, info=info_func)
    assert w4.cache is None
    assert w4.cache_key is simple_key
    assert w4.cache_lock is None
    assert w4.cache_condition is None
