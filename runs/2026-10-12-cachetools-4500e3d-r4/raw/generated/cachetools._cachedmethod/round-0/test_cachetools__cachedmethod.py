import builtins
import threading
import warnings

import pytest

import cachetools._cachedmethod as cm


def test_unlocked_caching_and_cache_clear():
    """Basic unlocked caching: method called once, cache cleared resets."""
    calls = {"cnt": 0}

    def method(self, x):
        calls["cnt"] += 1
        return x * 2

    class A:
        def __init__(self):
            self._cache = {}

    # attach the cached descriptor
    A.foo = cm._unlocked(method, cache=lambda self: self._cache, key=lambda self, x: x)

    a = A()
    # first call computes
    assert a.foo(3) == 6
    assert calls["cnt"] == 1
    # second call hits cache, method not called again
    assert a.foo(3) == 6
    assert calls["cnt"] == 1

    # different argument not cached yet
    assert a.foo(4) == 8
    assert calls["cnt"] == 2

    # clear cache and ensure method is called again
    a.foo.cache_clear()
    assert a.foo(3) == 6
    assert calls["cnt"] == 3


def test_locked_caching_and_info():
    """Locked version with hit/miss info."""
    hits_misses = {"hits": 0, "misses": 0}
    lock = threading.Lock()

    def method(self, x):
        return x + 5

    def info(cache, hits, misses):
        hits_misses["hits"] = hits
        hits_misses["misses"] = misses
        return (hits, misses)

    class B:
        def __init__(self):
            self._cache = {}

    B.bar = cm._locked_info(
        method,
        cache=lambda self: self._cache,
        key=lambda self, x: x,
        lock=lambda self: lock,
        info=info,
    )

    b = B()
    # first call: miss
    assert b.bar(1) == 6
    assert hits_misses["hits"] == 0
    assert hits_misses["misses"] == 1
    # second call: hit
    assert b.bar(1) == 6
    assert hits_misses["hits"] == 1
    assert hits_misses["misses"] == 1

    # cache_info returns the tuple from info()
    assert b.bar.cache_info() == (1, 1)

    # clear cache resets counters
    b.bar.cache_clear()
    assert b.bar.cache_info() == (0, 0)


def test_condition_caching():
    """Condition + lock version ensures pending set handling."""
    lock = threading.Lock()
    cond = threading.Condition(lock)

    call_log = []

    def method(self, x):
        call_log.append(x)
        return x * x

    class C:
        def __init__(self):
            self._cache = {}

    C.baz = cm._condition(
        method,
        cache=lambda self: self._cache,
        key=lambda self, x: x,
        lock=lambda self: lock,
        cond=lambda self: cond,
    )

    c = C()
    # first call computes and caches
    assert c.baz(2) == 4
    assert call_log == [2]
    # second call hits cache, no extra call
    assert c.baz(2) == 4
    assert call_log == [2]

    # different key
    assert c.baz(3) == 9
    assert call_log == [2, 3]

    # clear cache via descriptor method
    c.baz.cache_clear()
    # after clear, method called again
    assert c.baz(2) == 4
    assert call_log == [2, 3, 2]


def test_deprecated_classmethod_warning():
    """Calling a cached method via the class should emit a DeprecationWarning."""
    lock = threading.Lock()

    def method(self, x):
        return x - 1

    class D:
        def __init__(self):
            self._cache = {}

    D.qux = cm._locked(
        method,
        cache=lambda self: self._cache,
        key=lambda self, x: x,
        lock=lambda self: lock,
    )

    # Using the descriptor via the class (i.e., as a classmethod) should warn
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = D.qux(10)  # class access
        assert result == 9
        assert any(issubclass(item.category, DeprecationWarning) for item in w)
        # The warning message should mention class methods
        assert any("class methods" in str(item.message) for item in w)

    # Using via an instance should not warn
    d = D()
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("error")
        assert d.qux(10) == 9
        assert not w  # no warnings


def test_descriptor_without_dict_raises_type_error():
    """Objects without a __dict__ should raise a TypeError when caching is attempted."""
    def method(self, x):
        return x

    class NoDict:
        __slots__ = ()  # no __dict__

        def __init__(self):
            self._cache = {}

    NoDict.cached = cm._unlocked(
        method,
        cache=lambda self: self._cache,
        key=lambda self, x: x,
    )

    nd = NoDict()
    # Accessing the descriptor should raise TypeError because __dict__ is missing
    with pytest.raises(TypeError) as exc:
        nd.cached(1)
    assert "No '__dict__' attribute" in str(exc.value)


def test_wrapper_properties_exposed_on_descriptor():
    """The wrapper returned by _wrapper should expose cache, cache_key, etc."""
    lock = threading.Lock()
    cond = threading.Condition(lock)

    def method(self, x):
        return x * 10

    # Use _wrapper directly to get a descriptor with all properties set
    descriptor = cm._wrapper(
        method,
        cache=lambda self: self._cache,
        key=lambda self, x: x,
        lock=lock,
        cond=cond,
        info=lambda cache, h, m: (h, m),
    )

    class E:
        def __init__(self):
            self._cache = {}

    # Attach descriptor
    E.f = descriptor

    e = E()
    # The descriptor itself should have the properties set (as per _wrapper)
    assert hasattr(descriptor, "cache")
    assert hasattr(descriptor, "cache_key")
    assert hasattr(descriptor, "cache_lock")
    assert hasattr(descriptor, "cache_condition")

    # Ensure they point to the original callables
    assert descriptor.cache is (lambda self: self._cache)
    assert descriptor.cache_key is (lambda self, x: x)
    assert descriptor.cache_lock is lock
    assert descriptor.cache_condition is cond

    # Normal usage still works
    assert e.f(2) == 20
