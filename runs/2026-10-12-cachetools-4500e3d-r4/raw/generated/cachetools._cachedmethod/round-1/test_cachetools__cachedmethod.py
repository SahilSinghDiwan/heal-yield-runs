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
        cached_info = cm._locked(
            method,
            cache=lambda self: self._cache,
            key=lambda self, x: x,
            lock=lambda self: lock,
        )
        # manually set the info function on the descriptor returned by _locked
        cached_info = cm._wrapper(
            method,
            cache=lambda self: self._cache,
            key=lambda self, x: x,
            lock=lock,
            info=info,
        )

    a = A()
    # first call: miss
    assert a.cached_info(1) == 2
    # second call: hit
    assert a.cached_info(1) == 2
    # cache_info should report 1 hit, 1 miss
    assert a.cached_info.cache_info() == (1, 1)


def test_deprecated_classmethod_warning():
    """Calling a cached method via the class should emit a DeprecationWarning."""
    lock = threading.Lock()

    def method(self, x):
        return x - 1

    class D:
        def __init__(self):
            self._cache = {}

        # descriptor defined inside the class body
        qux = cm._locked(
            method,
            cache=lambda self: self._cache,
            key=lambda self, x: x,
            lock=lambda self: lock,
        )

    # Access via the class should warn; we need to pass the class as the first argument
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = D.qux(D, 10)  # class access, passing class as self
        assert result == 9
        assert any(issubclass(item.category, DeprecationWarning) for item in w)


def test_descriptor_without_dict_raises_type_error():
    """Objects without a __dict__ should raise a TypeError when caching is attempted."""
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
    # Accessing the cached method should raise TypeError because the instance lacks __dict__
    with pytest.raises(TypeError):
        nd.cached(5)


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
        lock=lock,
        cond=cond,
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

    # Ensure they point to the original callables
    assert descriptor.cache is cache_func
    assert descriptor.cache_key is key_func
    assert descriptor.cache_lock is lock
    assert descriptor.cache_condition is cond

    # Verify that the cached method works and records info correctly
    assert e.f(2) == 20
    assert e.f(2) == 20
    # cache_info should return (hits, misses) = (1, 1)
    assert e.f.cache_info() == (1, 1)


def test_condition_caching():
    """Test that a condition‑based cached method works as expected."""
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
    # First call populates the cache
    assert b.cached(5) == 6
    # Second call hits the cache
    assert b.cached(5) == 6
