import threading

import pytest

import cachetools._cached as cached


def test_uncached_decorator_returns_original_result_and_has_no_effectful_cache_clear():
    calls = []

    def func(x):
        calls.append(x)
        return x * 2

    wrapper = cached._uncached(func)
    assert wrapper(3) == 6
    # calling again should call the original function again
    assert wrapper(3) == 6
    assert calls == [3, 3]

    # cache_clear should be a no‑op and not raise
    wrapper.cache_clear()
    # still works after clear
    assert wrapper(4) == 8
    assert calls == [3, 3, 4]


def test_uncached_info_tracks_misses_and_resets_on_clear():
    calls = []

    def func(x):
        calls.append(x)
        return x + 1

    info = lambda hits, misses: (hits, misses)
    wrapper = cached._uncached_info(func, info)

    # first call – miss
    assert wrapper(1) == 2
    assert wrapper.cache_info() == (0, 1)

    # second call – another miss (no caching)
    assert wrapper(2) == 3
    assert wrapper.cache_info() == (0, 2)

    # clear resets miss counter
    wrapper.cache_clear()
    assert wrapper.cache_info() == (0, 0)

    # after clear, calls continue to be counted as misses
    assert wrapper(1) == 2
    assert wrapper.cache_info() == (0, 1)
    assert calls == [1, 2, 1]


def test_unlocked_caches_without_lock_and_hits_misses_are_not_tracked():
    call_counter = {"cnt": 0}

    def func(x):
        call_counter["cnt"] += 1
        return x * 3

    cache = {}
    key = lambda x: x
    wrapper = cached._unlocked(func, cache, key)

    # first call – compute and store
    assert wrapper(2) == 6
    assert call_counter["cnt"] == 1
    assert cache == {2: 6}

    # second call – should hit cache, no extra call
    assert wrapper(2) == 6
    assert call_counter["cnt"] == 1  # unchanged

    # different key – new computation
    assert wrapper(3) == 9
    assert call_counter["cnt"] == 2
    assert cache == {2: 6, 3: 9}

    # clear cache via attribute
    wrapper.cache_clear()
    assert cache == {}
    # after clear, function is called again
    assert wrapper(2) == 6
    assert call_counter["cnt"] == 3


def test_unlocked_info_tracks_hits_and_misses():
    call_counter = {"cnt": 0}

    def func(x):
        call_counter["cnt"] += 1
        return x * 5

    cache = {}
    key = lambda x: x
    info = lambda hits, misses: (hits, misses)
    wrapper = cached._unlocked_info(func, cache, key, info)

    # first call – miss
    assert wrapper(1) == 5
    assert wrapper.cache_info() == (0, 1)
    assert call_counter["cnt"] == 1

    # second call – hit
    assert wrapper(1) == 5
    assert wrapper.cache_info() == (1, 1)
    assert call_counter["cnt"] == 1  # no extra call

    # different key – miss again
    assert wrapper(2) == 10
    assert wrapper.cache_info() == (1, 2)
    assert call_counter["cnt"] == 2

    # clear resets counters and cache
    wrapper.cache_clear()
    assert wrapper.cache_info() == (0, 0)
    assert cache == {}

    # after clear, miss again
    assert wrapper(1) == 5
    assert wrapper.cache_info() == (0, 1)


def test_locked_caches_with_thread_lock_and_respects_race_condition():
    call_counter = {"cnt": 0}

    def func(x):
        call_counter["cnt"] += 1
        return x - 1

    cache = {}
    key = lambda x: x
    lock = threading.Lock()
    wrapper = cached._locked(func, cache, key, lock)

    # first call – miss, compute and store
    assert wrapper(10) == 9
    assert call_counter["cnt"] == 1
    assert cache == {10: 9}

    # second call – hit, no extra call
    assert wrapper(10) == 9
    assert call_counter["cnt"] == 1

    # simulate race: manually insert a different value before calling wrapper
    cache[20] = 100
    # wrapper will compute but should prefer existing cached value
    assert wrapper(20) == 100
    # function should not have been called for key 20
    assert call_counter["cnt"] == 1

    # clear via wrapper
    wrapper.cache_clear()
    assert cache == {}
    # after clear, function is called again
    assert wrapper(10) == 9
    assert call_counter["cnt"] == 2


