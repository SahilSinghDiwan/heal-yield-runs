import warnings

import pytest

import cachetools._cachedmethod as cm


def test_unlocked_info_hits_and_misses():
    """Validate that the unlocked info descriptor tracks hits and misses."""

    calls = []

    def method(self, x):
        calls.append(x)
        return x * 2

    def cache_factory(self):
        return self._cache

    def key(self, x):
        return x

    def info(cache, hits, misses):
        return {"hits": hits, "misses": misses, "size": len(cache)}

    class MyClass:
        def __init__(self):
            self._cache = {}

        foo = cm._wrapper(
            method=method,
            cache=cache_factory,
            key=key,
            lock=None,
            cond=None,
            info=info,
        )

    obj = MyClass()
    # first call – miss
    assert obj.foo(3) == 6
    # second call – hit
    assert obj.foo(3) == 6
    # third call – miss with different key
    assert obj.foo(4) == 8

    # cache info should reflect 1 hit and 2 misses
    cache_info = obj.foo.cache_info()
    assert cache_info["hits"] == 1
    assert cache_info["misses"] == 2
    assert cache_info["size"] == 2
    # underlying cache should contain both keys
    assert obj.foo.cache == {3: 6, 4: 8}
    # method should have been called only for the two distinct inputs
    assert calls == [3, 4]


def test_locked_descriptor_uses_custom_lock():
    """Ensure that a custom lock object is used and that caching works."""

    lock_calls = []

    class DummyLock:
        def __enter__(self):
            lock_calls.append("enter")
            return self

        def __exit__(self, exc_type, exc, tb):
            lock_calls.append("exit")
            return False

    # lock must be a callable returning a context manager per the implementation
    def lock_factory(_):
        return DummyLock()

    def method(self, x):
        return x + 5

    def cache_factory(self):
        return self._cache

    def key(self, x):
        return x

    class MyClass:
        def __init__(self):
            self._cache = {}

        foo = cm._wrapper(
            method=method,
            cache=cache_factory,
            key=key,
            lock=lock_factory,
            cond=None,
            info=None,
        )

    obj = MyClass()
    # first call – cache miss
    assert obj.foo(10) == 15
    # second call – cache hit (should still use the lock)
    assert obj.foo(10) == 15

    # lock should have been entered and exited twice (once per call)
    assert lock_calls == ["enter", "exit", "enter", "exit"]


def test_descriptor_without_dict_raises_type_error():
    """Objects without a __dict__ (e.g., slots) should emit a deprecation warning
    and still function, because the descriptor is marked as deprecated."""
    def method(self, x):
        return x * 3

    def cache_factory(self):
        return self._cache

    def key(self, x):
        return x

    class SlotClass:
        __slots__ = ["_cache"]

        def __init__(self):
            self._cache = {}

        foo = cm._wrapper(
            method=method,
            cache=cache_factory,
            key=key,
            lock=None,
            cond=None,
            info=None,
        )

    obj = SlotClass()
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = obj.foo(2)
        # The call should succeed and return the computed value
        assert result == 6
        # A DeprecationWarning about missing __dict__ should be emitted
        assert any(
            issubclass(warn.category, DeprecationWarning)
            and "No '__dict__' attribute" in str(warn.message)
            for warn in w
        )
    # The value should be cached despite the warning
    assert obj.foo.cache == {2: 6}
    # Subsequent call hits the cache (no additional warning)
    with warnings.catch_warnings(record=True) as w2:
        warnings.simplefilter("always")
        assert obj.foo(2) == 6
        assert not w2  # no new warnings


def test_classmethod_deprecation_warning():
    """Calling a cachedmethod defined as a classmethod should raise a deprecation warning."""
    def method(cls, x):
        return x * 2

    def cache_factory(cls):
        return cls._cache

    def key(cls, x):
        return x

    class MyClass:
        _cache = {}

        foo = cm._wrapper(
            method=method,
            cache=cache_factory,
            key=key,
            lock=None,
            cond=None,
            info=None,
        )

    with pytest.warns(DeprecationWarning, match="decorating class methods"):
        # Access via class triggers the deprecation warning
        assert MyClass.foo(3) == 6


def test_cache_property_exposes_underlying_cache():
    """The wrapper's cache property should expose the underlying cache object."""
    def method(self, x):
        return x + 1

    def cache_factory(self):
        return self._cache

    def key(self, x):
        return x

    class MyClass:
        def __init__(self):
            self._cache = {}

        foo = cm._wrapper(
            method=method,
            cache=cache_factory,
            key=key,
            lock=None,
            cond=None,
            info=None,
        )

    obj = MyClass()
    # Before any call, cache should be empty
    assert obj.foo.cache == {}
    # After a call, the cache should contain the computed value
    assert obj.foo(5) == 6
    assert obj.foo.cache == {5: 6}
