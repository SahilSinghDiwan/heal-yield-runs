import threading
import warnings

import pytest

import cachetools._cachedmethod as cm


def test_locked_caching_and_info():
    """Ensure that a locked cached method records hits and misses correctly."""
    lock = threading.Lock()

    def method(self, x):
        return x * 2

    def info(cache, hits, misses):
        return hits, misses

    class A:
        def __init__(self):
            self._cache = {}

        # descriptor defined inside the class body so __set_name__ is called
        cached = cm._locked(
            method,
            cache=lambda self: self._cache,
            key=lambda self, x: x,
            lock=lambda self: lock,
        )
        # attach info via a separate descriptor that includes info
        cached_info = cm._wrapper(
            method,
            cache=lambda self: self._cache,
            key=lambda self, x: x,
            lock=lambda self: lock,
            info=info,
        )

    a = A()
    # first call: miss
    assert a.cached_info(1) == 2
    # second call: hit (same key)
    assert a.cached_info(1) == 2
    # verify that cache_info reports 1 hit and 1 miss
    assert a.cached_info.cache_info() == (1, 1)


def test_condition_caching():
    """Validate that a condition‑based cached method works and respects the condition."""
    lock = threading.Lock()
    cond = threading.Condition(lock)

    def method(self, x):
        return x + 1

    class B:
        def __init__(self):
            self._cache = {}

        cached = cm._condition(
            method,
            cache=lambda self: self._cache,
            key=lambda self, x: x,
            lock=lambda self: lock,
            cond=lambda self: cond,
        )

    b = B()
    # first call: miss
    assert b.cached(10) == 11
    # second call: hit (same key)
    assert b.cached(10) == 11
    # ensure cache was populated
    assert b._cache[10] == 11


def test_descriptor_without_dict_raises_type_error():
    """Objects without a __dict__ should raise a DeprecationWarning (not TypeError) when caching is attempted."""
    def method(self, x):
        return x

    class NoDict:
        __slots__ = ("_cache",)  # allow _cache attribute but no __dict__

        def __init__(self):
            self._cache = {}

        # descriptor defined inside the class body
        cached = cm._unlocked(
            method,
            cache=lambda self: self._cache,
            key=lambda self, x: x,
        )

    nd = NoDict()
    # Accessing the cached method should emit a DeprecationWarning but still work
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = nd.cached(5)
        assert result == 5
        # a warning should have been issued about missing __dict__
        assert any(
            issubclass(warn.category, DeprecationWarning)
            and "No '__dict__' attribute" in str(warn.message)
            for warn in w
        ), "Expected a DeprecationWarning about missing __dict__"


def test_wrapper_properties_exposed_on_descriptor():
    """The wrapper returned by _wrapper should expose cache, cache_key, etc."""
    lock = threading.Lock()
    cond = threading.Condition(lock)

    def method(self, x):
        return x * 10

    cache_func = lambda self: self._cache
    key_func = lambda self, x: x
    info_func = lambda cache, h, m: (h, m)

    # Use _wrapper directly to get a descriptor with all properties set
    descriptor = cm._wrapper(
        method,
        cache=cache_func,
        key=key_func,
        lock=lambda self: lock,
        cond=lambda self: cond,
        info=info_func,
    )

    class E:
        def __init__(self):
            self._cache = {}

        # attach descriptor
        f = descriptor

    e = E()
    # The descriptor itself should have the properties set (as per _wrapper)
    assert hasattr(descriptor, "cache")
    assert hasattr(descriptor, "cache_key")
    assert hasattr(descriptor, "cache_lock")
    assert hasattr(descriptor, "cache_condition")

    # Ensure they point to the original callables (or objects for lock/cond)
    assert descriptor.cache is cache_func
    assert descriptor.cache_key is key_func
    assert descriptor.cache_lock is lock
    assert descriptor.cache_condition is cond

    # Verify that the cached method works and records info correctly
    assert e.f(2) == 20
    # cache_info should return (hits, misses) = (0, 1) after a single miss
    assert e.f.cache_info() == (0, 1)
