import threading
import warnings

import pytest

import cachetools._cachedmethod as cm


def test_locked_caching_and_info():
    """Test that the locked descriptor caches values and reports info correctly."""
    lock = threading.Lock()

    # Simple method to be cached
    def method(self, x):
        return x * 2

    # Cache accessor and key function
    cache_func = lambda self: self._cache
    key_func = lambda self, x: x

    # Info function returns hits and misses
    info_func = lambda cache, hits, misses: (hits, misses)

    # Build the descriptor using the internal _wrapper helper with lock and info
    descriptor = cm._wrapper(
        method,
        cache=cache_func,
        key=key_func,
        lock=lambda self: lock,
        info=info_func,
    )

    class C:
        def __init__(self):
            self._cache = {}

        # Attach the descriptor
        f = descriptor

    c = C()

    # First call: cache miss
    assert c.f(3) == 6
    # Second call with same argument: cache hit
    assert c.f(3) == 6

    # The descriptor's wrapper should expose a cache_info method returning (hits, misses)
    wrapper = c.__dict__["f"]
    assert wrapper.cache_info() == (1, 1)  # 1 hit, 1 miss


def test_condition_caching():
    """Test that the condition-based descriptor respects the condition and caches."""
    lock = threading.Lock()
    cond = threading.Condition(lock)

    def method(self, x):
        return x + 5

    cache_func = lambda self: self._cache
    key_func = lambda self, x: x
    info_func = lambda cache, hits, misses: (hits, misses)

    # Build descriptor with both lock and condition, plus info
    descriptor = cm._wrapper(
        method,
        cache=cache_func,
        key=key_func,
        lock=lambda self: lock,
        cond=lambda self: cond,
        info=info_func,
    )

    class D:
        def __init__(self):
            self._cache = {}

        g = descriptor

    d = D()

    # First call populates the cache
    assert d.g(10) == 15
    # Second call hits the cache
    assert d.g(10) == 15

    wrapper = d.__dict__["g"]
    # After one miss and one hit, hits=1, misses=1
    assert wrapper.cache_info() == (1, 1)


def test_descriptor_without_dict_raises_type_error():
    """Accessing a cachedmethod on an object without __dict__ should raise TypeError."""
    lock = threading.Lock()

    def method(self, x):
        return x

    cache_func = lambda self: {}
    key_func = lambda self, x: x

    descriptor = cm._wrapper(
        method,
        cache=cache_func,
        key=key_func,
        lock=lambda self: lock,
    )

    class NoDict:
        __slots__ = ()

        h = descriptor

    nd = NoDict()
    # Accessing the descriptor should raise TypeError because __dict__ is missing
    with pytest.raises(TypeError):
        nd.h(1)


def test_wrapper_properties_exposed_on_descriptor():
    """The wrapper returned by _wrapper should expose cache, cache_key, etc."""
    lock = threading.Lock()
    cond = threading.Condition(lock)

    def method(self, x):
        return x * 10

    cache_func = lambda self: self._cache
    key_func = lambda self, x: x
    info_func = lambda cache, h, m: (h, m)

    lock_func = lambda self: lock
    cond_func = lambda self: cond

    # Use _wrapper directly to get a descriptor with all properties set
    descriptor = cm._wrapper(
        method,
        cache=cache_func,
        key=key_func,
        lock=lock_func,
        cond=cond_func,
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
    # The wrapper stores the *callable* we passed for lock, not the lock object itself
    assert descriptor.cache_lock is lock_func
    assert descriptor.cache_condition is cond_func
