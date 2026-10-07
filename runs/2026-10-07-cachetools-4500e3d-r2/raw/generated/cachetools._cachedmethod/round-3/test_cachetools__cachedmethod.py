import threading

import pytest

from cachetools._cachedmethod import _wrapper


def make_descriptor(cache_func, key_func, lock=None, cond=None, info=None):
    """
    Helper to create a descriptor suitable for use as a method decorator.
    It returns a decorator that, when applied to a method, produces the
    appropriate cachedmethod descriptor via ``_wrapper``.
    """
    return lambda method: _wrapper(method, cache_func, key_func, lock, cond, info)


def simple_cache(self):
    """Return the per‑instance cache dictionary."""
    return self._cache


def simple_key(self, *args, **kwargs):
    """Use the positional arguments as the cache key."""
    return args


def simple_info(cache, hits, misses):
    """Return a tuple summarising the cache state."""
    return (len(cache), hits, misses)


def test_unlocked_caches_and_counts():
    """The unlocked descriptor should cache results and avoid recomputation."""
    class Foo:
        def __init__(self):
            self._cache = {}
            self.calls = 0

        @make_descriptor(simple_cache, simple_key)
        def compute(self, x):
            self.calls += 1
            return x * 2

    f = Foo()

    # First call computes the value.
    assert f.compute(3) == 6
    assert f.calls == 1
    # Result is cached.
    assert f._cache[(3,)] == 6

    # Second call with same argument hits the cache.
    assert f.compute(3) == 6
    assert f.calls == 1  # no additional call

    # Different argument is a cache miss.
    assert f.compute(4) == 8
    assert f.calls == 2
    assert f._cache[(4,)] == 8

    # Cache clear removes stored values.
    f.compute.cache_clear()
    assert f._cache == {}

    # After clearing, a call recomputes.
    assert f.compute(3) == 6
    assert f.calls == 3


def test_locked_caches_and_counts():
    """The locked descriptor should behave like the unlocked one but be thread‑safe."""
    lock = threading.Lock()

    class Bar:
        def __init__(self):
            self._cache = {}
            self.calls = 0

        @make_descriptor(simple_cache, simple_key, lock=lock, info=simple_info)
        def compute(self, x):
            self.calls += 1
            return x + 5

    b = Bar()

    # First call stores the result.
    assert b.compute(10) == 15
    assert b.calls == 1
    assert b._cache[(10,)] == 15

    # Second call hits the cache; calls count unchanged.
    assert b.compute(10) == 15
    assert b.calls == 1

    # Cache info reflects one hit and one miss.
    cache_len, hits, misses = b.compute.cache_info()
    assert cache_len == 1
    assert hits == 1
    assert misses == 1

    # Clear the cache and verify it is empty.
    b.compute.cache_clear()
    assert b._cache == {}
    cache_len, hits, misses = b.compute.cache_info()
    assert cache_len == 0
    assert hits == 0
    assert misses == 0


def test_conditioned_caches_and_counts():
    """The conditioned descriptor should also cache correctly while using a condition."""
    lock = threading.Lock()
    cond = threading.Condition(lock)

    class Baz:
        def __init__(self):
            self._cache = {}
            self.calls = 0

        @make_descriptor(simple_cache, simple_key, lock=lock, cond=cond, info=simple_info)
        def compute(self, x):
            self.calls += 1
            return x * x

    z = Baz()

    # First call caches the result.
    assert z.compute(5) == 25
    assert z.calls == 1
    assert z._cache[(5,)] == 25

    # Second call hits the cache.
    assert z.compute(5) == 25
    assert z.calls == 1

    # Cache info reflects hits/misses.
    cache_len, hits, misses = z.compute.cache_info()
    assert cache_len == 1
    assert hits == 1
    assert misses == 1

    # Clear and verify.
    z.compute.cache_clear()
    assert z._cache == {}
    cache_len, hits, misses = z.compute.cache_info()
    assert cache_len == 0
    assert hits == 0
    assert misses == 0
