import threading

import pytest

import cachetools._cached as cached_module


def test_unlocked_cache_basic():
    """Basic functionality of an unlocked cache with info tracking."""
    hits_misses = []

    def info(h, m):
        hits_misses.append((h, m))
        return (h, m)

    def func(x):
        return x * 2

    cache = {}
    key = lambda x: x
    wrapped = cached_module._wrapper(func, cache, key, info=info)

    # First call: miss
    assert wrapped(3) == 6
    # Second call: hit
    assert wrapped(3) == 6
    # Third call with new key: miss
    assert wrapped(5) == 10

    # Access cache_info to trigger the info callback
    assert wrapped.cache_info() == (1, 2)  # 1 hit, 2 misses
    # Ensure the callback was called with the correct values
    assert hits_misses[-1] == (1, 2)


def test_locked_cache_hits_and_misses():
    """Locked cache should count hits and misses correctly via cache_info."""
    hits_misses = []

    def info(h, m):
        hits_misses.append((h, m))
        return (h, m)

    def func(x):
        return x + 1

    cache = {}
    key = lambda x: x
    lock = threading.Lock()
    wrapped = cached_module._wrapper(func, cache, key, lock=lock, info=info)

    # First call: miss
    assert wrapped(5) == 6
    # Second call: hit
    assert wrapped(5) == 6
    # Third call with new key: miss
    assert wrapped(7) == 8

    # cache_info should reflect 1 hit and 2 misses
    assert wrapped.cache_info() == (1, 2)
    # Verify the info callback received the same tuple
    assert hits_misses[-1] == (1, 2)


def test_condition_cache_with_pending():
    """Condition cache should handle pending keys correctly."""
    lock = threading.Lock()
    cond = threading.Condition(lock)

    def func(x):
        return x * x

    cache = {}
    key = lambda x: x
    wrapped = cached_module._wrapper(func, cache, key, lock=lock, cond=cond)

    # First call populates the cache
    assert wrapped(4) == 16
    # Second call retrieves from cache
    assert wrapped(4) == 16

    # Ensure the cache contains the expected entry
    assert cache[4] == 16

    # Clear the cache and verify it's empty
    wrapped.cache_clear()
    assert cache == {}


def test_uncached_with_info_counts_misses():
    """Uncached wrapper with info should count only misses."""
    calls = []

    def info(_, m):
        calls.append(m)
        return ("uncached", m)

    def func(x):
        return x - 1

    wrapped = cached_module._wrapper(func, None, lambda x: x, info=info)

    # Call several times; each should be a miss
    assert wrapped(10) == 9
    assert wrapped(20) == 19
    assert wrapped(10) == 9

    # cache_info should report 0 hits and 3 misses
    assert wrapped.cache_info() == ("uncached", 3)
    # Verify the info callback recorded the miss count correctly
    assert calls[-1] == 3


def test_uncached_without_info_has_no_cache_info():
    """Uncached wrapper without info should not provide a cache_info attribute."""
    def func():
        return "value"

    wrapped = cached_module._wrapper(func, None, lambda: None)

    # Ensure the wrapper works normally
    assert wrapped() == "value"
    # cache_info should be None as per implementation
    assert wrapped.cache_info is None


def test_wrapper_attributes_are_set_correctly():
    """All wrapper attributes should be attached to the returned function."""
    def func(x):
        return x * 3

    cache = {}
    key = lambda x: x
    lock = threading.Lock()
    cond = threading.Condition(lock)

    wrapped = cached_module._wrapper(func, cache, key, lock=lock, cond=cond, info=lambda h, m: (h, m))

    # Verify attribute presence and correctness
    assert wrapped.cache is cache
    assert wrapped.cache_key is key
    # When both lock and cond are provided, cache_lock should be the lock
    assert wrapped.cache_lock is lock
    assert wrapped.cache_condition is cond
    # The wrapper should preserve the original function's metadata
    assert wrapped.__name__ == func.__name__
    assert wrapped.__doc__ == func.__doc__


def test_value_error_on_cache_set_is_handled_gracefully():
    """If the cache raises ValueError on set, the wrapper should still return the computed value."""
    class BadCache(dict):
        def __setitem__(self, key, value):
            raise ValueError("Too large")

    def func(x):
        return x * 10

    cache = BadCache()
    key = lambda x: x
    lock = threading.Lock()
    wrapped = cached_module._wrapper(func, cache, key, lock=lock, info=lambda h, m: (h, m))

    # First call attempts to store in cache, which raises ValueError, but should still return correct result
    assert wrapped(2) == 20
    # Subsequent call should compute again (since cache never stored the value)
    assert wrapped(2) == 20

    # Cache should remain empty
    assert dict(cache) == {}
