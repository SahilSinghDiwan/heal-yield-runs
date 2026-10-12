# test_cachetools__cached.py
import threading

import pytest

from cachetools import _cached


def test_uncached_decorator_returns_original_result_and_has_no_effectful_cache_clear():
    calls = []

    def func(x):
        calls.append(x)
        return x * 2

    # Use the low‑level _wrapper to create an uncached decorator (no cache, no info)
    wrapper = _cached._wrapper(func, cache=None, key=lambda x: x)

    # The wrapper should behave like the original function
    assert wrapper(3) == 6
    assert calls == [3]

    # cache_clear should be a no‑op and not raise
    wrapper.cache_clear()
    # Calling again should still work and record another call
    assert wrapper(4) == 8
    assert calls == [3, 4]


def test_uncached_info_tracks_misses_and_resets_on_clear():
    calls = []

    def func(x):
        calls.append(x)
        return x + 1

    # info function returns a tuple (hits, misses)
    info = lambda hits, misses: (hits, misses)

    wrapper = _cached._wrapper(
        func,
        cache=None,
        key=lambda x: x,
        info=info,
    )

    # No caching, so each call is a miss
    assert wrapper(1) == 2
    assert wrapper(2) == 3
    assert wrapper.cache_info() == (0, 2)

    # cache_clear should reset the miss counter
    wrapper.cache_clear()
    assert wrapper.cache_info() == (0, 0)


def test_unlocked_caches_without_lock_and_hits_misses_are_not_tracked():
    calls = []

    def func(x):
        calls.append(x)
        return x * x

    cache = {}
    wrapper = _cached._wrapper(func, cache=cache, key=lambda x: x)

    # First call populates the cache
    assert wrapper(2) == 4
    assert calls == [2]
    # Second call hits the cache; no hit/miss tracking is exposed
    assert wrapper(2) == 4
    assert calls == [2]  # no additional call

    # cache_clear should empty the underlying cache
    wrapper.cache_clear()
    assert cache == {}
    # After clearing, a new call recomputes
    assert wrapper(2) == 4
    assert calls == [2, 2]


def test_unlocked_info_tracks_hits_and_misses():
    calls = []

    def func(x):
        calls.append(x)
        return x - 1

    cache = {}
    info = lambda hits, misses: {"hits": hits, "misses": misses}
    wrapper = _cached._wrapper(
        func,
        cache=cache,
        key=lambda x: x,
        info=info,
    )

    # First call is a miss
    assert wrapper(5) == 4
    assert wrapper.cache_info() == {"hits": 0, "misses": 1}
    # Second call hits the cache
    assert wrapper(5) == 4
    assert wrapper.cache_info() == {"hits": 1, "misses": 1}
    # Different key is another miss
    assert wrapper(6) == 5
    assert wrapper.cache_info() == {"hits": 1, "misses": 2}


def test_locked_caches_with_thread_lock_and_respects_race_condition():
    lock = threading.Lock()
    cache = {}

    call_counter = {"count": 0}

    def func(x):
        # Simulate work
        call_counter["count"] += 1
        return x * 10

    wrapper = _cached._wrapper(
        func,
        cache=cache,
        key=lambda x: x,
        lock=lock,
    )

    # First call populates cache
    assert wrapper(1) == 10
    assert call_counter["count"] == 1
    # Second call should hit cache without invoking func again
    assert wrapper(1) == 10
    assert call_counter["count"] == 1

    # Simulate a race: manually insert a value while another thread would be computing
    cache[2] = 20
    # Wrapper should prefer the existing cached value
    assert wrapper(2) == 20
    # No extra call to func
    assert call_counter["count"] == 1


def test_locked_info_tracks_hits_and_misses_and_respects_lock():
    lock = threading.Lock()
    cache = {}
    info = lambda h, m: (h, m)

    call_counter = {"c": 0}

    def func(x):
        call_counter["c"] += 1
        return x * 3

    wrapper = _cached._wrapper(
        func,
        cache=cache,
        key=lambda x: x,
        lock=lock,
        info=info,
    )

    # Miss
    assert wrapper(2) == 6
    assert wrapper.cache_info() == (0, 1)
    # Hit
    assert wrapper(2) == 6
    assert wrapper.cache_info() == (1, 1)
    # Another miss
    assert wrapper(3) == 9
    assert wrapper.cache_info() == (1, 2)


def test_condition_decorator_handles_pending_set_and_exception_cleanup():
    lock = threading.Lock()
    cond = threading.Condition(lock)
    cache = {}

    call_log = []

    def func(x):
        call_log.append(x)
        if x == "bad":
            raise ValueError("bad input")
        return f"val-{x}"

    wrapper = _cached._wrapper(
        func,
        cache=cache,
        key=lambda x: x,
        lock=lock,
        cond=cond,
    )

    # Normal call populates cache
    assert wrapper("good") == "val-good"
    assert cache["good"] == "val-good"

    # Exception should not leave the key in the pending set
    with pytest.raises(ValueError):
        wrapper("bad")
    # After exception, we can still compute a good value for the same key
    assert wrapper("bad") == "val-bad"
    assert cache["bad"] == "val-bad"


def test_condition_info_tracks_hits_and_misses_and_cleans_up_pending():
    lock = threading.Lock()
    cond = threading.Condition(lock)
    cache = {}
    info = lambda h, m: {"hits": h, "misses": m}
    call_log = []

    def func(x):
        call_log.append(x)
        return f"out-{x}"

    wrapper = _cached._wrapper(
        func,
        cache=cache,
        key=lambda x: x,
        lock=lock,
        cond=cond,
        info=info,
    )

    # First call is a miss
    assert wrapper("a") == "out-a"
    assert wrapper.cache_info() == {"hits": 0, "misses": 1}
    # Second call hits cache
    assert wrapper("a") == "out-a"
    assert wrapper.cache_info() == {"hits": 1, "misses": 1}
    # Ensure pending set is cleaned up after each call
    # (no direct access, but we can verify that subsequent calls work)
    assert wrapper("b") == "out-b"
    assert wrapper.cache_info() == {"hits": 1, "misses": 2}


def test_wrapper_attribute_exposure():
    lock = threading.Lock()
    cond = threading.Condition(lock)
    cache = {}
    info = lambda h, m: (h, m)

    def func(x):
        return x

    wrapper = _cached._wrapper(
        func,
        cache=cache,
        key=lambda x: x,
        lock=lock,
        cond=cond,
        info=info,
    )

    # Verify that the wrapper exposes the expected attributes
    assert wrapper.cache is cache
    assert wrapper.cache_key is not None
    assert wrapper.cache_lock is lock
    assert wrapper.cache_condition is cond
    # __wrapped__ should point to the original function
    assert wrapper.__wrapped__ is func
