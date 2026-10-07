import threading
import warnings
import types

import pytest

# Import the module under test
import cachetools._cachedmethod as cm


def test_unlocked_info_hits_and_misses():
    """Verify that the unlocked info descriptor tracks hits and misses."""
    calls = []

    def method(self, x):
        calls.append(x)
        return x * 2

    def cache_factory(self):
        return self._cache

    def key(self, x):
        return x

    def info(cache, hits, misses):
        # return a tuple we can assert on
        return (len(cache), hits, misses)

    class MyClass:
        def __init__(self):
            self._cache = {}

        # the descriptor is created manually using the private _wrapper
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
    assert obj.foo(1) == 2
    assert calls == [1]
    # second call – hit
    assert obj.foo(1) == 2
    assert calls == [1]  # method not called again

    # third call with a new argument – miss
    assert obj.foo(3) == 6
    assert calls == [1, 3]

    # cache_info should reflect 2 hits (second call of 1) and 2 misses (first 1 and 3)
    cache_len, hits, misses = obj.foo.cache_info()
    assert cache_len == 2  # keys 1 and 3 stored
    assert hits == 1       # only the second call of 1 was a hit
    assert misses == 2

    # clear cache and verify counters reset
    obj.foo.cache_clear()
    assert obj.foo.cache == {}
    cache_len, hits, misses = obj.foo.cache_info()
    assert (cache_len, hits, misses) == (0, 0, 0)


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
            lock=DummyLock(),
            cond=None,
            info=None,
        )

    obj = MyClass()
    # first call – cache miss
    assert obj.foo(10) == 15
    # second call – cache hit, lock still used
    assert obj.foo(10) == 15

    # The lock should have been entered and exited twice (once per call)
    assert lock_calls == ["enter", "exit", "enter", "exit"]


def test_descriptor_without_dict_raises_type_error():
    """Objects without a __dict__ (e.g., slots) should raise TypeError when used."""
    def method(self, x):
        return x

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
    # Accessing the descriptor should raise TypeError because __dict__ is missing
    with pytest.raises(TypeError) as exc:
        obj.foo(1)
    assert "No '__dict__' attribute" in str(exc.value)


def test_classmethod_deprecation_warning():
    """Accessing the wrapper with a class as the object should emit a deprecation warning."""
    def method(self, x):
        return x

    def cache_factory(self):
        return {}

    def key(self, x):
        return x

    # Build the descriptor manually so we can instantiate the Wrapper with a class
    descriptor = cm._wrapper(
        method=method,
        cache=cache_factory,
        key=key,
        lock=None,
        cond=None,
        info=None,
    )

    # The Wrapper class is stored as descriptor.Wrapper
    WrapperCls = descriptor.Wrapper  # type: ignore[attr-defined]

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        # Passing a class (type) as the obj triggers the deprecation warning
        WrapperCls(types.SimpleNamespace)  # any class object

    # Exactly one warning, of the correct type and message
    assert len(w) == 1
    warning = w[0]
    assert issubclass(warning.category, DeprecationWarning)
    assert "decorating class methods with @cachedmethod is deprecated" in str(warning.message)


def test_cache_property_exposes_underlying_cache():
    """The wrapper's cache property should return the cache object for the instance."""
    def method(self):
        return 42

    def cache_factory(self):
        return self._cache

    def key(self):
        return "k"

    class MyClass:
        def __init__(self):
            self._cache = {"k": 99}

        foo = cm._wrapper(
            method=method,
            cache=cache_factory,
            key=key,
            lock=None,
            cond=None,
            info=None,
        )

    obj = MyClass()
    # The cache property should give us the underlying dict
    assert obj.foo.cache is obj._cache
    # The cache_key property should be a callable that incorporates the instance
    assert callable(obj.foo.cache_key)
    # Using the cache_key directly should produce the same key as the method would use
    assert obj.foo.cache_key() == "k"
