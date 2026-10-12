import threading

import pytest

import cachetools._cached as cached_module


def test_unlocked_cache_basic():
    """Basic functionality of an unlocked cache wrapper."""
    calls = []

    def func(x):
        calls.append(x)
        return x * 2

    cache = {}
    key = lambda x: x
    wrapped = cached_module._wrapper(func, cache, key)

    # First call computes and stores the result.
    assert wrapped(3) == 6
    assert calls == [3]
    assert cache == {3: 6}

    # Second call hits the cache, no new computation.
    assert wrapped(3) == 6
    assert calls == [3]  # unchanged
    assert cache == {3: 6}


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

    # cache_info should have been called implicitly only when accessed.
    # Access it now to trigger the info callback.
    assert wrapped.cache_info() == (2, 1)  # 2 hits, 1 miss
    # Verify that the info callback recorded the correct tuple.
    assert hits_misses[-1] == (2, 1)


def test_condition_cache_with_pending():
    """Condition-based wrapper should handle pending keys correctly."""
    lock = threading.Lock()
    cond = threading.Condition(lock)

    calls = []

    def func(x):
        calls.append(x)
        return x * x

    cache = {}
    key = lambda x: x
    wrapped = cached_module._wrapper(func, cache, key, lock=lock, cond=cond)

    # Simulate two threads calling the same key sequentially.
    # First call computes and stores.
    assert wrapped(4) == 16
    # Second call should hit the cache.
    assert wrapped(4) == 16
    # Verify only one computation occurred.
    assert calls == [4]
    # Cache should contain the result.
    assert cache == {4: 16}


def test_uncached_with_info_counts_misses():
    """When caching is disabled but ``info`` is supplied, only misses are counted."""
    misses = []

    def info(h, m):
        misses.append(m)
        return (h, m)

    def func(x):
        return x - 1

    wrapped = cached_module._wrapper(func, cache=None, key=lambda x: x, info=info)

    # Two calls – both are misses.
    assert wrapped(5) == 4
    assert wrapped(5) == 4

    # Access cache_info to trigger the info callback.
    assert wrapped.cache_info() == (0, 2)
    # The info callback should have been called once with the final miss count.
    assert misses == [2]


def test_uncached_without_info_has_no_cache_info():
    """Uncached wrapper without info should not provide a cache_info attribute."""
    def func(x):
        return x * 3

    wrapped = cached_module._wrapper(func, cache=None, key=lambda x: x)
    assert wrapped(2) == 6
    # cache_info should be None as per implementation.
    assert wrapped.cache_info is None


def test_wrapper_attributes_are_set_correctly():
    """All wrapper attributes should be set according to the parameters."""
    def func(x):
        return x

    cache = {}
    key = lambda x: x
    lock = threading.Lock()
    cond = threading.Condition(lock)

    # With lock and condition
    wrapped = cached_module._wrapper(func, cache, key, lock=lock, cond=cond, info=lambda h, m: (h, m))
    assert wrapped.cache is cache
    assert wrapped.cache_key is key
    assert wrapped.cache_lock is lock
    assert wrapped.cache_condition is cond

    # With only lock
    wrapped2 = cached_module._wrapper(func, cache, key, lock=lock, info=lambda h, m: (h, m))
    assert wrapped2.cache_lock is lock
    assert wrapped2.cache_condition is None

    # With only condition
    wrapped3 = cached_module._wrapper(func, cache, key, cond=cond, info=lambda h, m: (h, m))
    assert wrapped3.cache_lock is cond
    assert wrapped3.cache_condition is cond

    # With no lock/cond (unlocked)
    wrapped4 = cached_module._wrapper(func, cache, key, info=lambda h, m: (h, m))
    assert wrapped4.cache_lock is None
    assert wrapped4.cache_condition is None


def test_value_error_on_cache_set_is_handled_gracefully():
    """If the cache raises ``ValueError`` on set, the wrapper should return the computed value."""
    class BadCache(dict):
        def __setitem__(self, key, value):
            raise ValueError("value too large")

    def func(x):
        return x * 10

    cache = BadCache()
    key = lambda x: x
    lock = threading.Lock()
    wrapped = cached_module._wrapper(
        func,
        cache,
        key,
        lock=lock,
        info=lambda h, m: (h, m),
    )

    # The call should succeed and not propagate the ValueError.
    assert wrapped(2) == 20
    # Because dict's C implementation of setdefault bypasses __setitem__,
    # the value may have been stored. Accept either outcome.
    assert list(cache.items()) in ([], [(2, 20)])
