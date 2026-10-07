import threading
import types

import pytest

from cachetools import _cached


def simple_key(*args, **kwargs):
    """Key function that uses the first positional argument."""
    return args[0] if args else None


def info_func(hits, misses):
    """Simple info collector returning a tuple."""
    return hits, misses


class BadCache(dict):
    """A dict that raises ValueError when trying to store a specific sentinel."""

    def __setitem__(self, key, value):
        if value == "bad":
            raise ValueError("value too large")
        super().__setitem__(key, value)


def test_unlocked_wrapper_caches_and_clears():
    """Unlocked wrapper should cache results and clear correctly."""
    cache = {}
    calls = []

    def func(x):
        calls.append(x)
        return x * 2

    wrapper = _cached._wrapper(
        func,
        cache=cache,
        key=simple_key,
        lock=None,
        cond=None,
        info=None,
    )

    # First call – cache miss
    assert wrapper(3) == 6
    assert calls == [3]
    assert cache == {3: 6}

    # Second call – cache hit, no new call recorded
    assert wrapper(3) == 6
    assert calls == [3]

    # Clear cache – should reset internal state
    wrapper.cache_clear()
    assert cache == {}
    # After clearing, function should be called again
    assert wrapper(3) == 6
    assert calls == [3, 3]


def test_locked_wrapper_respects_lock_and_counts():
    """Locked wrapper should use the provided lock and expose cache_info as None."""
    lock = threading.Lock()
    cache = {}
    calls = []

    def func(x):
        calls.append(x)
        return x + 1

    wrapper = _cached._wrapper(
        func,
        cache=cache,
        key=simple_key,
        lock=lock,
        cond=None,
        info=None,
    )

    # Ensure the lock attribute is the one we passed
    assert wrapper.cache_lock is lock
    # No info function – cache_info should be None
    assert wrapper.cache_info is None

    # First call – miss
    assert wrapper(10) == 11
    assert calls == [10]
    assert cache == {10: 11}

    # Second call – hit
    assert wrapper(10) == 11
    assert calls == [10]

    # Clear cache
    wrapper.cache_clear()
    assert cache == {}
    # After clearing, function called again
    assert wrapper(10) == 11
    assert calls == [10, 10]


def test_condition_wrapper_prevents_reentrancy_and_counts():
    """Condition wrapper should prevent re‑entrancy for the same key."""
    lock = threading.Lock()
    cond = threading.Condition(lock)
    cache = {}
    calls = []

    def func(x):
        calls.append(x)
        return x * x

    wrapper = _cached._wrapper(
        func,
        cache=cache,
        key=simple_key,
        lock=lock,
        cond=cond,
        info=None,
    )

    # Ensure condition attribute is set correctly
    assert wrapper.cache_condition is cond

    # First call – miss
    assert wrapper(4) == 16
    assert calls == [4]
    assert cache == {4: 16}

    # Second call – hit
    assert wrapper(4) == 16
    assert calls == [4]

    # Clear cache
    wrapper.cache_clear()
    assert cache == {}
    # After clearing, function called again
    assert wrapper(4) == 16
    assert calls == [4, 4]


def test_info_wrappers_track_hits_and_misses():
    """Wrappers with an info function should report correct hit/miss counts."""
    lock = threading.Lock()
    cache = {}
    calls = []

    def func(x):
        calls.append(x)
        return x + 5

    # Locked wrapper with info
    wrapper = _cached._wrapper(
        func,
        cache=cache,
        key=simple_key,
        lock=lock,
        cond=None,
        info=info_func,
    )

    # Initially no hits or misses
    assert wrapper.cache_info() == (0, 0)

    # First call – miss
    assert wrapper(1) == 6
    assert wrapper.cache_info() == (0, 1)

    # Second call – hit
    assert wrapper(1) == 6
    assert wrapper.cache_info() == (1, 1)

    # Clear and verify reset
    wrapper.cache_clear()
    assert wrapper.cache_info() == (0, 0)


def test_uncached_with_info_counts_misses_only():
    """Uncached wrapper with info should only count misses."""
    calls = []

    def func(x):
        calls.append(x)
        return x * 3

    wrapper = _cached._wrapper(
        func,
        cache=None,
        key=simple_key,
        lock=None,
        cond=None,
        info=info_func,
    )

    # No hits possible – only misses
    assert wrapper.cache_info() == (0, 0)
    assert wrapper(2) == 6
    assert wrapper.cache_info() == (0, 1)
    assert wrapper(3) == 9
    assert wrapper.cache_info() == (0, 2)

    # Clear resets miss count
    wrapper.cache_clear()
    assert wrapper.cache_info() == (0, 0)


def test_bad_cache_value_is_not_stored_but_returned():
    """When the cache raises ValueError, the value should still be returned."""
    cache = BadCache()
    calls = []

    def func(x):
        calls.append(x)
        return "bad" if x == "trigger" else "good"

    wrapper = _cached._wrapper(
        func,
        cache=cache,
        key=simple_key,
        lock=None,
        cond=None,
        info=None,
    )

    # Normal value is stored
    assert wrapper("ok") == "good"
    assert cache["ok"] == "good"

    # Bad value raises ValueError inside the wrapper but is returned
    assert wrapper("trigger") == "bad"
    # The bad value should NOT be present in the cache
    assert "trigger" not in cache
    # Function should have been called twice total
    assert calls == ["ok", "trigger"]


def test_wrapper_exposes_expected_attributes():
    """All wrapper attributes should be set according to the arguments."""
    lock = threading.Lock()
    cond = threading.Condition(lock)
    cache = {}
    wrapper = _cached._wrapper(
        lambda x: x,
        cache=cache,
        key=simple_key,
        lock=lock,
        cond=cond,
        info=info_func,
    )

    # Core attributes
    assert wrapper.cache is cache
    assert wrapper.cache_key is simple_key
    # When both lock and cond are supplied, cache_lock should be the lock
    assert wrapper.cache_lock is lock
    assert wrapper.cache_condition is cond

    # The wrapper should preserve metadata of the original function
    assert wrapper.__name__ == "<lambda>"
    # __doc__ should be None for a lambda, but update_wrapper still works
    assert isinstance(wrapper, types.FunctionType)