def test_locked_info_tracks_hits_and_misses_and_respects_lock():
    call_counter = {"cnt": 0}

    def func(x):
        call_counter["cnt"] += 1
        return x * x

    cache = {}
    key = lambda x: x
    lock = threading.Lock()
    info = lambda hits, misses: (hits, misses)
    wrapper = cached._locked_info(func, cache, key, lock, info)

    # miss
    assert wrapper(3) == 9
    assert wrapper.cache_info() == (0, 1)
    assert call_counter["cnt"] == 1

    # hit
    assert wrapper(3) == 9
    assert wrapper.cache_info() == (1, 1)
    assert call_counter["cnt"] == 1

    # clear resets counters and cache
    wrapper.cache_clear()
    assert wrapper.cache_info() == (0, 0)
    assert cache == {}

    # miss again
    assert wrapper(4) == 16
    assert wrapper.cache_info() == (0, 1)
    assert call_counter["cnt"] == 2


def test_condition_decorator_handles_pending_set_and_exception_cleanup():
    call_counter = {"cnt": 0}
    exc_raised = {"first": True}

    def func(x):
        call_counter["cnt"] += 1
        if exc_raised["first"]:
            exc_raised["first"] = False
            raise RuntimeError("first failure")
        return x + 10

    cache = {}
    key = lambda x: x
    lock = threading.Lock()
    cond = threading.Condition(lock)
    wrapper = cached._condition(func, cache, key, lock, cond)

    # first call raises; pending must be cleared so a second call can proceed
    with pytest.raises(RuntimeError):
        wrapper(5)

    # after exception, pending set should be empty and cache unchanged
    assert cache == {}
    # second call should succeed and store result
    assert wrapper(5) == 15
    assert cache == {5: 15}
    # third call should hit cache without invoking func
    assert wrapper(5) == 15
    assert call_counter["cnt"] == 2  # only two successful executions


def test_condition_info_tracks_hits_and_misses_and_cleans_up_pending():
    call_counter = {"cnt": 0}
    fail_once = {"first": True}

    def func(x):
        call_counter["cnt"] += 1
        if fail_once["first"]:
            fail_once["first"] = False
            raise ValueError("intentional")
        return x * 2

    cache = {}
    key = lambda x: x
    lock = threading.Lock()
    cond = threading.Condition(lock)
    info = lambda hits, misses: (hits, misses)
    wrapper = cached._condition_info(func, cache, key, lock, cond, info)

    # first call raises; miss counted
    with pytest.raises(ValueError):
        wrapper(7)
    assert wrapper.cache_info() == (0, 1)

    # second call succeeds; miss counted then hit after caching
    assert wrapper(7) == 14
    assert wrapper.cache_info() == (0, 2)  # still 0 hits, 2 misses (first fail + first success)

    # third call hits cache
    assert wrapper(7) == 14
    assert wrapper.cache_info() == (1, 2)

    # clear resets everything
    wrapper.cache_clear()
    assert wrapper.cache_info() == (0, 0)
    assert cache == {}

    # after clear, a new call is a miss again
    assert wrapper(7) == 14
    assert wrapper.cache_info() == (0, 1)


def test_wrapper_attribute_exposure():
    # Use a combination that yields a locked_info wrapper
    cache = {}
    key = lambda x: x
    lock = threading.Lock()
    info = lambda h, m: (h, m)
    wrapper = cached._wrapper(
        func=lambda x: x,
        cache=cache,
        key=key,
        lock=lock,
        cond=None,
        info=info,
    )
    # attributes should be set
    assert wrapper.cache is cache
    assert wrapper.cache_key is key
    # when cond is None, cache_lock falls back to lock
    assert wrapper.cache_lock is lock
    assert wrapper.cache_condition is None
    # cache_info should be present (because info is not None)
    assert callable(wrapper.cache_info)
    # cache_clear should be present
    assert callable(wrapper.cache_clear)
