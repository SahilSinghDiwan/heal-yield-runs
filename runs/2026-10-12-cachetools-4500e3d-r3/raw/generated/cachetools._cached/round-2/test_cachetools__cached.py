import threading

import pytest

from cachetools import _cached as _cached


def test_uncached_decorator_returns_original_result_and_has_no_effectful_cache_clear():
    """_uncached should simply call the function and have a no‑op cache_clear."""
    call_log = []

    def func(x):
        call_log.append(x)
        return f"val-{x}"

    wrapper = _cached._wrapper(func, cache=None, key=lambda x: x, lock=None, cond=None, info=None)

    # The wrapper should return the original function's result.
    assert wrapper("a") == "val-a"
    # The underlying function should have been called exactly once.
    assert call_log == ["a"]
    # cache_clear should be a no‑op and not raise.
    wrapper.cache_clear()
    # Subsequent call still works.
    assert wrapper("b") == "val-b"
    assert call_log == ["a", "b"]


def test_uncached_info_tracks_misses_and_resets_on_clear():
    """_uncached_info should count misses and reset on cache_clear."""
    call_log = []

    def func(x):
        call_log.append(x)
        return f"val-{x}"

    info = lambda hits, misses: (hits, misses)
    wrapper = _cached._wrapper(func, cache=None, key=lambda x: x, lock=None, cond=None, info=info)

    # First call counts as a miss.
    assert wrapper("x") == "val-x"
    assert wrapper.cache_info() == (0, 1)
    # Second call also a miss (no caching).
    assert wrapper("y") == "val-y"
    assert wrapper.cache_info() == (0, 2)

    # cache_clear resets the miss count.
    wrapper.cache_clear()
    assert wrapper.cache_info() == (0, 0)


def test_unlocked_caches_without_lock_and_hits_misses_are_not_tracked():
    """_unlocked should cache values but not provide cache_info."""
    call_log = []

    def func(x):
        call_log.append(x)
        return f"val-{x}"

    cache = {}
    wrapper = _cached._wrapper(func, cache=cache, key=lambda x: x, lock=None, cond=None, info=None)

    # First call computes and stores.
    assert wrapper("k") == "val-k"
    assert cache["k"] == "val-k"
    # Second call hits the cache, func not called again.
    assert wrapper("k") == "val-k"
    assert call_log == ["k"]
    # cache_info should be None for this configuration.
    assert wrapper.cache_info is None


def test_unlocked_info_tracks_hits_and_misses():
    """_unlocked_info should cache and track hits/misses."""
    call_log = []

    def func(x):
        call_log.append(x)
        return f"val-{x}"

    info = lambda hits, misses: (hits, misses)
    cache = {}
    wrapper = _cached._wrapper(func, cache=cache, key=lambda x: x, lock=None, cond=None, info=info)

    # Miss on first call.
    assert wrapper("a") == "val-a"
    assert wrapper.cache_info() == (0, 1)
    # Hit on second call.
    assert wrapper("a") == "val-a"
    assert wrapper.cache_info() == (1, 1)
    # Miss on a new key.
    assert wrapper("b") == "val-b"
    assert wrapper.cache_info() == (1, 2)


def test_locked_caches_with_thread_lock_and_respects_race_condition():
    """_locked should use a lock and prefer a cached value if set during the call."""
    call_log = []

    def func(x):
        call_log.append(x)
        return f"val-{x}"

    lock = threading.Lock()
    cache = {}
    wrapper = _cached._wrapper(func, cache=cache, key=lambda x: x, lock=lock, cond=None, info=None)

    # First call computes and stores.
    assert wrapper("z") == "val-z"
    assert cache["z"] == "val-z"
    # Simulate a race: manually replace the cached value before the second call.
    cache["z"] = "race-val-z"
    # Second call should return the race‑injected value without calling func.
    assert wrapper("z") == "race-val-z"
    # func should have been called only once.
    assert call_log == ["z"]


