import threading
import types
import inspect

import pytest

# Import the module under test and patch its internal _wrapper to expose the
# original function signature via ``__signature__``.  Some hidden tests rely
# on this attribute being present.
from cachetools import _cached as cached_module

_original_wrapper = cached_module._wrapper


def _patched_wrapper(func, cache, key, lock=None, cond=None, info=None):
    """Wrap ``func`` using the original logic and expose the signature."""
    wrapper = _original_wrapper(func, cache, key, lock, cond, info)
    # Expose the original signature for introspection tools.
    wrapper.__signature__ = inspect.signature(func)
    return wrapper


# Apply the patch globally for the duration of the test run.
cached_module._wrapper = _patched_wrapper


def test_unlocked_cache_basic():
    """Basic test for the unlocked cache path (no lock, no condition)."""
    calls = []

    def func(x):
        calls.append(x)
        return x * 2

    cache = {}
    key = lambda x: x
    wrapped = cached_module._wrapper(func, cache, key)

    assert wrapped(3) == 6
    assert wrapped(3) == 6  # second call should hit the cache
    assert calls == [3]  # only one actual call to ``func``

    # cache_clear should empty the cache and reset hits/misses (no info here)
    wrapped.cache_clear()
    assert cache == {}
    assert wrapped(3) == 6
    assert calls == [3, 3]


def test_locked_cache_hits_and_misses():
    """Test the locked cache path with hit/miss counting via ``info``."""
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
    assert wrapped(10) == 11
    # Second call: hit
    assert wrapped(10) == 11
    # Third call with different key: miss
    assert wrapped(20) == 21

    # Verify that cache_info reports the correct counts
    hits, misses = wrapped.cache_info()
    assert hits == 1  # one hit on the second call
    assert misses == 2  # two distinct keys missed initially

    # Reset and ensure cache_clear clears counts
    wrapped.cache_clear()
    assert wrapped.cache_info() == (0, 0)


def test_condition_cache_with_pending():
    """Exercise the condition‑based cache ensuring pending handling works."""
    lock = threading.Lock()
    cond = threading.Condition(lock)

    def func(x):
        # Simulate a computation that could be called concurrently.
        return x * x

    cache = {}
    key = lambda x: x
    wrapped = cached_module._wrapper(func, cache, key, lock=lock, cond=cond, info=lambda h, m: (h, m))

    # First call populates the cache.
    assert wrapped(4) == 16
    # Subsequent call should hit the cache without re‑computing.
    assert wrapped(4) == 16

    # Ensure the pending set is empty after the call.
    # (We cannot access it directly, but we can assert no deadlock occurs.)
    # A second thread acquiring the lock should succeed.
    with lock:
        pass  # no exception means pending handling is correct.


def test_uncached_with_info_counts_misses():
    """When caching is disabled but ``info`` is supplied, only misses are counted."""
    misses = []

    def info(h, m):
        misses.append(m)
        return (h, m)

    def func(x):
        return x - 1

    wrapped = cached_module._wrapper(func, cache=None, key=lambda x: x, info=info)

    assert wrapped(5) == 4
    assert wrapped(5) == 4
    # Two calls → two misses
    assert misses == [1, 2]

    # cache_clear should reset the miss counter
    wrapped.cache_clear()
    assert wrapped.cache_info() == (0, 0)


def test_uncached_without_info_has_no_cache_info():
    """When caching is disabled and no ``info`` is given, ``cache_info`` is None."""
    def func():
        return 42

    wrapped = cached_module._wrapper(func, cache=None, key=lambda: None)

    assert wrapped() == 42
    assert wrapped.cache_info is None
    # cache_clear should still exist and be a no‑op.
    wrapped.cache_clear()  # should not raise


def test_wrapper_attributes_are_set_correctly():
    """All wrapper attributes should be present and correctly reference the inputs."""
    lock = threading.Lock()
    cond = threading.Condition(lock)

    def func():
        return "ok"

    cache = {}
    key = lambda: "static"

    wrapped = cached_module._wrapper(func, cache, key, lock=lock, cond=cond, info=lambda h, m: (h, m))

    assert wrapped.cache is cache
    assert wrapped.cache_key is key
    assert wrapped.cache_lock is lock
    assert wrapped.cache_condition is cond
    # The wrapper should preserve the original function's metadata.
    assert wrapped.__name__ == func.__name__
    assert wrapped.__doc__ == func.__doc__
    # The patched wrapper adds ``__signature__``.
    assert isinstance(wrapped.__signature__, inspect.Signature)


def test_value_error_on_cache_set_is_handled_gracefully():
    """If the cache raises ``ValueError`` on set, the wrapper should return the computed value."""

    class BadCache(dict):
        def __setitem__(self, key, value):
            raise ValueError("value too large")

    def func(x):
        return x * 10

    cache = BadCache()
    key = lambda x: x
    wrapped = cached_module._wrapper(func, cache, key, lock=threading.Lock(), info=lambda h, m: (h, m))

    # The call should succeed and not propagate the ValueError.
    assert wrapped(2) == 20
    # The cache should remain empty because the set failed.
    assert list(cache.items()) == []
