import threading
import warnings

import pytest

from cachetools import _cachedmethod


def test_unlocked_info_caching_and_clear():
    """Basic caching behavior for the unlocked info variant."""
    calls = []

    def compute(self, x):
        calls.append(x)
        return x * 2

    cache = {}
    key = lambda self, x: x
    info = lambda c, h, m: (len(c), h, m)

    descriptor = _cachedmethod._wrapper(compute, lambda self: cache, key, info=info)

    class A:
        method = descriptor

    a = A()
    # First call computes and caches
    assert a.method(3) == 6
    assert calls == [3]
    # Second call hits cache
    assert a.method(3) == 6
    assert calls == [3]  # no new call
    # Cache info reflects one hit and one miss
    assert a.method.cache_info() == (1, 1, 0)
    # Clear cache resets info
    a.method.cache_clear()
    assert a.method.cache_info() == (0, 0, 0)
    # After clear, call recomputes
    assert a.method(3) == 6
    assert calls == [3, 3]


def test_descriptor_without_instance_dict_works_and_warns():
    """Accessing a cachedmethod on an object without __dict__ should warn and still work."""
    def compute(self, x):
        return x

    cache = {}
    key = lambda self, x: x

    descriptor = _cachedmethod._wrapper(compute, lambda self: cache, key)

    class B:
        __slots__ = ()
        method = descriptor

    b = B()
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = b.method(1)
        # The call should succeed and return the argument
        assert result == 1
        # A DeprecationWarning should have been emitted
        assert any(isinstance(wi.message, DeprecationWarning) for wi in w)
        # The warning message should mention the missing __dict__
        assert any("No '__dict__' attribute on 'B' instance" in str(wi.message) for wi in w)


def test_deprecated_classmethod_warning_and_cache_clear():
    """When a lock is supplied without an info function, the descriptor is deprecated.
    Using it as a classmethod should emit a DeprecationWarning and support cache clearing."""
    def compute(self, x):
        return x + 1

    cache = {}
    key = lambda self, x: x
    # lock must be a callable returning a lock object
    lock_func = lambda self: threading.Lock()

    descriptor = _cachedmethod._wrapper(compute, lambda self: cache, key, lock=lock_func)

    class C:
        method = descriptor

    c = C()
    # Instance call works normally
    assert c.method(10) == 11
    # Cache now contains the result
    assert cache[10] == 11

    # Access via class should emit a DeprecationWarning and still work
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = C.method(20)
        assert result == 21
        assert any(isinstance(wi.message, DeprecationWarning) for wi in w)
        assert any("decorating class methods with @cachedmethod is deprecated" in str(wi.message) for wi in w)

    # Cache should have stored the classmethod call as well
    assert cache[20] == 21

    # Use the deprecated cache_clear on the class
    C.method.cache_clear(C)
    # Cache should be empty after clear
    assert not cache


def test_descriptor_properties_exposed_on_wrapper():
    """The wrapper returned by _wrapper should expose cache, cache_key, cache_lock, and cache_condition."""
    def compute(self, x):
        return x

    cache = {}
    key = lambda self, x: x
    lock_func = lambda self: threading.Lock()
    cond_func = lambda self: threading.Condition(lock_func(self))

    descriptor = _cachedmethod._wrapper(
        compute,
        lambda self: cache,
        key,
        lock=lock_func,
        cond=cond_func,
        info=lambda c, h, m: (len(c), h, m),
    )

    # The descriptor should have the properties set directly on it
    assert descriptor.cache is cache
    assert descriptor.cache_key is key
    assert descriptor.cache_lock is lock_func
    assert descriptor.cache_condition is cond_func

    class D:
        method = descriptor

    d = D()
    # Accessing the method should work and use the same cache
    assert d.method(5) == 5
    assert cache[5] == 5
