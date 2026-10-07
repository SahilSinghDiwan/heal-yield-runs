import warnings

import pytest

import cachetools._cachedmethod as cm


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
    # second call – cache hit (still uses the lock for the read path)
    assert obj.foo(10) == 15

    # lock should have been entered and exited twice per call:
    # once for the read attempt and once for the write/commit attempt.
    assert lock_calls == [
        "enter", "exit",  # first read
        "enter", "exit",  # first write
        "enter", "exit",  # second read (hit)
        "enter", "exit",  # second write (no-op but still entered)
    ]


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
    # Subsequent call also works (warning may be emitted again)
    with warnings.catch_warnings(record=True) as w2:
        warnings.simplefilter("always")
        assert obj.foo(2) == 6
        # At least one warning should be present (implementation may warn each access)
        assert any(
            issubclass(warn.category, DeprecationWarning)
            and "No '__dict__' attribute" in str(warn.message)
            for warn in w2
        )


def test_classmethod_deprecation_warning():
    """Calling a cachedmethod defined as a classmethod via the descriptor object
    should raise a deprecation warning."""
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

    # Access the underlying descriptor directly from the class dict.
    descriptor = MyClass.__dict__["foo"]
    # Calling the descriptor as a function should emit a DeprecationWarning
    # and correctly compute the result.
    with pytest.warns(DeprecationWarning, match="decorating class methods"):
        assert descriptor(MyClass, 3) == 6