def test_locked_info_tracks_hits_and_misses_and_respects_lock():
    """_locked_info should track hits/misses and respect the provided lock."""
    call_log = []

    def func(x):
        call_log.append(x)
        return f"val-{x}"

    lock = threading.Lock()
    info = lambda hits, misses: (hits, misses)
    cache = {}
    wrapper = _cached._wrapper(func, cache=cache, key=lambda x: x, lock=lock, cond=None, info=info)

    # Miss on first call.
    assert wrapper("m") == "val-m"
    assert wrapper.cache_info() == (0, 1)
    # Hit on second call.
    assert wrapper("m") == "val-m"
    assert wrapper.cache_info() == (1, 1)
    # Ensure the lock is the one we passed.
    assert wrapper.cache_lock is lock
    # func called only once.
    assert call_log == ["m"]


def test_condition_decorator_handles_pending_set_and_exception_cleanup():
    """_condition should clean up the pending set even when the wrapped function raises."""
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
        info=None,
    )

    # Normal call populates cache.
    assert wrapper("good") == "val-good"
    assert cache["good"] == "val-good"

    # Exception should not leave the key in the pending set.
    with pytest.raises(ValueError):
        wrapper("bad")
    # After the exception the key must not be cached.
    assert "bad" not in cache
    # A subsequent call with the same bad key should raise again (pending set cleared).
    with pytest.raises(ValueError):
        wrapper("bad")
    # call_log should contain both attempts.
    assert call_log == ["good", "bad", "bad"]


def test_condition_info_tracks_hits_and_misses_and_cleans_up_pending():
    """_condition_info should track hits/misses and always clean pending."""
    lock = threading.Lock()
    cond = threading.Condition(lock)
    cache = {}

    info = lambda hits, misses: (hits, misses)

    call_log = []

    def func(x):
        call_log.append(x)
        if x == "bad":
            raise RuntimeError("bad")
        return f"val-{x}"

    wrapper = _cached._wrapper(
        func,
        cache=cache,
        key=lambda x: x,
        lock=lock,
        cond=cond,
        info=info,
    )

    # First good call: miss.
    assert wrapper("ok") == "val-ok"
    assert wrapper.cache_info() == (0, 1)
    # Second good call: hit.
    assert wrapper("ok") == "val-ok"
    assert wrapper.cache_info() == (1, 1)

    # Bad call raises and does not affect cache.
    with pytest.raises(RuntimeError):
        wrapper("bad")
    assert wrapper.cache_info() == (1, 2)  # miss incremented

    # Ensure pending set is cleared (no residual effect).
    assert "bad" not in cache
    # Subsequent good call still works.
    assert wrapper("new") == "val-new"
    assert wrapper.cache_info() == (1, 3)


def test_wrapper_attribute_exposure():
    """All wrapper variants should expose the expected attributes."""
    lock = threading.Lock()
    cond = threading.Condition(lock)
    cache = {}
    info = lambda h, m: (h, m)

    def func(x):
        return f"val-{x}"

    # Unlocked with info
    w1 = _cached._wrapper(func, cache=cache, key=lambda x: x, lock=None, cond=None, info=info)
    assert w1.cache is cache
    assert w1.cache_key is not None
    assert w1.cache_lock is None
    assert w1.cache_condition is None
    assert callable(w1.cache_info)

    # Locked with lock only
    w2 = _cached._wrapper(func, cache=cache, key=lambda x: x, lock=lock, cond=None, info=None)
    assert w2.cache_lock is lock
    assert w2.cache_condition is None
    assert w2.cache_info is None

    # Condition with both lock and cond
    w3 = _cached._wrapper(func, cache=cache, key=lambda x: x, lock=lock, cond=cond, info=None)
    assert w3.cache_lock is lock
    assert w3.cache_condition is cond
    assert w3.cache_info is None
