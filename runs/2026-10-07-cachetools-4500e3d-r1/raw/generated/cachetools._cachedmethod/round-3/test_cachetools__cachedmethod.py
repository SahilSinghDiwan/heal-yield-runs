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
    # first call – cache miss (read lock + write lock)
    assert obj.foo(10) == 15
    # second call – cache hit (only read lock)
    assert obj.foo(10) == 15

    # lock should have been entered and exited:
    # first call: read lock, then write lock
    # second call: read lock only (hit)
    assert lock_calls == [
        "enter", "exit",  # first read
        "enter", "exit",  # first write
        "enter", "exit",  # second read (hit)
    ]


def test_descriptor_without_dict_raises_type_error():
    """Accessing a cachedmethod on an object without __dict__ should raise TypeError."""

    def method(self, x):
        return x * 2

    def cache(self):
        return {}

    def key(self, x):
        return x

    class SlotClass:
        __slots__ = ()

        foo = cm._wrapper(
            method=method,
            cache=cache,
            key=key,
            lock=None,
            cond=None,
            info=None,
        )

    obj = SlotClass()
    # Accessing the descriptor should raise a TypeError because the instance
    # lacks a __dict__ to store the wrapper.
    with pytest.raises(TypeError) as exc:
        _ = obj.foo(1)
    assert "No '__dict__' attribute" in str(exc.value)


def test_classmethod_deprecation_warning():
    """Using @cachedmethod on a classmethod should emit a DeprecationWarning."""

    def method(cls, x):
        return x + 1

    def cache(cls):
        return {}

    def key(cls, x):
        return x

    class MyClass:
        @classmethod
        def foo(cls, x):
            return x + 1

        # Apply the wrapper directly to the classmethod function
        foo = cm._wrapper(
            method=method,
            cache=cache,
            key=key,
            lock=None,
            cond=None,
            info=None,
        )

    # Access via class should trigger the deprecation warning
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = MyClass.foo(3)
        assert result == 4
        # Two warnings: one from _warn_classmethod in _WrapperBase init,
        # another from the descriptor call path.
        assert any(issubclass(warn.category, DeprecationWarning) for warn in w)
