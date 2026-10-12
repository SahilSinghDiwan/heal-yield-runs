import threading
import warnings

import pytest

from cachetools import _cachedmethod


def test_unlocked_info_caching_and_clear():
    """Test the unlocked path with an info function."""
    # Simple method to double the input
    def compute(self, x):
        return x * 2

    # Cache and key function
    cache = {}
    key = lambda self, x: x
    info = lambda c, hits, misses: (len(c), hits, misses)

    # Build the descriptor
    descriptor = _cachedmethod._wrapper(compute, lambda self: cache, key, info=info)

    class A:
        method = descriptor

    a = A()

    # First call: miss
    assert a.method(3) == 6
    assert cache == {3: 6}
    # cache_info should report 1 entry, 0 hits, 1 miss
    assert a.method.cache_info() == (1, 0, 1)

    # Second call with same argument: hit
    assert a.method(3) == 6
    assert a.method.cache_info() == (1, 1, 1)

    # Different argument: another miss
    assert a.method(4) == 8
    assert a.method.cache_info() == (2, 1, 2)

    # Clear the cache and verify counters reset
    a.method.cache_clear()
    assert cache == {}
    assert a.method.cache_info() == (0, 0, 0)


def test_descriptor_without_instance_dict_raises():
    """Accessing a cachedmethod on an object without __dict__ should raise TypeError."""
    def compute(self, x):
        return x

    cache = {}
    key = lambda self, x: x

    descriptor = _cachedmethod._wrapper(compute, lambda self: cache, key)

    class B:
        __slots__ = ()
        method = descriptor

    b = B()
    # Accessing the method should raise a TypeError with a specific message
    with pytest.raises(TypeError) as exc:
        b.method(1)
    msg = str(exc.value)
    assert "__dict__" in msg
    assert "B" in msg
    assert "method" in msg


def test_deprecated_classmethod_warning_and_cache_clear():
    """When a lock is supplied without an info function, the descriptor is deprecated
    and using it as a classmethod should emit a DeprecationWarning."""
    def compute(self, x):
        return x + 1

    cache = {}
    key = lambda self, x: x
    lock = threading.Lock()

    # This creates a _DeprecatedDescriptorBase because `info` is None and `lock` is given.
    descriptor = _cachedmethod._wrapper(compute, lambda self: cache, key, lock=lock)

    class C:
        method = descriptor

    c = C()

    # Instance call works normally
    assert c.method(10) == 11
    assert cache == {10: 11}

    # Class call should raise a DeprecationWarning and still return the correct value
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = C.method(20)  # triggers __call__ on the descriptor
        assert result == 21
        # One warning should have been emitted about classmethod usage
        assert any(
            issubclass(warn.category, DeprecationWarning) and
            "decorating class methods with @cachedmethod is deprecated" in str(warn.message)
            for warn in w
        )

    # The cache should now contain both entries
    assert cache == {10: 11, 20: 21}

    # cache_clear on the descriptor (class level) should clear the cache
    C.method.cache_clear(C)
    assert cache == {}

    # After clearing, a new call repopulates the cache
    assert c.method(30) == 31
    assert cache == {30: 31}


def test_descriptor_properties_exposed_on_wrapper():
    """The wrapper returned by _wrapper should expose cache, cache_key, cache_lock, and cache_condition."""
    def compute(self, x):
        return x

    cache = {}
    key = lambda self, x: x
    lock = threading.Lock()
    cond = threading.Condition(lock)

    descriptor = _cachedmethod._wrapper(
        compute,
        lambda self: cache,
        key,
        lock=lock,
        cond=cond,
        info=lambda c, h, m: (len(c), h, m),
    )

    # The descriptor should have the properties set directly on it
    assert descriptor.cache is not None
    assert descriptor.cache_key is key
    assert descriptor.cache_lock is lock
    assert descriptor.cache_condition is cond

    class D:
        method = descriptor

    d = D()
    # Accessing the method should still work and use the same cache
    assert d.method(5) == 5
    assert cache == {5: 5}
